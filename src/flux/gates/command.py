"""``CommandGate`` — a gate backed by one subprocess.

A gate is evidence, not judgment (ADR 0005): flux runs the command itself and reads the
exit status. What this module adds on top of :mod:`flux.proc` is the rule that decides a
verdict, including the one that matters most — a gate that could not run has *failed*.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from flux.metrics.record import GateOutcome
from flux.proc import (
    DEFAULT_TIMEOUT_S,
    MAX_DETAIL_CHARS,
    CommandRun,
    clean_env,
    run_command,
    tail,
)

Summarizer = Callable[[CommandRun], str]


def default_summary(run: CommandRun) -> str:
    """Nothing on success; the tail of the output on failure."""
    return "" if run.returncode == 0 else tail(run.output)


@dataclass(frozen=True, slots=True)
class CommandGate:
    """A :class:`~flux.runner.stage.Gate` backed by one subprocess.

    ``summarize`` decides what the runner keeps from the output. It is a field rather
    than a subclass hook so that a gate is fully described by data — which is what
    lets ``flux.toml`` name one.
    """

    name: str
    argv: tuple[str, ...]
    timeout_s: int = DEFAULT_TIMEOUT_S
    ok_returncodes: tuple[int, ...] = (0,)
    summarize: Summarizer = default_summary
    env: Mapping[str, str] | None = field(default=None)
    """Extra variables for the gate, layered over a cleaned environment."""

    def run(self, worktree: Path) -> GateOutcome:
        run = run_command(self.argv, cwd=worktree, timeout_s=self.timeout_s, env=self._env())
        if not run.completed:
            # A gate that could not run is a failed gate. Skipping it would let a
            # missing typechecker read as a clean typecheck, which is the one thing
            # the gate suite exists to prevent.
            return GateOutcome(
                name=self.name,
                passed=False,
                duration_ms=run.duration_ms,
                detail=_clip(f"{self.name} did not run: {run.fault}"),
            )
        passed = run.returncode in self.ok_returncodes
        detail = self.summarize(run)
        if not passed and not detail:
            detail = f"exit status {run.returncode}"
        return GateOutcome(
            name=self.name,
            passed=passed,
            duration_ms=run.duration_ms,
            detail=_clip(detail),
        )

    def _env(self) -> Mapping[str, str]:
        """A cleaned environment, so the gate measures the repo and not flux."""
        base = clean_env()
        return {**base, **self.env} if self.env is not None else base


def _clip(detail: str) -> str:
    return detail if len(detail) <= MAX_DETAIL_CHARS else detail[: MAX_DETAIL_CHARS - 1] + "…"
