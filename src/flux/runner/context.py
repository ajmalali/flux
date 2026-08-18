"""The per-ticket handle the runner and stages are given (design.md §1).

A :class:`TicketContext` is pure addressing plus policy: where this ticket's
artifacts, checkpoints and worktree live, and how many times the loop may go round.
It deliberately holds no stage output — every stage reads what it needs from disk, so
a fresh process reconstructs the identical context.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from flux.errors import ConfigError

FLUX_DIRNAME = ".flux"
CONTEXT_DIRNAME = "context"
STATE_DIRNAME = "state"
METRICS_RELPATH = Path("usage") / "metrics.jsonl"

# Ticket ids become path components, so they are restricted to what is safe there.
_TICKET_ID_RE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]*\Z")


def validate_ticket_id(ticket_id: str) -> str:
    """Return ``ticket_id`` if it is safe to use as a path component, else raise.

    Ticket ids come from outside flux and are turned straight into directory names,
    so this runs before any path is *built* from one, not merely before it is used.
    """
    if not _TICKET_ID_RE.match(ticket_id):
        raise ConfigError(
            f"ticket id {ticket_id!r} is not a safe path component "
            "(expected letters, digits, '.', '_' or '-', starting alphanumeric)"
        )
    return ticket_id


@dataclass(frozen=True, slots=True)
class RunnerConfig:
    """Loop bounds. Every one of these exists to make non-termination impossible."""

    max_review_iters: int = 3
    """Review passes allowed before the ticket parks for human triage (design.md §1)."""

    artifact_retries: int = 1
    """Extra attempts after a required artifact fails validation. Design fixes this at 1."""

    max_stage_runs: int = 40
    """Total stage invocations per ticket, across resumes.

    Backstop only: the transition function is already bounded. This catches a stage
    that completes without ever writing a checkpoint, which would otherwise spin.
    """

    def __post_init__(self) -> None:
        if self.max_review_iters <= 0:
            raise ConfigError(
                f"RunnerConfig.max_review_iters must be positive, got {self.max_review_iters}"
            )
        if self.artifact_retries < 0:
            raise ConfigError(
                f"RunnerConfig.artifact_retries must not be negative, got {self.artifact_retries}"
            )
        if self.max_stage_runs <= 0:
            raise ConfigError(
                f"RunnerConfig.max_stage_runs must be positive, got {self.max_stage_runs}"
            )


DEFAULT_RUNNER_CONFIG = RunnerConfig()


@dataclass(frozen=True, slots=True)
class TicketContext:
    """Everything a stage needs to locate its inputs and outputs."""

    ticket_id: str
    root: Path
    """Absolute path to the repo flux is operating on."""

    worktree: Path = field(default=Path())
    """Where gates and edits happen. Defaults to :attr:`root`; M5 gives each ticket its own."""

    brief: str = ""
    """The ticket's human-written statement of work. Filled from ``bd show`` at M4."""

    config: RunnerConfig = DEFAULT_RUNNER_CONFIG

    def __post_init__(self) -> None:
        validate_ticket_id(self.ticket_id)
        if not self.root.is_absolute():
            raise ConfigError(f"TicketContext.root must be an absolute path, got {self.root}")
        if self.worktree == Path():
            object.__setattr__(self, "worktree", self.root)
        elif not self.worktree.is_absolute():
            raise ConfigError(
                f"TicketContext.worktree must be an absolute path, got {self.worktree}"
            )

    @property
    def flux_dir(self) -> Path:
        """The single namespace all flux artifacts live under (ADR 0006)."""
        return self.root / FLUX_DIRNAME

    @property
    def context_dir(self) -> Path:
        """Handoff artifacts — the interface between stages. Committed."""
        return self.flux_dir / CONTEXT_DIRNAME / self.ticket_id

    @property
    def state_dir(self) -> Path:
        """Stage checkpoints. Machine-only, gitignored."""
        return self.flux_dir / STATE_DIRNAME / self.ticket_id

    @property
    def metrics_path(self) -> Path:
        return self.flux_dir / METRICS_RELPATH
