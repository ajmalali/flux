"""The implement stage: make the change, leave a note the next stage can read.

The first stage that runs a real model, and therefore the first place the three
handoff rules meet reality (design.md §2):

* the session is told, explicitly, that nothing it says survives — only ``impl-notes.md``
  does, and the runner checks that file rather than believing the transcript (Rule 1);
* whether the change is any good is decided by gates flux runs itself (Rule 2);
* everything the session knows arrives through :meth:`ImplementStage.hydrate`, which is
  plain code over files (Rule 3).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from flux import knowledge
from flux.config import FluxConfig
from flux.executor.types import ExecConfig, ExecResult, PromptPack
from flux.gates.spec import bash_permissions
from flux.git import head_sha, stage_commit
from flux.metrics.record import GateOutcome
from flux.runner.artifact import ArtifactSpec
from flux.runner.context import TicketContext
from flux.runner.stage import Gate, Outcome
from flux.stages.hydration import artifact_slice, bullets, join, read_text, section

STAGE_NAME = "implement"

NOTES_FILENAME = "impl-notes.md"
CONTEXT_PACK_FILENAME = "context-pack.md"
PLAN_SUMMARY_FILENAME = "plan-summary.md"
TESTS_ARTIFACT_FILENAME = "tests.json"

NOTES_SPEC = ArtifactSpec(
    path=NOTES_FILENAME,
    kind="text",
    required_sections=("Changed", "Deviations", "Discovered work"),
    min_chars=40,
    description=(
        "it is the only thing the next stage reads about what you did: what changed, "
        "where you departed from the plan, and what you found but did not do."
    ),
)

SYSTEM_PROMPT = """\
You are the implement stage of the flux pipeline, working in a checkout of a real \
repository.

Make the change the ticket describes, then write the handoff note. Nothing else.

Three things about this environment are enforced by the harness, not left to your \
judgement:

1. Deterministic gates run after your session ends, and their verdict decides whether \
this stage stands. Your own assessment of the change does not. Run them yourself before \
you finish if you want to know where you are.
2. Nothing you say in this session is carried forward. The next stage starts with an \
empty context and reads only the files you leave behind, so anything worth knowing must \
be written down.
3. The handoff note is checked by the harness after you finish. If it is missing or is \
missing a required heading, the stage is retried once and then parked for a human.

