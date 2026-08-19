"""The review stage: a different model, reading only, judging what gates cannot.

Everything a machine can decide has already been decided by the time this stage runs —
lint, types, the suite, the held-out suite, the red step. So the reviewer is given a
rubric of exactly the things a subprocess cannot check (correctness of the logic,
whether the change fits the plan, edge cases nobody wrote a test for, whether the next
person can read it) and is told, in the prompt, not to re-report what the gates own.
ADR 0005 puts it as: the LLM reviewer is *advisory*, on a different model, downstream
of the gates.

Three properties make its verdict worth acting on, and none of them is a request:

* **It cannot edit the code.** ``review_stage_guard`` confines every write to the
  ticket's context directory, so the reviewer physically cannot fix what it finds.
* **It cannot read the tests.** ``source_stage_guard`` blindfolds it the same way the
  implement stage is blindfolded, and the diff it is shown excludes the test files that
  the tests stage committed. That is not to protect the reviewer from the tests — it is
  because ``review.json`` is read by the *fix* stage, and a reviewer that could quote a
  test would hand back through a finding exactly what the opaque gate withholds.
* **What it says is structure, not prose.** ``review.json`` is validated and deduped by
  the runner, and only the severities in ``[review] fix_severities`` turn the loop.

The reviewer instead learns what the change was *supposed* to do from the acceptance
criteria in ``tests.json`` — the half of the tests artifact that is a statement of
requirements rather than a test body.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from types import MappingProxyType
from typing import Any

from flux.config import SEVERITIES, FluxConfig
from flux.diff import Diff
from flux.diff import parse as parse_diff
from flux.errors import ParkSignal
from flux.executor.types import ExecConfig, ExecResult, PromptPack
from flux.fsio import read_json_mapping, write_json_atomic
from flux.git import DiffResult, stage_commit, ticket_diff
from flux.jsonio import JsonMapping, as_json_list, as_json_mapping
from flux.metrics.record import GateOutcome
from flux.runner.artifact import ArtifactSpec
from flux.runner.context import TicketContext
from flux.runner.stage import Gate, Outcome
from flux.stages import tests as tests_stage
from flux.stages.guards import diff_exclusions, review_stage_guard, source_stage_guard
from flux.stages.hydration import artifact_slice, bullets, join, read_text, section

STAGE_NAME = "review"

ARTIFACT_FILENAME = "review.json"
CONTEXT_PACK_FILENAME = "context-pack.md"
PLAN_SUMMARY_FILENAME = "plan-summary.md"

FINDINGS_KEY = "findings"
SUMMARY_KEY = "summary"

AXES: tuple[str, ...] = ("correctness", "design-fit", "edge-cases", "readability")
"""The rubric. Named axes rather than "review this" because an unaxed review drifts to
whatever the model noticed first, and because a finding that fits no axis is usually a
finding the gates already own."""

_WHITESPACE = re.compile(r"\s+")
_NO_EXTRA: Mapping[str, Any] = MappingProxyType({})


def review_diff(ticket: TicketContext, settings: FluxConfig) -> DiffResult:
    """The change under review: this ticket's stage commits, minus the tests.

    A module function rather than a method because the fix stage needs the identical
    diff to resolve its hunks out of, and two stages computing "the diff" from two
    call sites is two chances for them to disagree about what is under review.

    T4c settled that ``git diff`` is ground truth here — it is what actually changed,
    rather than a tool's opinion about what changed.
    """
    return ticket_diff(
        ticket.worktree,
        ticket=ticket.ticket_id,
        exclude=diff_exclusions(ticket, settings),
    )


def artifact_path(ticket: TicketContext) -> Path:
    return ticket.context_dir / ARTIFACT_FILENAME


def read_artifact(ticket: TicketContext) -> JsonMapping | None:
    return read_json_mapping(artifact_path(ticket))


@dataclass(frozen=True, slots=True)
class Finding:
    """One reviewer finding, after the runner has normalised it.

    ``resolved``/``resolution`` are written by the *fix* stage into the same file, so a
    finding carries its own history: what was wrong, and what was done about it.
    """

    severity: str
    finding: str
    file: str = ""
    line: int = 0
    axis: str = ""
    suggestion: str = ""
    id: str = ""
    resolved: bool = False
    resolution: str = ""
    extra: JsonMapping = _NO_EXTRA
    """Anything else the reviewer wrote. Kept so normalising is never lossy."""

    @property
    def location(self) -> str:
        if not self.file:
            return "(no file given)"
        return f"{self.file}:{self.line}" if self.line > 0 else self.file

    @property
    def dedup_key(self) -> tuple[str, str, int, str]:
        """What makes two findings the same one: the place and the claim.

        Severity is deliberately *not* part of the key — the same defect reported twice
        at two severities is still one defect, and keeping both would let a reviewer
        inflate its own blocker count by restating itself.
        """
        text = _WHITESPACE.sub(" ", self.finding).strip().lower()[:120]
        return (self.file, self.axis, self.line, text)

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = dict(self.extra)
        payload.update(
            {
                "id": self.id,
                "severity": self.severity,
                "axis": self.axis,
                "file": self.file,
                "line": self.line,
                "finding": self.finding,
                "suggestion": self.suggestion,
                "resolved": self.resolved,
                "resolution": self.resolution,
            }
        )
        return payload

    @classmethod
    def from_json(cls, payload: JsonMapping) -> Finding:
        known = {
            "id",
            "severity",
            "axis",
            "file",
            "line",
            "finding",
            "suggestion",
            "resolved",
            "resolution",
        }
        return cls(
            severity=str(payload.get("severity", "")).strip().lower(),
            finding=str(payload.get("finding", "")).strip(),
            file=str(payload.get("file", "")).strip(),
            line=_int(payload.get("line")),
            axis=str(payload.get("axis", "")).strip().lower(),
            suggestion=str(payload.get("suggestion", "")).strip(),
            id=str(payload.get("id", "")).strip(),
            resolved=bool(payload.get("resolved", False)),
            resolution=str(payload.get("resolution", "")).strip(),
            extra=MappingProxyType({k: v for k, v in payload.items() if k not in known}),
        )


def read_findings(payload: JsonMapping) -> tuple[Finding, ...]:
    """Every finding in a ``review.json`` payload. Unreadable entries are skipped."""
    entries = as_json_list(payload.get(FINDINGS_KEY)) or []
    findings: list[Finding] = []
    for entry in entries:
        mapping = as_json_mapping(entry)
        if mapping is not None:
            findings.append(Finding.from_json(mapping))
    return tuple(findings)


def dedupe(findings: Iterable[Finding]) -> tuple[Finding, ...]:
    """The same findings with repeats dropped, keeping the most severe of each.

    The stage I/O table requires deduping here rather than asking the model not to
    repeat itself: a duplicated blocker is one extra fix-stage session and, at
    ``max_review_iters``, one parked ticket.
    """
    kept: dict[tuple[str, str, int, str], Finding] = {}
    for finding in findings:
        seen = kept.get(finding.dedup_key)
        if seen is None or _rank(finding.severity) < _rank(seen.severity):
            kept[finding.dedup_key] = finding
    return tuple(kept.values())


def number(findings: Sequence[Finding]) -> tuple[Finding, ...]:
    """Give every finding a stable, unique id — the handle the fix stage resolves by."""
    used: set[str] = set()
    numbered: list[Finding] = []
    for index, finding in enumerate(findings, start=1):
        identifier = finding.id if finding.id and finding.id not in used else f"R{index}"
        while identifier in used:
            identifier = f"R{index}-{len(used)}"
        used.add(identifier)
        numbered.append(replace(finding, id=identifier))
    return tuple(numbered)


def sort_findings(findings: Iterable[Finding]) -> tuple[Finding, ...]:
    """Most serious first, then by file and line. What a human reads top-down."""
    return tuple(sorted(findings, key=lambda f: (_rank(f.severity), f.file, f.line)))


def blocking(findings: Iterable[Finding], settings: FluxConfig) -> tuple[Finding, ...]:
    """Findings that must be resolved before the ticket may move on."""
    return tuple(f for f in findings if settings.review.blocks(f.severity))


def unresolved(findings: Iterable[Finding], settings: FluxConfig) -> tuple[Finding, ...]:
    return tuple(f for f in blocking(findings, settings) if not f.resolved)


def check_artifact(payload: JsonMapping) -> str:
    """Structural check the runner applies before the review stage may commit.

    An empty ``findings`` list is valid and is the outcome to hope for — "the change is
    clean" is a review. What is not valid is a finding with no severity, no location or
    no claim, because the fix stage would have nothing to act on and the loop would turn
    for nothing.
    """
    if not str(payload.get(SUMMARY_KEY, "")).strip():
        return f"{SUMMARY_KEY!r} must be a non-empty verdict on the change as a whole"
    entries = as_json_list(payload.get(FINDINGS_KEY))
    if entries is None:
        return f"{FINDINGS_KEY!r} must be a list (write [] if the change is clean)"
    for entry in entries:
        mapping = as_json_mapping(entry)
        if mapping is None:
            return f"every {FINDINGS_KEY!r} entry must be an object"
        finding = Finding.from_json(mapping)
        if finding.severity not in SEVERITIES:
            return (
                f"a finding has severity {finding.severity or '(missing)'!r}; use one of "
                f"{list(SEVERITIES)}"
            )
        if not finding.finding:
            return "every finding needs a non-empty 'finding' saying what is wrong"
        if not finding.file:
            return "every finding needs a 'file' so the fix stage knows where to look"
    return ""


ARTIFACT_SPEC = ArtifactSpec(
    path=ARTIFACT_FILENAME,
    kind="json",
    required_keys=(SUMMARY_KEY, FINDINGS_KEY),
    check=check_artifact,
    description=(
        "it is the whole of your review: a verdict plus a list of findings, each with a "
        "severity, a file, and what is wrong. Nothing you say outside it is read."
    ),
)

SYSTEM_PROMPT = """\
You are the review stage of the flux pipeline. A different model wrote the code you are \
about to read; your job is to judge it, not to change it.

