"""``run_ticket()`` — the stateless runner loop (design.md §1).

The loop owns four responsibilities and delegates everything else:

1. ask :func:`~flux.runner.transition.next_stage` what to do (pure, from disk),
2. run the stage's session through the :class:`~flux.executor.protocol.Executor` seam,
3. verify the required artifact itself — one retry with an explicit nudge, then park,
4. record metrics and write the checkpoint.

It holds no state between iterations: every pass re-reads the checkpoint store, so
killing the process at any point and re-invoking it resumes rather than restarts.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Literal

from flux.errors import FluxError, ParkSignal
from flux.executor.protocol import Executor
from flux.executor.types import ExecConfig, ExecResult, PromptPack
from flux.metrics.record import GateOutcome, MetricRecord, MetricsStore
from flux.runner.artifact import (
    FAILED_SESSION_NUDGE,
    ArtifactCheck,
    missing_artifact_nudge,
    validate_artifact,
)
from flux.runner.checkpoint import Checkpoint, CheckpointStore, ParkRecord, RunState
from flux.runner.context import TicketContext
from flux.runner.stage import Outcome, Stage
from flux.runner.transition import Decision, Pipeline, next_stage

RunStatus = Literal["completed", "parked"]


@dataclass(frozen=True, slots=True)
class RunResult:
    """What one ``run_ticket`` invocation did. Stages already done do not appear."""

    ticket: str
    status: RunStatus
    stages_run: tuple[str, ...] = ()
    park: ParkRecord | None = None

    @property
    def completed(self) -> bool:
        return self.status == "completed"


def run_ticket(
    ticket: TicketContext,
    pipeline: Pipeline,
    executor: Executor,
    *,
    store: CheckpointStore | None = None,
    metrics: MetricsStore | None = None,
    variant: str = "harness",
) -> RunResult:
    """Drive ``ticket`` through ``pipeline`` until it finishes or parks.

    Args:
        variant: ``harness`` or ``vanilla`` — the A/B axis recorded in metrics (ADR 0008).
    """
    checkpoints = store if store is not None else CheckpointStore(ticket.state_dir)
    metrics_store = metrics if metrics is not None else MetricsStore(ticket.metrics_path)
    ran: list[str] = []

    while True:
        state = checkpoints.load_state(ticket.ticket_id)
        decision = next_stage(
            pipeline,
            completed=checkpoints.completed_stages(),
            state=state,
            config=ticket.config,
        )
        if decision.kind == "finished":
            return RunResult(ticket=ticket.ticket_id, status="completed", stages_run=tuple(ran))
        if decision.kind == "park":
            return _park(checkpoints, state, _park_record(decision, ran), ran)

        stage = decision.stage
        if stage is None:  # unreachable: a "run" decision always carries a stage
            raise FluxError(f"transition returned {decision.kind!r} without a stage")
        if state.stage_runs >= ticket.config.max_stage_runs:
            note = (
                f"stage budget of {ticket.config.max_stage_runs} invocations exhausted "
                f"before {stage.name!r} could run"
            )
            record = ParkRecord(stage=stage.name, reason="stage-budget-exhausted", note=note)
            return _park(checkpoints, state, record, ran)

        # Persisted *before* the stage runs, so a crashing stage still burns budget and
        # a crash loop cannot spin forever.
        state = checkpoints.save_state(replace(state, stage_runs=state.stage_runs + 1))

        try:
            outcome = _run_stage(ticket, stage, executor, checkpoints, metrics_store, variant)
        except ParkSignal as parked:
            record = ParkRecord(stage=stage.name, reason=parked.reason, note=parked.note)
            return _park(checkpoints, checkpoints.load_state(ticket.ticket_id), record, ran)

        ran.append(stage.name)
        state = _apply_outcome(checkpoints, pipeline, stage, outcome, ticket.ticket_id)
        if outcome.parked:
            record = ParkRecord(stage=stage.name, reason=outcome.reason, note=outcome.note)
            return _park(checkpoints, state, record, ran)


def _run_stage(
    ticket: TicketContext,
    stage: Stage,
    executor: Executor,
    store: CheckpointStore,
    metrics: MetricsStore,
    variant: str,
) -> Outcome:
    """Run one stage to a verified conclusion, or raise :class:`ParkSignal`.

    Artifact validation is the gate on "did this stage happen": a session that
    returned successfully but left no valid artifact is a failed attempt, and gets
    exactly the retries ``RunnerConfig.artifact_retries`` allows (design fixes it at 1).
    """
    pack = stage.hydrate(ticket)
    cfg = stage.config(ticket)
    spec = stage.required_artifact()
    attempt = 0

    while True:
        result, wall_ms = _timed_run(executor, pack, cfg)

        hard_stop = _hard_stop(result, cfg)
        if hard_stop is not None:
            _record(metrics, ticket, stage, result, attempt, wall_ms, variant, error=hard_stop.note)
            raise hard_stop

        check = validate_artifact(ticket, spec)
        problem = _attempt_problem(result, check)
        if problem is None:
            break

        _record(metrics, ticket, stage, result, attempt, wall_ms, variant, error=problem)
        if attempt >= ticket.config.artifact_retries:
            raise ParkSignal(
                f"{stage.name}: {problem} (after {attempt + 1} attempt(s))",
                reason="artifact-invalid" if not check.ok else "session-failed",
            )
        attempt += 1
        pack = pack.with_appendix(_nudge(ticket, result, check))

    gate_results = tuple(gate.run(ticket.worktree) for gate in stage.gates(ticket))
    _record(metrics, ticket, stage, result, attempt, wall_ms, variant, gates=gate_results)

    outcome = stage.commit(ticket, result, gate_results)
    store.write(
        Checkpoint(
            stage=stage.name,
            ok=outcome.ok and not outcome.parked,
            attempts=attempt + 1,
            note=outcome.note,
            artifact_path=spec.path if spec else "",
            artifact_digest=check.digest,
            detail=outcome.detail,
        )
    )
    return outcome


def _timed_run(executor: Executor, pack: PromptPack, cfg: ExecConfig) -> tuple[ExecResult, int]:
    started = time.monotonic()
    result = executor.run(pack, cfg)
    return result, int((time.monotonic() - started) * 1000)


def _hard_stop(result: ExecResult, cfg: ExecConfig) -> ParkSignal | None:
    """Conditions no retry can fix — parking immediately is cheaper than trying.

    A usage-limit hit parks and waits for the window to reset (ADR 0010); retrying
    would only fail again. An over-budget session parks because the retry would spend
    more of the budget it already blew.
    """
    if result.window is not None and result.window.limit_hit:
        resets = f" (window resets at {result.window.resets_at})" if result.window.resets_at else ""
        return ParkSignal(f"subscription usage limit reached{resets}", reason="usage-limit")
    spent = result.usage.total_tokens
    if spent > cfg.max_tokens:
        return ParkSignal(
            f"session used {spent:,} tokens against a budget of {cfg.max_tokens:,}",
            reason="token-budget-exceeded",
        )
    return None


def _attempt_problem(result: ExecResult, check: ArtifactCheck) -> str | None:
    """Why this attempt does not count, or ``None`` if it does."""
    if not result.ok:
        return result.error or "the session did not complete successfully"
    if not check.ok:
        name = check.spec.path if check.spec else str(check.path)
        return f"required artifact {name!r} is invalid: {check.problem}"
    return None


def _nudge(ticket: TicketContext, result: ExecResult, check: ArtifactCheck) -> str:
    if not check.ok:
        return missing_artifact_nudge(check, context_dir=ticket.context_dir)
    return FAILED_SESSION_NUDGE


def _record(
    metrics: MetricsStore,
    ticket: TicketContext,
    stage: Stage,
    result: ExecResult,
    attempt: int,
    wall_ms: int,
    variant: str,
    *,
    gates: Sequence[GateOutcome] = (),
    error: str | None = None,
) -> MetricRecord:
    """Append one line per executor call — failed attempts included (ADR 0008).

    Retries are exactly what the metrics store exists to make visible, so a dropped
    attempt would understate what the ticket cost.
    """
    record = MetricRecord.from_exec_result(
        ticket=ticket.ticket_id,
        stage=stage.name,
        result=result,
        gates=gates,
        retry_count=attempt,
        wall_ms=wall_ms,
        variant=variant,
    )
    if error is not None:
        record = replace(record, ok=False, error=error)
    return metrics.record(record)


def _apply_outcome(
    store: CheckpointStore,
    pipeline: Pipeline,
    stage: Stage,
    outcome: Outcome,
    ticket_id: str,
) -> RunState:
    """Fold a stage's outcome into the run state, and turn the review loop.

    Two rules, both of them the loop's business rather than any stage's:
    a completed review pass counts against ``max_review_iters``, and a completed fix
    invalidates the review — the reviewer must see the fix before the ticket moves on.
    """
    state = store.load_state(ticket_id)
    if outcome.open_findings is not None:
        state = replace(state, open_findings=outcome.open_findings)
    if stage.name == pipeline.review_stage:
        state = replace(state, review_iterations=state.review_iterations + 1)
    elif stage.name == pipeline.fix_stage and not outcome.parked:
        store.clear(pipeline.review_stage)
        store.clear(pipeline.fix_stage)
    return store.save_state(state)


def _park_record(decision: Decision, ran: Sequence[str]) -> ParkRecord:
    stage_name = decision.stage.name if decision.stage else (ran[-1] if ran else "")
    return ParkRecord(stage=stage_name, reason=decision.reason, note=decision.note)


def _park(
    store: CheckpointStore,
    state: RunState,
    record: ParkRecord,
    ran: Sequence[str],
) -> RunResult:
    """Persist the park so the next invocation stops at the same place, and report it."""
    parked = state.parked or record
    if state.parked is None:
        store.save_state(replace(state, parked=record))
    return RunResult(
        ticket=state.ticket,
        status="parked",
        stages_run=tuple(ran),
        park=parked,
    )
