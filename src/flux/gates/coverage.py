"""The coverage gate: a threshold check, not a report.

Separate from :class:`~flux.gates.command.CommandGate` because its verdict is not the
exit status. ``coverage report`` exits 0 whether coverage is 90% or 9%, so the gate
has to read the total out of the table and compare it itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from flux.gates.summaries import coverage_percent
from flux.metrics.record import GateOutcome
from flux.proc import DEFAULT_TIMEOUT_S, clean_env, run_command, tail


@dataclass(frozen=True, slots=True)
class CoverageGate:
    """Runs a coverage reporter and fails when total coverage is below ``min_percent``."""

    name: str
    argv: tuple[str, ...]
    min_percent: float = 0.0
    timeout_s: int = DEFAULT_TIMEOUT_S

    def run(self, worktree: Path) -> GateOutcome:
        run = run_command(self.argv, cwd=worktree, timeout_s=self.timeout_s, env=clean_env())
        if not run.completed:
            return GateOutcome(
                name=self.name,
                passed=False,
                duration_ms=run.duration_ms,
                detail=f"{self.name} did not run: {run.fault}",
            )
        if run.returncode != 0:
            return GateOutcome(
                name=self.name,
                passed=False,
                duration_ms=run.duration_ms,
                detail=tail(run.output) or f"exit status {run.returncode}",
            )
        total = coverage_percent(run)
        if total is None:
            # An unreadable report is a failed gate: "we could not measure it" must
            # never be recorded as "it was fine".
            return GateOutcome(
                name=self.name,
                passed=False,
                duration_ms=run.duration_ms,
                detail="no TOTAL line in the coverage report",
            )
        passed = total >= self.min_percent
        return GateOutcome(
            name=self.name,
            passed=passed,
            duration_ms=run.duration_ms,
            detail=f"{total:.1f}% total coverage (minimum {self.min_percent:.1f}%)",
        )
