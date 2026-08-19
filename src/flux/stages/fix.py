"""The fix stage: resolve the findings that block, and nothing else.

This is the stage that makes the reference-not-paste rule (design.md §2, change-doc B4)
concrete. By the time it runs, four artifacts and a whole diff exist, and the tempting
implementation is to hand it all of them. It gets neither: its pack is the *unresolved
blocking findings* plus *the diff hunks those findings point at*, resolved out of the
diff by ``file:line``. So a ticket with two findings costs two hunks, whatever the size
of the change they sit in — which is the property the pipeline's pack-size invariant
asserts, and the only reason the review↔fix loop does not grow its own context on every
turn.

Three things it inherits rather than re-derives, deliberately:

* the **same guard** as the implement stage — ``source_stage_guard``, unchanged. The
  fix stage is the second place a session is told "make the gate go green", so it is the
  second place where editing a test is the cheapest way to comply;
* the **same digest backstop** — every test file is re-hashed afterwards, catching the
  routes a ``PreToolUse`` hook cannot see;
* the **same gate suite**, held-out tests included, because "the reviewer is re-invoked
  only if gates pass" is only true if the gates actually ran again.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass

from flux.config import FluxConfig
from flux.diff import HunkRef, select_hunks
from flux.diff import parse as parse_diff
from flux.errors import ParkSignal
from flux.executor.types import ExecConfig, ExecResult, PromptPack
from flux.gates.spec import bash_permissions
from flux.git import stage_commit
from flux.jsonio import JsonMapping, as_json_list, as_json_mapping
from flux.metrics.record import GateOutcome
from flux.runner.artifact import ArtifactSpec
from flux.runner.context import TicketContext
from flux.runner.stage import Gate, Outcome
from flux.stages import review as review_stage
from flux.stages import tests as tests_stage
from flux.stages.guards import source_stage_guard
from flux.stages.hydration import join, read_text, section
from flux.stages.implement import held_out_gate
from flux.stages.review import Finding

STAGE_NAME = "fix"

PLAN_SUMMARY_FILENAME = "plan-summary.md"

SYSTEM_PROMPT = """\
You are the fix stage of the flux pipeline, working in a checkout of a real repository.

A reviewer running a different model read this ticket's change and raised the findings \
below. Resolve them, then record what you did. Nothing else — this is not a second \
implementation pass, and work you were not asked for is work nobody reviewed.

Four things about this environment are enforced by the harness, not left to your \
judgement:

1. The full gate suite runs again when your session ends, and its verdict decides \
whether this stage stands. Run the gates yourself before you finish.
2. You cannot read or change the tests. Every test file is re-hashed after your session, \
so a test that changed by any route at all fails this stage. A finding is about the \
code; fix the code.
3. Every blocking finding must come back marked resolved, with one line saying what you \
changed. The harness checks the file, not the transcript.
4. The reviewer runs again after you and does not read this file — it re-reads the code. \
So marking a finding resolved without changing anything does not end the loop, it \
spends another pass of it, and the ticket parks when the passes run out.