Work only inside the repository you were given. Do not weaken, skip, or delete tests to \
make a gate pass — a gate that passes for that reason is a defect, and it is the one \
thing this pipeline exists to catch.\
"""


@dataclass(frozen=True, slots=True)
class ImplementStage:
    """The M0 pipeline's single stage; the middle stage of the M1 pipeline.

    Holds the repo's :class:`~flux.config.FluxConfig` and nothing else — no per-run
    state, so the same instance drives a ticket across as many resumes as it takes.
    """

    settings: FluxConfig
    """The target repo's ``flux.toml``. Named ``settings`` because ``config`` is the
    protocol's method for this stage's per-call :class:`ExecConfig`."""

    name: str = STAGE_NAME

    # -- inputs ---------------------------------------------------------------

    def hydrate(self, ticket: TicketContext) -> PromptPack:
        """Assemble the pack from disk. Pure: same files in, same pack out."""
        context = ticket.context_dir
        return PromptPack(
            system_prompt=SYSTEM_PROMPT,
            plan_summary=read_text(context / PLAN_SUMMARY_FILENAME),
            context_pack=join(
                section("Ticket", ticket.brief),
                read_text(context / CONTEXT_PACK_FILENAME),
                self._repo_map_section(ticket),
            ),
            stage_tail=join(
                self._tests_section(context),
                self._gates_section(),
                self._output_section(ticket),
            ),
        )

    def _repo_map_section(self, ticket: TicketContext) -> str:
        """The cached repo map, sliced to what a pack can afford (ADR 0009).

        Absent is normal — a repo that has never run ``flux index`` simply gets no
        section. A *stale* map is stated as stale rather than quietly presented as
        current: an out-of-date map that looks authoritative is worse than none
        (plan.md §7, stale context is the dominant residual risk).
        """
        repo_map = knowledge.load(ticket.root)
        if repo_map is None:
            return ""
        body = repo_map.render(limit=self.settings.repo_map.pack_entries)
        if not body:
            return ""
        stale = repo_map.is_stale(head_sha(ticket.worktree))
        caveat = (
            "\n\nThis map was generated at an earlier commit and may not match the "
            "current tree. Verify anything load-bearing before relying on it."
            if stale
            else ""
        )
        return section(
            "Repo map (files ranked by import centrality)",
            f"```\n{body}\n```{caveat}",
        )

    def _tests_section(self, context: Path) -> str:
        """Test *paths* and the red run, never test bodies (design.md stage I/O table)."""
        sliced = artifact_slice(
            context / TESTS_ARTIFACT_FILENAME, ("test_files", "red_output", "cases")
        )
        if not sliced:
            return ""
        return section(
            "Tests already written for this ticket",
            "These tests exist and currently fail. Make them pass by changing the "
            "implementation. Do not edit them.\n\n```json\n"
            + json.dumps(dict(sliced), indent=2)
            + "\n```",
        )

    def _gates_section(self) -> str:
        specs = self.settings.gates
        if not specs:
            return section(
                "Gates",
                "No gates are configured for this repository, so nothing will "
                "independently verify this change. Be correspondingly careful.",
            )
        listed = bullets(f"`{g.name}`: `{' '.join(g.command)}`" for g in specs)
        return section(
            "Gates that will run when you finish",
            f"{listed}\n\nAll of them must pass for this stage to stand.",
        )

    def _output_section(self, ticket: TicketContext) -> str:
        path = NOTES_SPEC.resolve(ticket)
        return section(
            "Required output",
            f"Write `{path}` with exactly these headings:\n\n"
            "- `## Changed` — what you changed and why, file by file.\n"
            "- `## Deviations` — anything you did differently from the ticket, and why. "
            'Write "None" if there were none.\n'
            "- `## Discovered work` — work you found but deliberately did not do, so it "
            'can become a follow-up ticket. Write "None" if there was none.',
        )

    # -- policy ---------------------------------------------------------------

    def config(self, ticket: TicketContext) -> ExecConfig:
        """Model, effort and caps for this stage — always explicit (ADR 0007).

        The gate commands are pre-approved so the session can check its own work: a
        headless session has nobody to answer a permission prompt, and a stage that
        cannot run the gates will reason about them instead of measuring them.
        """
        return self.settings.profile(self.name).exec_config(
            cwd=ticket.worktree,
            allowed_tools=bash_permissions(self.settings.gates),
        )

    def required_artifact(self) -> ArtifactSpec | None:
        return NOTES_SPEC

    def gates(self, ticket: TicketContext) -> Sequence[Gate]:
        return self.settings.build_gates()

    # -- verification ---------------------------------------------------------

    def commit(
        self,
        ticket: TicketContext,
        result: ExecResult,
        gate_results: Sequence[GateOutcome],
    ) -> Outcome:
        """Stand or fall on the gates, then record the work as a tagged commit.

        A failed gate parks rather than retries: at M0 there is no fix stage to route
        to, and re-running the same prompt against the same failure is the definition
        of burning budget for nothing. M1 replaces the park with the review↔fix loop.
        """
        failed = [g for g in gate_results if not g.passed]
        if failed:
            names = ", ".join(g.name for g in failed)
            detail = "; ".join(f"{g.name}: {g.detail}" for g in failed if g.detail)
            return Outcome(
                ok=False,
                parked=True,
                reason="gates-failed",
                note=f"gates failed: {names}" + (f" — {detail}" if detail else ""),
                detail={"failed_gates": [g.name for g in failed]},
            )

        commit = self._record_commit(ticket)
        return Outcome(
            ok=True,
            note="implemented; all gates green",
            detail={
                "gates": [g.name for g in gate_results],
                "commit": commit,
                "session_id": result.session_id,
            },
        )

    def _record_commit(self, ticket: TicketContext) -> dict[str, object]:
        """Commit the stage's work, if the repo is configured for it.

        A failure here is recorded, not raised: the change is already in the worktree
        and the gates already passed, so refusing to proceed over a missing git
        identity would throw away good work for a bookkeeping problem.
        """
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
