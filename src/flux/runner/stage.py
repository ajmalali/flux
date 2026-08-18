"""The contracts the runner drives: :class:`Stage`, :class:`Gate`, :class:`Outcome`.

These live in ``runner/`` rather than ``stages/`` on purpose: they are what the loop
depends on, and the concrete stages (M1) and gates (T4) depend on them in turn. A
stage never imports the SDK — it composes a :class:`~flux.executor.types.PromptPack`
and an :class:`~flux.executor.types.ExecConfig` and hands them back (ADR 0007).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Protocol

from flux.executor.types import ExecConfig, ExecResult, PromptPack
from flux.metrics.record import GateOutcome
from flux.runner.artifact import ArtifactSpec
from flux.runner.context import TicketContext

_NO_DETAIL: Mapping[str, Any] = MappingProxyType({})


class Gate(Protocol):
    """A deterministic post-check the runner executes itself (ADR 0005).

    Gates are subprocesses, not judgments: lint, typecheck, tests, coverage. Their
    verdicts are evidence the runner observed, never something read out of a transcript.
    """

    name: str

    def run(self, worktree: Path) -> GateOutcome: ...


@dataclass(frozen=True, slots=True)
class Outcome:
    """What a stage's ``commit()`` concluded, after seeing gates and the session result."""

    ok: bool = True
    """False means the stage ran but did not achieve its goal (e.g. a gate failed)."""

    parked: bool = False
    note: str = ""
    """Human-readable reason, written verbatim into the park note."""

    reason: str = "unspecified"
    """Short slug for grouping parks in triage."""

    open_findings: bool | None = None
    """Review-loop signal: does unresolved work remain?

    Only the review stage sets this; it is derived from ``review.json``, so the
    artifact stays the source of truth and the runner stays generic. ``None`` leaves
    the previous value alone.
    """

    detail: Mapping[str, Any] = _NO_DETAIL
    """Stage-specific facts to persist in the checkpoint. Must be JSON-serialisable."""


class Stage(Protocol):
    """One pipeline step. Five of these make the pipeline (design.md stage I/O table).

    The split exists so that everything except ``run()`` is testable without a model:
    ``hydrate`` is pure code over disk, ``gates`` are subprocesses, and ``commit`` is
    the runner's own verification of what came back.
    """

    name: str

    def hydrate(self, ticket: TicketContext) -> PromptPack:
        """Assemble the prompt pack from artifacts on disk. Deterministic (design.md §2)."""
        ...

    def config(self, ticket: TicketContext) -> ExecConfig:
        """Model, effort, permissions and caps for this stage's session."""
        ...

    def required_artifact(self) -> ArtifactSpec | None:
        """The artifact the stage must leave behind, or ``None`` if it produces none."""
        ...

    def gates(self, ticket: TicketContext) -> Sequence[Gate]:
        """Deterministic checks to run after the session, before ``commit``."""
        ...

    def commit(
        self,
        ticket: TicketContext,
        result: ExecResult,
        gate_results: Sequence[GateOutcome],
    ) -> Outcome:
        """Verify the stage's own evidence and decide whether it stands.

        This is where Rule 2 lives (design.md §2): a stage that claims something the
        runner can check — tests are red, findings are resolved — checks it here by
        running the check itself, not by believing the transcript.
        """
        ...