If a finding is wrong, say so in its resolution and leave the code alone. A disputed \
finding that the next review pass does not raise again is settled; one it raises again \
is a disagreement for a human, which is what parking is for.\
"""


def resolution_check(settings: FluxConfig) -> ArtifactSpec:
    """The artifact contract for *this* repo's blocking severities.

    Built per call rather than declared as a constant because what counts as resolved
    depends on ``[review] fix_severities``: the spec has to know which findings the
    stage was actually asked to fix, and reading that from config at validation time
    keeps a repo that blocks on majors from being validated against blockers only.
    """

    def check(payload: JsonMapping) -> str:
        entries = as_json_list(payload.get(review_stage.FINDINGS_KEY))
        if entries is None:
            return f"{review_stage.FINDINGS_KEY!r} must still be a list of findings"
        outstanding: list[str] = []
        for entry in entries:
            mapping = as_json_mapping(entry)
            if mapping is None:
                return f"every {review_stage.FINDINGS_KEY!r} entry must be an object"
            finding = Finding.from_json(mapping)
            if not settings.review.blocks(finding.severity):
                continue
            if not finding.resolved or not finding.resolution:
                outstanding.append(finding.id or finding.location)
        if outstanding:
            return (
                f"{len(outstanding)} finding(s) are not resolved: {', '.join(outstanding)} — "
                'each needs "resolved": true and a "resolution" saying what you changed'
            )
        return ""

    return ArtifactSpec(
        path=review_stage.ARTIFACT_FILENAME,
        kind="json",
        required_keys=(review_stage.FINDINGS_KEY,),
        check=check,
        description=(
            "it is the reviewer's finding list, and you resolve findings by editing it "
            "in place: set 'resolved' to true and write a one-line 'resolution' on each."
        ),
    )


@dataclass(frozen=True, slots=True)
class FixStage:
    """The fourth stage, and the only one the transition function reaches non-linearly."""

    settings: FluxConfig
    name: str = STAGE_NAME

    # -- inputs ---------------------------------------------------------------

    def hydrate(self, ticket: TicketContext) -> PromptPack:
        """Findings and their hunks. Not the diff, not the notes, not the tests.

        Raises:
            ParkSignal: there is nothing to fix. The transition function only routes
                here when the review left findings open, so an empty list means the
                artifact changed underneath the runner — spending a session to discover
                that would tell nobody anything.
        """
        findings = self._open_findings(ticket)
        if not findings:
            raise ParkSignal(
                f"the fix stage was reached with no unresolved findings in "
                f"{review_stage.ARTIFACT_FILENAME}",
                reason="nothing-to-fix",
            )
        hunks = self._hunks(ticket, findings)
        return PromptPack(
            system_prompt=SYSTEM_PROMPT,
            plan_summary=read_text(ticket.context_dir / PLAN_SUMMARY_FILENAME),
            context_pack=section("Ticket", ticket.brief),
            stage_tail=join(
                self._findings_section(findings),
                self._hunks_section(hunks),
                self._gates_section(),
                self._output_section(ticket, findings),
            ),
        )

    def _open_findings(self, ticket: TicketContext) -> tuple[Finding, ...]:
        payload = review_stage.read_artifact(ticket)
        if payload is None:
            return ()
        return review_stage.unresolved(review_stage.read_findings(payload), self.settings)

    def _hunks(self, ticket: TicketContext, findings: Sequence[Finding]) -> tuple[HunkRef, ...]:
        """The slices of the diff the findings point at — the whole of the code context.

        A finding whose line falls outside every changed hunk still earns a line saying
        so: "the reviewer pointed at unchanged code" is information, and silence there
        would read as "that file was not part of this ticket".
        """
        result = review_stage.review_diff(ticket, self.settings)
        if not result.ok:
            return ()
        diff = parse_diff(result.text)
        refs = select_hunks(diff, ((f.file, f.line) for f in findings))
        return refs[: self.settings.review.max_hunks]

    def _findings_section(self, findings: Sequence[Finding]) -> str:
        blocks = [
            join(
                f"### {f.id} — {f.severity} · {f.axis or 'unaxed'} · {f.location}",
                f.finding,
                f"Suggested: {f.suggestion}" if f.suggestion else "",
            )
            for f in findings
        ]
        return section(
            f"Findings to resolve ({len(findings)})",
            "\n\n".join(blocks),
        )

    def _hunks_section(self, hunks: Sequence[HunkRef]) -> str:
        if not hunks:
            return ""
        return section(
            "The code those findings point at",
            "Only the changed hunks the findings name are shown. Read the surrounding "
            "file if you need more; test files are out of reach.\n\n"
            + "\n\n".join(ref.render() for ref in hunks),
        )

    def _gates_section(self) -> str:
        specs = self.settings.gates
        if not specs:
            return ""
        listed = "\n".join(f"- `{g.name}`: `{' '.join(g.command)}`" for g in specs)
        return section(
            "Gates that will run when you finish",
            f"{listed}\n\nAll of them must pass for this stage to stand. They passed "
            "before your session started, so a gate that fails afterwards is something "
            "you did.",
        )

    def _output_section(self, ticket: TicketContext, findings: Sequence[Finding]) -> str:
        path = review_stage.artifact_path(ticket)
        example = json.dumps(
            {
                review_stage.FINDINGS_KEY: [
                    {
                        "id": findings[0].id,
                        "resolved": True,
                        "resolution": "what you changed, in one line",
                    }
                ]
            },
            indent=2,
        )
        return section(
            "Required output",
            f"Edit `{path}` in place. Every finding listed above must end up with "
            f'`"resolved": true` and a non-empty `"resolution"`. Leave every other field '
            f"of every finding exactly as it is — the file is the reviewer's, and you are "
            f"annotating it:\n\n```json\n{example}\n```",
        )

    # -- policy ---------------------------------------------------------------

    def config(self, ticket: TicketContext) -> ExecConfig:
        """Identical policy to the implement stage, by construction rather than by copy.

        The same guard object, the same gate pre-approval, the same granted context
        directory. Anywhere these two stages differ is somewhere a session that could
        not game the implement stage could game this one.
        """
        return self.settings.profile(self.name).exec_config(
            cwd=ticket.worktree,
            allowed_tools=bash_permissions(self.settings.gates),
            add_dirs=(ticket.context_dir,),
            guards=(source_stage_guard(ticket, self.settings),),
        )

    def required_artifact(self) -> ArtifactSpec | None:
        return resolution_check(self.settings)

    def gates(self, ticket: TicketContext) -> Sequence[Gate]:
        """The full suite again, held-out tests included (design.md stage I/O table)."""
        suite = self.settings.build_gates()
        gate = held_out_gate(ticket, self.settings)
        return suite if gate is None else (*suite, gate)

    # -- verification ---------------------------------------------------------

    def commit(
        self,
        ticket: TicketContext,
        result: ExecResult,
        gate_results: Sequence[GateOutcome],
    ) -> Outcome:
        """Stand only if the tests are untouched and every gate is green.

        Order matters: the digest check runs *first*, because a suite that went green
        after a test file changed is not evidence about the code, and reporting the
        gates as passed before saying so would bury the finding under good news.
        """
        edited = tests_stage.modified_tests(ticket)
        if edited:
            return Outcome(
                ok=False,
                parked=True,
                reason="tests-modified",
                note=(
                    "test files changed during the fix stage: "
                    f"{', '.join(edited)}. The tests are this ticket's specification, so a "
                    "change to them invalidates every gate that ran afterwards."
                ),
                detail={"modified_tests": list(edited)},
            )

        failed = [g for g in gate_results if not g.passed]
        if failed:
            names = ", ".join(g.name for g in failed)
            detail = "; ".join(f"{g.name}: {g.detail}" for g in failed if g.detail)
            return Outcome(
                ok=False,
                parked=True,
                reason="gates-failed",
                note=f"gates failed after the fix: {names}" + (f" — {detail}" if detail else ""),
                detail={"failed_gates": [g.name for g in failed]},
            )

        resolved = self._resolutions(ticket)
        commit = self._record_commit(ticket)
        return Outcome(
            ok=True,
            # The reviewer decides whether the findings are really closed; this only
            # records that the fixer says they are. `_apply_outcome` clears the review
            # checkpoint on the way out, so the next pass re-reads the code, not this.
            open_findings=False,
            note=f"{len(resolved)} finding(s) resolved; all gates green",
            detail={
                "resolved": [f.id for f in resolved],
                "gates": [g.name for g in gate_results],
                "commit": commit,
                "session_id": result.session_id,
            },
        )

    def _resolutions(self, ticket: TicketContext) -> tuple[Finding, ...]:
        payload = review_stage.read_artifact(ticket)
        if payload is None:
            return ()
        findings = review_stage.read_findings(payload)
        return tuple(f for f in review_stage.blocking(findings, self.settings) if f.resolved)

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