Five things about this environment are enforced by the harness, not left to your \
judgement:

1. You cannot edit the repository. Every write outside the handoff artifact is blocked \
before it happens. Findings are how you act.
2. Lint, type checking and the full test suite have ALREADY PASSED on this change. \
Do not report anything a gate would have caught — a finding that says "this would fail \
type checking" is false, and it costs a paid session to disprove.
3. You cannot read the tests, and the diff you are shown excludes them. That is \
deliberate: what you write is read by the stage that fixes the code, and a quoted \
assertion would let it write to the test rather than to the requirement.
4. Nothing you say in this session is carried forward. Only the handoff artifact is read.
5. Only findings at the severities the repository blocks on cause any further work. \
Everything else is recorded for a human and changes nothing, so severity is a claim \
about consequence, not about how strongly you feel.

Report what you can point at. A finding with a file, a line and a concrete failure \
someone can reproduce is worth more than five observations about style. If the change \
is good, say so and return an empty findings list — an invented blocker costs a real \
session and can park the ticket.\
"""


@dataclass(frozen=True, slots=True)
class ReviewStage:
    """The third stage: judgment, bounded and structured."""

    settings: FluxConfig
    name: str = STAGE_NAME

    # -- inputs ---------------------------------------------------------------

    def hydrate(self, ticket: TicketContext) -> PromptPack:
        """Assemble the pack from disk and from git. Pure: same tree in, same pack out.

        Raises:
            ParkSignal: there is no diff to review. Raised here rather than discovered
                by the session because it costs nothing: a review of an empty change is
                a paid session that can only conclude "nothing happened", and the real
                problem is upstream.
        """
        diff = review_diff(ticket, self.settings)
        if not diff.ok:
            raise ParkSignal(
                f"the review stage could not read this ticket's diff: {diff.detail}",
                reason="diff-unavailable",
            )
        parsed = parse_diff(diff.text)
        if parsed.is_empty:
            raise ParkSignal(
                "there is nothing to review: no file outside the tests changed between "
                f"{diff.base or 'the start of the ticket'} and the working tree",
                reason="empty-diff",
            )
        context = ticket.context_dir
        return PromptPack(
            system_prompt=SYSTEM_PROMPT,
            plan_summary=read_text(context / PLAN_SUMMARY_FILENAME),
            context_pack=join(
                section("Ticket", ticket.brief),
                read_text(context / CONTEXT_PACK_FILENAME),
                self._criteria_section(ticket),
            ),
            stage_tail=join(
                self._diff_section(diff, parsed),
                self._rubric_section(),
                self._output_section(ticket),
            ),
        )

    def _criteria_section(self, ticket: TicketContext) -> str:
        """What the change was supposed to do, from ``tests.json``.

        The criteria are the non-leaky half of the tests artifact: a statement of
        requirements, written before the code, with no test source in it. Without them
        the reviewer would be judging the code only against itself.
        """
        sliced = artifact_slice(
            ticket.context_dir / tests_stage.ARTIFACT_FILENAME, (tests_stage.CASES_KEY,)
        )
        cases = as_json_list(sliced.get(tests_stage.CASES_KEY)) or []
        criteria: list[str] = []
        for entry in cases:
            mapping = as_json_mapping(entry)
            if mapping is not None:
                criterion = str(mapping.get("criterion", "")).strip()
                if criterion and criterion not in criteria:
                    criteria.append(criterion)
        if not criteria:
            return ""
        return section(
            "Acceptance criteria",
            "Each of these has a test behind it, and those tests pass. Judge whether the "
            "code satisfies the criterion, not merely the test.\n\n" + bullets(criteria),
        )

    def _diff_section(self, result: DiffResult, parsed: Diff) -> str:
        body = parsed.render(limit=self.settings.review.max_diff_chars)
        notes = [
            f"{len(parsed.files)} file(s), {parsed.changed_lines} changed line(s), "
            f"from `{result.base}` to the working tree."
        ]
        if result.omitted:
            notes.append(
                f"{len(result.omitted)} new file(s) were left out of this diff: "
                f"{', '.join(result.omitted)}."
            )
        notes.append("Test files are excluded — you may not read them.")
        return section("The change under review", "\n".join(notes) + f"\n\n{body}")

    def _rubric_section(self) -> str:
        return section(
            "Rubric",
            "Judge the change on these axes and tag every finding with the one it came "
            "from:\n\n"
            + bullets(
                (
                    "`correctness` — logic that is wrong on an input the tests do not "
                    "cover: boundaries, empty and error paths, concurrency, resource "
                    "lifetimes.",
                    "`design-fit` — does this fit the plan and the existing code, or does "
                    "it add a second way of doing something the repo already does once?",
                    "`edge-cases` — behaviour nobody specified: what happens on failure, "
                    "on absent input, at the limits.",
                    "`readability` — could the next person change this safely? Names, "
                    "dead code, comments that explain what rather than why.",
                )
            )
            + "\n\nSeverity: `blocker` (it is wrong, or it will break something), "
            "`major` (it will cost someone real time later), `minor` (worth doing), "
            "`nit` (taste). Be honest about the difference — the repository acts on "
            f"{', '.join(self.settings.review.fix_severities)} and only on that.",
        )

    def _output_section(self, ticket: TicketContext) -> str:
        path = ARTIFACT_SPEC.resolve(ticket)
        example = json.dumps(
            {
                SUMMARY_KEY: "one paragraph: what this change does and whether it is sound",
                FINDINGS_KEY: [
                    {
                        "severity": SEVERITIES[0],
                        "axis": AXES[0],
                        "file": "src/example.py",
                        "line": 42,
                        "finding": "what is wrong, and the input on which it goes wrong",
                        "suggestion": "what to do instead",
                    }
                ],
            },
            indent=2,
        )
        return section(
            "Required output",
            f"Write `{path}` as a JSON object of exactly this shape:\n\n"
            f"```json\n{example}\n```\n\n"
            f"`{FINDINGS_KEY}` may be `[]` — say so in the summary if the change is sound. "
            f"`severity` is one of {', '.join(SEVERITIES)}; `axis` is one of "
            f"{', '.join(AXES)}; `file` is a path from the repository root and `line` is a "
            "line in the diff you were shown.",
        )

    # -- policy ---------------------------------------------------------------

    def config(self, ticket: TicketContext) -> ExecConfig:
        """A different model (ADR 0005), no Bash, and two guards.

        No tool permissions are granted: the gates have already run, and a reviewer that
        runs the suite itself is paying to re-learn what is in its own pack. The guards
        are what make "advisory" structural — one confines writing to the handoff
        artifact, the other keeps the tests out of reach.
        """
        return self.settings.profile(self.name).exec_config(
            cwd=ticket.worktree,
            add_dirs=(ticket.context_dir,),
            guards=(
                review_stage_guard(ticket),
                source_stage_guard(ticket, self.settings),
            ),
        )

    def required_artifact(self) -> ArtifactSpec | None:
        return ARTIFACT_SPEC

    def gates(self, ticket: TicketContext) -> Sequence[Gate]:
        """None. The reviewer cannot change the code, so nothing it did can break a gate.

        The suite ran at implement time and runs again after every fix; running it here
        would re-measure an unchanged tree and put a minute on every review pass.
        """
        return ()

    # -- verification ---------------------------------------------------------

    def commit(
        self,
        ticket: TicketContext,
        result: ExecResult,
        gate_results: Sequence[GateOutcome],
    ) -> Outcome:
        """Normalise the findings, and report whether any of them block the ticket.

        The verdict this returns is the one thing in the pipeline a model's *judgement*
        decides, so everything around it is made mechanical: findings are deduped and
        numbered by the runner, and only the configured severities set
        ``open_findings`` — which is what the transition function reads to turn the
        review↔fix loop (design.md §1).
        """
        payload = read_artifact(ticket)
        if payload is None:  # unreachable: the runner validated this file moments ago
            return Outcome(
                ok=False,
                parked=True,
                reason="artifact-invalid",
                note=f"{ARTIFACT_FILENAME} is gone",
            )

        findings = number(sort_findings(dedupe(read_findings(payload))))
        duplicates = len(read_findings(payload)) - len(findings)
        self._record(ticket, payload, findings)

        open_findings = unresolved(findings, self.settings)
        counts = {level: sum(1 for f in findings if f.severity == level) for level in SEVERITIES}
        commit = self._record_commit(ticket)
        summary = ", ".join(f"{n} {level}" for level, n in counts.items() if n) or "no findings"
        return Outcome(
            ok=True,
            open_findings=bool(open_findings),
            note=(
                f"reviewed: {summary}"
                + (f"; {len(open_findings)} to fix" if open_findings else "")
                + (f" ({duplicates} duplicate(s) merged)" if duplicates else "")
            ),
            detail={
                "findings": counts,
                "blocking": [f.id for f in open_findings],
                "duplicates_merged": duplicates,
                "commit": commit,
                "session_id": result.session_id,
            },
        )

    def _record(
        self, ticket: TicketContext, payload: JsonMapping, findings: Sequence[Finding]
    ) -> None:
        """Write the normalised findings back, so the fix stage reads what the runner saw."""
        updated = dict(payload)
        updated[FINDINGS_KEY] = [finding.to_json() for finding in findings]
        write_json_atomic(artifact_path(ticket), updated)

    def _record_commit(self, ticket: TicketContext) -> dict[str, object]:
        if not self.settings.stage_commits:
            return {"committed": False, "skipped": "stage_commits is off"}
        outcome = stage_commit(
            ticket.worktree,
            ticket=ticket.ticket_id,
            stage=self.name,
            message=f"flux({ticket.ticket_id}): {self.name}",
        )
        recorded: dict[str, object] = dict(outcome.to_detail())
        if not outcome.ok:
            recorded["problem"] = outcome.detail
        return recorded


def _rank(severity: str) -> int:
    return SEVERITIES.index(severity) if severity in SEVERITIES else len(SEVERITIES)


def _int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int | str):
        return 0
    try:
        return max(0, int(value))
    except ValueError:
        return 0
