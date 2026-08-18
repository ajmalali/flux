"""The vanilla baseline arm of the A/B comparison (ADR 0008, design.md §3).

The harness has to keep proving it is worth more than typing the ticket at Claude Code
and walking away. That is what this module runs: the *same* ticket, in the same repo,
against the same gates, with none of the harness — no context pack, no repo map, no
artifact contract, no stage sequence. One session, one metrics line, `variant="vanilla"`.

Three fairness rules decide whether the resulting number means anything. Each of them
exists because breaking it would quietly hand the comparison to one side:

* **Same model and effort as the implement stage.** The question is whether the *harness*
  earns its keep, not whether Opus beats Haiku. `[stages.vanilla]` may override it, but it
  defaults to a copy of `[stages.implement]`.
* **Same gate pre-approval.** T4 measured what happens to a headless session that cannot
  run the gates it is told about: it reasons its way to a conclusion in prose over 31 turns
  instead of measuring it in one. Denying vanilla the gates would beat it with a handicap.
* **A clean starting tree.** A vanilla run in the worktree where the harness already did
  the work is measuring nothing, so it is refused rather than recorded.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass

from flux.config import VANILLA_STAGE, FluxConfig
from flux.errors import FluxError
from flux.executor.protocol import Executor
from flux.executor.types import ExecConfig, ExecResult, PromptPack
from flux.gates.spec import bash_permissions
from flux.metrics.record import GateOutcome, MetricRecord, MetricsStore
from flux.runner.checkpoint import CheckpointStore
from flux.runner.context import TicketContext
from flux.runner.stage import Gate

VANILLA_VARIANT = "vanilla"
HARNESS_VARIANT = "harness"


@dataclass(frozen=True, slots=True)
class VanillaResult:
    """What one baseline sample observed."""

    ticket: str
    ok: bool
    record: MetricRecord
    gates: tuple[GateOutcome, ...] = ()

    @property
    def gates_passed(self) -> bool:
        """Every gate green. With no gates configured this is vacuously true — the
        caller has to look at :attr:`gates` to tell "verified" from "unverified"."""
        return all(gate.passed for gate in self.gates)


def vanilla_pack(ticket: TicketContext) -> PromptPack:
    """The whole input to a baseline session: the ticket text, and nothing else.

    Deliberately not a :class:`~flux.executor.types.PromptPack` with an empty
    ``system_prompt`` *field set to something helpful* — an empty system prompt means
    the CLI's own default, which is what "vanilla Claude Code" is. Any harness framing
    added here would make the baseline a weaker version of the harness rather than its
    alternative.
    """
    return PromptPack(system_prompt="", context_pack=ticket.brief)


def vanilla_config(ticket: TicketContext, settings: FluxConfig) -> ExecConfig:
    """Model, effort and caps for the baseline arm — matched to `implement` by default."""
    return settings.profile(VANILLA_STAGE).exec_config(
        cwd=ticket.worktree,
        allowed_tools=bash_permissions(settings.gates),
    )


def run_vanilla(
    ticket: TicketContext,
    settings: FluxConfig,
    executor: Executor,
    *,
    metrics: MetricsStore | None = None,
    gates: Sequence[Gate] | None = None,
    force: bool = False,
) -> VanillaResult:
    """Run ``ticket`` as plain Claude Code and record the comparison line.

    Writes no checkpoint and no artifact: a baseline sample is a measurement, not a
    pipeline run, and it must not make the harness think a stage is done.

    Args:
        gates: the suite to judge the sample by. Defaults to the repo's configured
            suite, which is the only setting that makes the two arms comparable —
            the parameter exists so tests can supply verdicts, not so callers can
            grade the baseline on a different curve.
        force: run even though the harness has already worked this ticket here. The
            resulting number is not comparable; only useful for a deliberate re-measure
            in a tree that has since been reset.
    """
    if not force:
        _refuse_contaminated(ticket)

    store = metrics if metrics is not None else MetricsStore(ticket.metrics_path)
    pack = vanilla_pack(ticket)
    cfg = vanilla_config(ticket, settings)

    suite = settings.build_gates() if gates is None else tuple(gates)
    result, wall_ms = _timed(executor, pack, cfg)
    outcomes = tuple(gate.run(ticket.worktree) for gate in suite)
    record = store.record(
        MetricRecord.from_exec_result(
            ticket=ticket.ticket_id,
            stage=VANILLA_STAGE,
            result=result,
            gates=outcomes,
            wall_ms=wall_ms,
            variant=VANILLA_VARIANT,
        )
    )
    return VanillaResult(
        ticket=ticket.ticket_id,
        ok=result.ok and all(g.passed for g in outcomes),
        record=record,
        gates=outcomes,
    )


def _refuse_contaminated(ticket: TicketContext) -> None:
    """Stop before spending anything if the harness already ran this ticket here.

    Not a warning. A baseline measured against a tree the harness already changed
    reads as "vanilla solved it in one cheap turn", and that number would go into the
    table that decides whether the harness lives.
    """
    completed = sorted(CheckpointStore(ticket.state_dir).completed_stages())
    if not completed:
        return
    raise FluxError(
        f"ticket {ticket.ticket_id!r} has already run through the harness here "
        f"({', '.join(completed)}), so a vanilla baseline measured in this worktree would "
        "be comparing against work that is already done. Run the baseline in a fresh "
        "clone at the same commit, or pass --force if this tree has been reset."
    )


def _timed(executor: Executor, pack: PromptPack, cfg: ExecConfig) -> tuple[ExecResult, int]:
    started = time.monotonic()
    result = executor.run(pack, cfg)
    return result, int((time.monotonic() - started) * 1000)
