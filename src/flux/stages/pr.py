"""The pr stage: write the pull request, and let the runner land the plane.

The last stage, and the only one whose work leaves the machine. That is what shapes it:
the split between what the session does and what the runner does is drawn much further
towards the runner here than anywhere else in the pipeline.

* The **session** writes prose. It reads the impl notes, the resolved review and the
  commit log, and produces ``pr.md`` — a title and a body. It has no Bash, cannot edit
  the repository, and never runs git.
* The **runner** does everything that is a fact. It runs the gate suite one last time on
  the exact tree it is about to push, pushes ``HEAD`` by refspec, re-reads the ref from
  the remote to confirm the sha, and opens the pull request itself. Every claim in the
  checkpoint is therefore something flux observed.

design.md's stage I/O table says the pr stage's ``commit()`` verifies "``git push``
succeeded; CI triggered". The first half is verified here against the remote rather than
against git's exit status. The second half is *not* claimed: whether a push triggered CI
is a property of the forge's configuration, and flux has no way to observe it that does
not amount to polling a provider it does not know about. What flux can say — the branch
exists on the remote at this sha, and this suite was green on it — it says, and it says
nothing else.

Three refusals, all in :class:`~flux.config.PrConfig` and all deliberate:

* **never a protected branch.** Work done on ``main`` is pushed to ``flux/<ticket>``
  instead. HEAD goes somewhere safe rather than the ticket parking with every stage but
  the last one successful.
* **never ``--force``.** A remote branch that already exists and does not contain this
  work is a collision for a human.
* **drafts by default.** An unattended harness asking for review is asking a person for
  their time; a draft asks without also claiming the work is ready.
"""

from __future__ import annotations

import shutil
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from flux.config import FluxConfig
from flux.diff import parse as parse_diff
from flux.errors import ParkSignal
from flux.executor.types import ExecConfig, ExecResult, PromptPack
from flux.git import (
    PushResult,
    current_branch,
    default_branch,
    push_head,
    remotes,
    stage_commit,
    ticket_log,
)
from flux.metrics.record import GateOutcome
from flux.proc import CommandRun, clean_env, run_command, tail
from flux.runner.artifact import ArtifactSpec
from flux.runner.context import TicketContext
from flux.runner.stage import Gate, Outcome
from flux.stages import review as review_stage
from flux.stages.guards import pr_stage_guard, source_stage_guard
from flux.stages.hydration import bullets, join, read_text, section
from flux.stages.implement import NOTES_FILENAME, held_out_gate
from flux.stages.review import Finding

STAGE_NAME = "pr"

ARTIFACT_FILENAME = "pr.md"
PLAN_SUMMARY_FILENAME = "plan-summary.md"

TITLE_SECTION = "Title"
BODY_SECTIONS: tuple[str, ...] = ("Summary", "Changes", "Review", "Risk")
"""The headings the body is assembled from, in the order a reader wants them.

Split from the title because a pull request is two fields, not one document, and
asking for them as one would make flux guess which line was which.
"""

MAX_TITLE_CHARS = 72

GH_TIMEOUT_S = 120


def artifact_path(ticket: TicketContext) -> Path:
    return ticket.context_dir / ARTIFACT_FILENAME


ARTIFACT_SPEC = ArtifactSpec(
    path=ARTIFACT_FILENAME,
    kind="text",
    required_sections=(TITLE_SECTION, *BODY_SECTIONS),
    min_chars=80,
    description=(
        "it is the pull request itself: a one-line title and the body a reviewer reads "
        "before anything else. Nothing you say outside it is published."
    ),
)

