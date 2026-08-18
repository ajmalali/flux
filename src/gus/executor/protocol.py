"""The one seam between gus and any model (ADR 0007).

Stage and runner code depends on this protocol and nothing else. Swapping the
backing agent — native workflows, another CLI, a different vendor — touches one
implementation module, never a stage.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from gus.executor.types import ExecConfig, ExecResult, PromptPack


@runtime_checkable
class Executor(Protocol):
    """Runs one prompt pack in one fresh session and reports what it cost."""

    def run(self, pack: PromptPack, cfg: ExecConfig) -> ExecResult:
        """Execute ``pack`` under ``cfg`` and return the session's outcome.

        Implementations must always start a fresh session (ADR 0003) and must never
        raise on a model-level failure — a failed session returns ``ExecResult`` with
        ``ok=False`` so the runner can retry or park. Raising is reserved for
        environment faults the runner cannot act on.
        """
        ...