SYSTEM_PROMPT = """\
You are the pr stage of the flux pipeline. The work is done, the gates are green, and \
your job is to describe it to the person who has to review it.

Write the pull request. Nothing else — this is not a last chance to improve the change.

Four things about this environment are enforced by the harness, not left to your \
judgement:

1. You cannot edit the repository. The gates have already passed on this exact tree and \
it is what will be pushed, so a change here would mean the branch that lands is not the \
branch that was verified.
2. You do not push anything and you do not open the pull request. The harness does both, \
after your session, and records what the remote actually says rather than what anything \
claims. Do not write as though you had run git.
3. Nothing you say in this session is carried forward. Only the handoff artifact is read.
4. What you were given is what there is: the implementation notes, the review and its \
resolutions, and the commit log. Do not invent test names, issue numbers, benchmarks or \
migration steps that are not in your context.

Write for someone who has not read the ticket. Say what changed and why it was worth \
changing, be specific about the risk, and be brief — a reviewer who has to skim a long \
pull request description reads none of it.\
"""


@dataclass(frozen=True, slots=True)
class PullRequest:
    """A pull request as ``pr.md`` describes it: a title and an assembled body."""

    title: str
    body: str

    @property
    def ok(self) -> bool:
        return bool(self.title and self.body)


def parse_artifact(text: str) -> PullRequest:
    """Split ``pr.md`` into the two fields a forge actually takes.

    The artifact is markdown with known headings because that is what the runner can
    check before paying for a retry; a pull request is a title string and a body string.
    This is the conversion, and it is deliberately forgiving about everything except the
    two facts that matter — the title is one line, and the body is the rest.
    """
    sections = _sections(text)
    title = " ".join(sections.get(TITLE_SECTION, "").split())
    if title.startswith("#"):  # a heading written where a line of text was asked for
        title = title.lstrip("#").strip()
    title = title[:MAX_TITLE_CHARS].rstrip()
    body = "\n\n".join(
        f"## {name}\n\n{sections[name].strip()}"
        for name in BODY_SECTIONS
        if sections.get(name, "").strip()
    )
    return PullRequest(title=title, body=body)


def _sections(text: str) -> dict[str, str]:
    """``{heading: body}`` for the headings this artifact declares, and only those.

    Splitting on *every* ``#`` line would be the obvious implementation and the wrong
    one twice over: a sub-heading inside ``## Changes`` would end the section it belongs
    to, and a title written as ``# Add the thing`` under ``## Title`` would become a
    section of its own rather than the title. Matching the declared names is also what
    the runner's own artifact check does, so a file that validates parses.
    """
    known = {name.lower(): name for name in (TITLE_SECTION, *BODY_SECTIONS)}
    found: dict[str, list[str]] = {}
    current = ""
    for line in text.splitlines():
        stripped = line.strip()
        heading = known.get(stripped.lstrip("#").strip().lower(), "")
        if stripped.startswith("#") and heading:
            current = heading
            found.setdefault(current, [])
            continue
        if current:
            found[current].append(line)
    return {name: "\n".join(lines).strip() for name, lines in found.items()}


def provenance(
    ticket: TicketContext,
    *,
    gates: Sequence[GateOutcome],
    commits: Sequence[str],
) -> str:
    """The footer flux writes onto every body it publishes — facts, not prose.

    Appended by the runner rather than asked of the session on purpose: this is the
    part of a pull request description a reviewer is entitled to trust, so it must come
    from what flux measured. A session that wrote "all gates pass" would be making
    exactly the kind of claim the rest of the pipeline exists to stop believing.
    """
    lines = [
        "---",
        f"Generated by flux for ticket `{ticket.ticket_id}`.",
    ]
    if gates:
        verdicts = ", ".join(f"{g.name} {'pass' if g.passed else 'FAIL'}" for g in gates)
        lines.append(f"Gates on the pushed tree: {verdicts}.")
    else:
        lines.append("No gates are configured for this repository — nothing verified this.")
    if commits:
        lines.append(f"{len(commits)} commit(s): {', '.join(c.split(' ')[0] for c in commits)}.")
    return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class PrStage:
    """The fifth stage: describe the change, then land it."""

    settings: FluxConfig
    name: str = STAGE_NAME

    # -- inputs ---------------------------------------------------------------

    def hydrate(self, ticket: TicketContext) -> PromptPack:
        """Notes, resolved review and commit log — the three things design.md names.

        Not the diff. The change has already been read closely by a reviewer running a
        larger model, and this stage runs Haiku at low effort to write four paragraphs;
        handing it the whole diff would cost more than the stage does and would tempt it
        into re-reviewing rather than describing.

        Raises:
            ParkSignal: nothing was committed under this ticket's tags, so there is no
                branch to open a pull request for. The stage would be describing a
                change that does not exist as commits.
        """
        commits = ticket_log(ticket.worktree, ticket=ticket.ticket_id)
        if self.settings.pr.push and not commits:
            raise ParkSignal(
                "this ticket has no stage commits, so there is nothing to push: the work "
                "is in the working tree only",
                reason="nothing-to-push",
            )
        context = ticket.context_dir
        return PromptPack(
            system_prompt=SYSTEM_PROMPT,
            plan_summary=read_text(context / PLAN_SUMMARY_FILENAME),
            context_pack=join(
                section("Ticket", ticket.brief),
                section("Implementation notes", read_text(context / NOTES_FILENAME)),
            ),
            stage_tail=join(
                self._review_section(ticket),
                self._commits_section(ticket, commits),
                self._output_section(ticket),
            ),
        )

    def _review_section(self, ticket: TicketContext) -> str:
        """What the reviewer raised and what the fix stage did about it.

        Resolutions are included because they are the half a human reviewer most wants
        and is least able to reconstruct: "a blocker was raised here and this is what
        changed" is the pull request's most useful paragraph. Findings still open are
        listed as open — a ticket only reaches this stage with open findings when a
        human accepted them, and saying so is more honest than omitting them.
        """
        payload = review_stage.read_artifact(ticket)
        if payload is None:
            return ""
        findings = review_stage.read_findings(payload)
        summary = str(payload.get(review_stage.SUMMARY_KEY, "")).strip()
        if not findings:
            return section(
                "The review",
                (summary + "\n\n" if summary else "")
                + "The reviewer raised no findings on this change.",
            )
        return section(
            "The review",
            (summary + "\n\n" if summary else "") + bullets(_finding_line(f) for f in findings),
        )

    def _commits_section(self, ticket: TicketContext, commits: Sequence[str]) -> str:
        """The commit log, plus a file-level shape of the change. Never the diff itself."""
        diff = review_stage.review_diff(ticket, self.settings)
        parts: list[str] = []
        if commits:
            parts.append("Commits on this branch, oldest first:\n\n" + bullets(commits))
        if diff.ok:
            parsed = parse_diff(diff.text)
            files = [
                f"`{path}` ({file.changed_lines} changed line(s))"
                for path in parsed.paths
                if (file := parsed.file(path)) is not None
            ]
            if files:
                parts.append(
                    f"{len(files)} file(s) changed, {parsed.changed_lines} line(s) in total "
                    "(test files excluded):\n\n" + bullets(files)
                )
        return section("What was committed", "\n\n".join(parts))

    def _output_section(self, ticket: TicketContext) -> str:
        path = ARTIFACT_SPEC.resolve(ticket)
        return section(
            "Required output",
            f"Write `{path}` with exactly these headings:\n\n"
            + bullets(
                (
                    f"`## {TITLE_SECTION}` — one line, imperative mood, at most "
                    f"{MAX_TITLE_CHARS} characters. No trailing full stop, no ticket id "
                    "(the harness adds provenance itself).",
                    "`## Summary` — two to four sentences: what changed and why.",
                    "`## Changes` — a short bullet list, one per meaningful change. "
                    "Group by intent rather than by file.",
                    "`## Review` — what the reviewer raised and how it was resolved. "
                    'Write "None" if the review was clean.',
                    "`## Risk` — what could go wrong and what a reviewer should look at "
                    'hardest. Write "None" only if you genuinely mean it.',
                )
            )
            + "\n\nThe harness appends a footer recording the gate results and the "
            "commits, so do not write one.",
        )

    # -- policy ---------------------------------------------------------------

    def config(self, ticket: TicketContext) -> ExecConfig:
        """Haiku at low effort, no tools, two guards (plan.md §3 routing table).

        No Bash is granted, and that is the load-bearing part rather than an economy:
        the stage's whole contract is that it does not touch the remote. A session with
        ``git`` could push, and then "the runner verified the push" would be a claim
        about which process ran a command rather than a property of the design.
        """
        return self.settings.profile(self.name).exec_config(
            cwd=ticket.worktree,
            add_dirs=(ticket.context_dir,),
            guards=(
                pr_stage_guard(ticket),
                source_stage_guard(ticket, self.settings),
            ),
        )

    def required_artifact(self) -> ArtifactSpec | None:
        return ARTIFACT_SPEC

    def gates(self, ticket: TicketContext) -> Sequence[Gate]:
        """The full suite, one last time, on the tree about to be pushed.

        The tree has not changed since the fix or implement stage passed it, so this
        re-measures something already measured — deliberately. A green suite recorded
        against the exact sha that lands is the difference between a pull request that
        says the gates passed and one that proves it, and it is the cheapest evidence
        in the pipeline: no session, no tokens, one run of a suite that is already fast
        enough to be a gate.
        """
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
        """Commit the body, push the branch, and confirm the remote holds it.

        Order is the argument. The gates are checked before anything leaves the machine,
        the body is committed before the push so the branch carries it, and the push is
        verified by re-reading the ref rather than by trusting an exit status.
        """
        failed = [g for g in gate_results if not g.passed]
        if failed:
            names = ", ".join(g.name for g in failed)
            detail = "; ".join(f"{g.name}: {g.detail}" for g in failed if g.detail)
            return Outcome(
                ok=False,
                parked=True,
                reason="gates-failed",
                note=(
                    f"gates failed on the tree the pr stage was about to push: {names}"
                    + (f" — {detail}" if detail else "")
                ),
                detail={"failed_gates": [g.name for g in failed]},
            )

        pull = parse_artifact(read_text(artifact_path(ticket)))
        if not pull.ok:
            return Outcome(
                ok=False,
                parked=True,
                reason="artifact-invalid",
                note=f"{ARTIFACT_FILENAME} has no usable title or body after parsing",
            )

        commits = ticket_log(ticket.worktree, ticket=ticket.ticket_id)
        body = f"{pull.body}\n\n{provenance(ticket, gates=gate_results, commits=commits)}\n"
        commit = self._record_commit(ticket)

        if not self.settings.pr.push:
            return Outcome(
                ok=True,
                note=f"pull request body written ({pull.title!r}); [pr] push is off",
                detail={"title": pull.title, "pushed": False, "commit": commit},
            )

        target = self._target_branch(ticket)
        if target.problem:
            return Outcome(
                ok=False,
                parked=True,
                reason=target.reason,
                note=target.problem,
                detail={"title": pull.title, "commit": commit},
            )

        push = push_head(ticket.worktree, remote=self.settings.pr.remote, branch=target.branch)
        if not push.ok:
            return Outcome(
                ok=False,
                parked=True,
                reason="push-failed",
                note=f"the branch was not pushed: {push.detail}",
                detail={"title": pull.title, "commit": commit, **push.to_detail()},
            )

        opened = self._open_pull_request(ticket, pull.title, body, push)
        if opened.problem and self.settings.pr.create == "always":
            return Outcome(
                ok=False,
                parked=True,
                reason="pr-not-opened",
                note=(
                    f"{push.remote}/{push.branch} is at {push.sha[:8]}, but the pull "
                    f"request could not be opened: {opened.problem}"
                ),
                detail={"title": pull.title, "commit": commit, **push.to_detail()},
            )
        return Outcome(
            ok=True,
            note=(
                f"pushed {push.sha[:8]} to {push.remote}/{push.branch}"
                + (f"; {opened.url}" if opened.url else f"; {opened.problem or 'no pull request'}")
            ),
            detail={
                "title": pull.title,
                "commit": commit,
                "session_id": result.session_id,
                "gates": [g.name for g in gate_results],
                **push.to_detail(),
                "pr_url": opened.url,
                "pr_problem": opened.problem,
            },
        )

    # -- where it lands -------------------------------------------------------

    def _target_branch(self, ticket: TicketContext) -> _Target:
        """The branch to push to, or why there is none.

        A protected branch is not an error: the ticket's work is real and has passed
        every gate, so it is redirected to ``<branch_prefix><ticket>`` rather than
        thrown away. A missing remote *is* an error, on ADR 0005's rule that a check
        which cannot run has failed — with nowhere to land, "completed" would be a
        false verdict, and ``[pr] push = false`` is how a repo says it means that.
        """
        configured = self.settings.pr
        if configured.remote not in remotes(ticket.worktree):
            return _Target(
                problem=(
                    f"this repository has no remote named {configured.remote!r}, so the "
                    "branch cannot be pushed. Add one, or set `[pr] push = false` if this "
                    "repository does not land anywhere."
                ),
                reason="no-remote",
            )
        branch = current_branch(ticket.worktree)
        if not branch or configured.protects(branch):
            return _Target(branch=f"{configured.branch_prefix}{ticket.ticket_id}")
        return _Target(branch=branch)

    def _open_pull_request(
        self, ticket: TicketContext, title: str, body: str, push: PushResult
    ) -> _Opened:
        """Ask ``gh`` to open the pull request, and report honestly if it cannot.

        ``gh`` is used rather than an API call because it already holds the user's
        credentials, which is the same reason flux runs on the logged-in subscription
        (ADR 0010): flux does not want to be told a token. A repository whose forge
        ``gh`` does not speak simply gets a pushed branch and a body on disk, which is
        the greater part of the job.
        """
        if self.settings.pr.create == "never":
            return _Opened(problem="[pr] create is 'never'")
        if shutil.which("gh") is None:
            return _Opened(problem="gh is not on PATH, so no pull request was opened")

        base = self.settings.pr.base or default_branch(ticket.worktree, push.remote)
        if not base:
            return _Opened(
                problem=(f"could not tell which branch {push.remote} defaults to; set `[pr] base`")
            )
        if base == push.branch:
            return _Opened(problem=f"the branch pushed is {base!r}, which is its own base")

        body_file = ticket.context_dir / "pr-body.md"
        body_file.write_text(body, encoding="utf-8")
        argv = [
            "gh",
            "pr",
            "create",
            "--base",
            base,
            "--head",
            push.branch,
            "--title",
            title,
            "--body-file",
            str(body_file),
        ]
        if self.settings.pr.draft:
            argv.append("--draft")
        run = run_command(argv, cwd=ticket.worktree, timeout_s=GH_TIMEOUT_S, env=clean_env())
        if run.returncode != 0:
            return _Opened(problem=_why(run))
        url = next(
            (line.strip() for line in run.stdout.splitlines() if line.strip().startswith("http")),
            "",
        )
        return _Opened(url=url, problem="" if url else "gh printed no pull request url")

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


@dataclass(frozen=True, slots=True)
class _Target:
    """Where this ticket's work is to be pushed, or why it is not."""

    branch: str = ""
    problem: str = ""
    reason: str = "unspecified"


@dataclass(frozen=True, slots=True)
class _Opened:
    """What came of asking the forge for a pull request."""

    url: str = ""
    problem: str = ""


def _finding_line(finding: Finding) -> str:
    state = f"resolved — {finding.resolution}" if finding.resolved else "still open"
    return f"`{finding.severity}` {finding.location}: {finding.finding} ({state})"


def _why(run: CommandRun) -> str:
    if not run.launched:
        return f"gh could not run: {run.fault}"
    if run.timed_out:
        return f"gh timed out after {GH_TIMEOUT_S}s"
    return f"gh exited {run.returncode}: {tail(run.output, lines=3, limit=400)}"
