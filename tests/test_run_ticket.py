"""``run_ticket()`` end to end with the executor stubbed — the T3 acceptance proofs.

Four properties the milestone is defined by: completed stages skip on rerun, a
kill mid-stage resumes cleanly, the review↔fix loop parks after ``max_review_iters``,
and a missing required artifact parks after exactly one retry.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fakes import FakeExecutor, FakeGate, FakeStage, StageCrash, make_executor
from flux.executor.types import WindowPressure
from flux.metrics.record import MetricsStore
from flux.runner.artifact import ArtifactSpec
from flux.runner.checkpoint import Checkpoint, CheckpointStore
from flux.runner.context import RunnerConfig, TicketContext
from flux.runner.loop import RunResult, run_ticket
from flux.runner.stage import Outcome
from flux.runner.transition import Pipeline

TESTS_SPEC = ArtifactSpec(path="tests.json", required_keys=("test_files",))
NOTES_SPEC = ArtifactSpec(path="impl-notes.md", kind="text", required_sections=("What changed",))
REVIEW_SPEC = ArtifactSpec(path="review.json", required_keys=("findings",))


@pytest.fixture
def ticket(tmp_path: Path) -> TicketContext:
    return TicketContext(ticket_id="flux-1", root=tmp_path, brief="add a parser")


def full_pipeline(**overrides: FakeStage) -> tuple[Pipeline, dict[str, FakeStage]]:
    """The five-stage pipeline with fakes, any of which the test can replace."""
    stages: dict[str, FakeStage] = {
        "tests": FakeStage("tests", spec=TESTS_SPEC),
        "implement": FakeStage("implement", spec=NOTES_SPEC),
        "review": FakeStage("review", spec=REVIEW_SPEC),
        "fix": FakeStage("fix", spec=REVIEW_SPEC),
        "pr": FakeStage("pr"),
    }
    stages.update(overrides)
    return Pipeline(stages=tuple(stages.values())), stages


def drive(
    ticket: TicketContext,
    pipeline: Pipeline,
    stages: dict[str, FakeStage],
    executor: FakeExecutor | None = None,
) -> tuple[RunResult, FakeExecutor]:
    executor = executor or make_executor(ticket, *stages.values())
    return run_ticket(ticket, pipeline, executor), executor


def test_a_clean_ticket_runs_every_stage_once_in_order(ticket: TicketContext) -> None:
    pipeline, stages = full_pipeline()
    result, executor = drive(ticket, pipeline, stages)

    assert result.status == "completed"
    assert result.stages_run == ("tests", "implement", "review", "pr")
    assert [name for name, _, _ in executor.calls] == list(result.stages_run)
    assert result.park is None


def test_each_stage_gets_a_freshly_hydrated_pack(ticket: TicketContext) -> None:
    """Nothing carries over in memory: every session's input comes from hydrate()."""
    pipeline, stages = full_pipeline()
    _, executor = drive(ticket, pipeline, stages)

    for name, pack, _cfg in executor.calls:
        assert pack is stages[name].hydrations[-1]
        assert pack.appendix == ""


# -- property 1: completed stages skip on rerun --


def test_completed_stages_skip_on_rerun(ticket: TicketContext) -> None:
    pipeline, stages = full_pipeline()
    drive(ticket, pipeline, stages)

    rerun, executor = drive(ticket, pipeline, stages)
    assert rerun.status == "completed"
    assert rerun.stages_run == ()
    assert executor.calls == []


def test_a_ticket_resumed_midway_only_runs_what_is_left(ticket: TicketContext) -> None:
    pipeline, stages = full_pipeline()
    CheckpointStore(ticket.state_dir).write(Checkpoint(stage="tests"))
    result, _ = drive(ticket, pipeline, stages)
    assert result.stages_run == ("implement", "review", "pr")


# -- property 2: kill mid-stage resumes cleanly --


def test_a_stage_killed_midway_leaves_no_checkpoint_and_reruns(ticket: TicketContext) -> None:
    pipeline, stages = full_pipeline(
        implement=FakeStage("implement", spec=NOTES_SPEC, crash_attempts=frozenset({0}))
    )
    with pytest.raises(StageCrash):
        drive(ticket, pipeline, stages)

    store = CheckpointStore(ticket.state_dir)
    assert store.completed_stages() == {"tests"}
    assert store.read("implement") is None

    # The process comes back; the crashed stage runs again and the finished one does not.
    healthy = full_pipeline(implement=FakeStage("implement", spec=NOTES_SPEC))
    result, executor = drive(ticket, *healthy)
    assert result.status == "completed"
    assert result.stages_run == ("implement", "review", "pr")
    assert executor.calls_for("tests") == []


def test_a_crash_still_burns_stage_budget(ticket: TicketContext) -> None:
    """Otherwise a stage that always dies would spin forever across resumes."""
    pipeline, stages = full_pipeline(
        tests=FakeStage("tests", spec=TESTS_SPEC, crash_attempts=frozenset({0}))
    )
    with pytest.raises(StageCrash):
        drive(ticket, pipeline, stages)
    assert CheckpointStore(ticket.state_dir).load_state("flux-1").stage_runs == 1


def test_the_stage_budget_backstop_parks(ticket: TicketContext) -> None:
    tight = TicketContext(
        ticket_id="flux-1", root=ticket.root, config=RunnerConfig(max_stage_runs=2)
    )
    pipeline, stages = full_pipeline()
    result, _ = drive(tight, pipeline, stages)
    assert result.status == "parked"
    assert result.park is not None
    assert result.park.reason == "stage-budget-exhausted"


# -- property 3: the review↔fix loop is bounded --


def review_loop_pipeline(open_findings: tuple[bool, ...]) -> tuple[Pipeline, dict[str, FakeStage]]:
    return full_pipeline(
        review=FakeStage(
            "review",
            spec=REVIEW_SPEC,
            outcomes=tuple(Outcome(open_findings=flag) for flag in open_findings),
        )
    )


def test_the_review_fix_loop_parks_after_max_review_iters(ticket: TicketContext) -> None:
    pipeline, stages = review_loop_pipeline((True,))
    result, _ = drive(ticket, pipeline, stages)

    assert result.status == "parked"
    assert result.stages_run == ("tests", "implement", "review", "fix", "review", "fix", "review")
    assert result.park is not None
    assert result.park.reason == "review-loop-exhausted"
    assert CheckpointStore(ticket.state_dir).load_state("flux-1").review_iterations == 3
    assert "pr" not in result.stages_run


def test_the_loop_budget_is_configurable(ticket: TicketContext) -> None:
    once = TicketContext(
        ticket_id="flux-1", root=ticket.root, config=RunnerConfig(max_review_iters=1)
    )
    pipeline, stages = review_loop_pipeline((True,))
    result, _ = drive(once, pipeline, stages)
    assert result.stages_run == ("tests", "implement", "review")
    assert result.status == "parked"


def test_a_resolved_review_lets_the_ticket_finish(ticket: TicketContext) -> None:
    pipeline, stages = review_loop_pipeline((True, False))
    result, _ = drive(ticket, pipeline, stages)

    assert result.status == "completed"
    assert result.stages_run == ("tests", "implement", "review", "fix", "review", "pr")


def test_a_completed_fix_invalidates_the_review_checkpoint(ticket: TicketContext) -> None:
    """The reviewer must see the fix; a stale review checkpoint would skip it."""
    pipeline, stages = review_loop_pipeline((True, False))
    drive(ticket, pipeline, stages)
    assert len(stages["review"].commits) == 2
    assert len(stages["fix"].commits) == 1


def test_a_parked_ticket_stays_parked_on_the_next_invocation(ticket: TicketContext) -> None:
    pipeline, stages = review_loop_pipeline((True,))
    drive(ticket, pipeline, stages)

    again, executor = drive(ticket, pipeline, stages)
    assert again.status == "parked"
    assert again.stages_run == ()
    assert executor.calls == []
    assert again.park is not None
    assert again.park.reason == "review-loop-exhausted"


# -- property 4: a missing artifact costs exactly one retry, then parks --


def test_a_missing_artifact_parks_after_exactly_one_retry(ticket: TicketContext) -> None:
    pipeline, stages = full_pipeline(
        implement=FakeStage("implement", spec=NOTES_SPEC, writes=(None,))
    )
    result, executor = drive(ticket, pipeline, stages)

    assert result.status == "parked"
    assert result.park is not None
    assert result.park.stage == "implement"
    assert result.park.reason == "artifact-invalid"
    assert len(executor.calls_for("implement")) == 2
    assert stages["implement"].commits == []
    assert CheckpointStore(ticket.state_dir).read("implement") is None


def test_the_retry_carries_a_nudge_naming_the_artifact(ticket: TicketContext) -> None:
    pipeline, stages = full_pipeline(
        implement=FakeStage("implement", spec=NOTES_SPEC, writes=(None,))
    )
    _, executor = drive(ticket, pipeline, stages)

    first, retry = (pack for _, pack, _ in executor.calls_for("implement"))
    assert first.appendix == ""
    assert "impl-notes.md" in retry.appendix
    assert "What changed" in retry.appendix
    assert retry.stable_prefix == first.stable_prefix  # the cache-stable half is untouched


def test_the_retry_can_succeed(ticket: TicketContext) -> None:
    pipeline, stages = full_pipeline(
        implement=FakeStage("implement", spec=NOTES_SPEC, writes=(None, "## What changed\n\nx\n"))
    )
    result, executor = drive(ticket, pipeline, stages)

    assert result.status == "completed"
    assert len(executor.calls_for("implement")) == 2
    assert CheckpointStore(ticket.state_dir).read("implement") is not None


def test_an_invalid_artifact_is_as_bad_as_a_missing_one(ticket: TicketContext) -> None:
    pipeline, stages = full_pipeline(
        tests=FakeStage("tests", spec=TESTS_SPEC, writes=(json.dumps({"wrong": 1}),))
    )
    result, executor = drive(ticket, pipeline, stages)
    assert result.status == "parked"
    assert len(executor.calls_for("tests")) == 2
    assert result.park is not None
    assert "test_files" in result.park.note


def test_a_failed_session_also_gets_one_retry_then_parks(ticket: TicketContext) -> None:
    pipeline, stages = full_pipeline(
        pr=FakeStage("pr", fail_attempts=frozenset({0, 1})),
    )
    result, executor = drive(ticket, pipeline, stages)
    assert result.status == "parked"
    assert result.park is not None
    assert result.park.reason == "session-failed"
    assert len(executor.calls_for("pr")) == 2


def test_retries_are_configurable(ticket: TicketContext) -> None:
    patient = TicketContext(
        ticket_id="flux-1", root=ticket.root, config=RunnerConfig(artifact_retries=3)
    )
    pipeline, stages = full_pipeline(
        tests=FakeStage("tests", spec=TESTS_SPEC, writes=(None,)),
    )
    result, executor = drive(patient, pipeline, stages)
    assert result.status == "parked"
    assert len(executor.calls_for("tests")) == 4


# -- gates, outcomes and hard stops --


def test_gate_results_reach_commit_and_the_metrics_line(ticket: TicketContext) -> None:
    gate = FakeGate(name="ruff")
    pipeline, stages = full_pipeline(
        implement=FakeStage("implement", spec=NOTES_SPEC, gate_list=(gate,))
    )
    drive(ticket, pipeline, stages)

    assert gate.runs == [ticket.worktree]
    _result, gate_results = stages["implement"].commits[0]
    assert [g.name for g in gate_results] == ["ruff"]

    records = MetricsStore(ticket.metrics_path).read()
    implement = next(r for r in records if r.stage == "implement")
    assert implement.gates_passed


def test_a_stage_that_parks_itself_stops_the_ticket(ticket: TicketContext) -> None:
    pipeline, stages = full_pipeline(
        implement=FakeStage(
            "implement",
            spec=NOTES_SPEC,
            gate_list=(FakeGate(name="pyright", passed=False),),
            outcomes=(Outcome(ok=False, parked=True, note="pyright failed", reason="gate-failed"),),
        )
    )
    result, _ = drive(ticket, pipeline, stages)

    assert result.status == "parked"
    assert result.park is not None
    assert result.park.reason == "gate-failed"
    # It ran, so there is a record for triage — but it did not stand, so it is not "done".
    store = CheckpointStore(ticket.state_dir)
    assert store.read("implement") is not None
    assert "implement" not in store.completed_stages()


def test_a_usage_limit_parks_without_retrying(ticket: TicketContext) -> None:
    """ADR 0010: on a limit hit the answer is park and resume at the window reset."""
    pipeline, stages = full_pipeline(
        tests=FakeStage(
            "tests",
            spec=TESTS_SPEC,
            window=WindowPressure(status="rejected", resets_at=99),
        )
    )
    result, executor = drive(ticket, pipeline, stages)

    assert result.status == "parked"
    assert result.park is not None
    assert result.park.reason == "usage-limit"
    assert "99" in result.park.note
    assert len(executor.calls_for("tests")) == 1


def test_blowing_the_token_budget_parks_without_retrying(ticket: TicketContext) -> None:
    pipeline, stages = full_pipeline(
        tests=FakeStage("tests", spec=TESTS_SPEC, max_tokens=2, usage_tokens=500)
    )
    result, executor = drive(ticket, pipeline, stages)

    assert result.status == "parked"
    assert result.park is not None
    assert result.park.reason == "token-budget-exceeded"
    assert "uncached" in result.park.note
    assert len(executor.calls_for("tests")) == 1


def test_cache_reads_do_not_count_against_the_token_budget(ticket: TicketContext) -> None:
    """A cached prefix is re-read every turn, so counting it would cap turns, not work."""
    pipeline, stages = full_pipeline(
        tests=FakeStage("tests", spec=TESTS_SPEC, max_tokens=100, cache_read_tokens=900_000)
    )
    result, _ = drive(ticket, pipeline, stages)

    assert result.completed


# -- metrics (ADR 0008) --


def test_one_metrics_line_per_executor_call_including_failed_attempts(
    ticket: TicketContext,
) -> None:
    pipeline, stages = full_pipeline(
        implement=FakeStage("implement", spec=NOTES_SPEC, writes=(None, "## What changed\n\nx\n"))
    )
    drive(ticket, pipeline, stages)

    records = MetricsStore(ticket.metrics_path).read()
    implement = [r for r in records if r.stage == "implement"]
    assert [(r.ok, r.retry_count) for r in implement] == [(False, 0), (True, 1)]
    assert implement[0].error is not None
    assert all(r.ticket == "flux-1" and r.variant == "harness" for r in records)


def test_the_variant_flag_reaches_the_metrics_store(ticket: TicketContext) -> None:
    pipeline, stages = full_pipeline()
    run_ticket(ticket, pipeline, make_executor(ticket, *stages.values()), variant="vanilla")
    assert {r.variant for r in MetricsStore(ticket.metrics_path).read()} == {"vanilla"}


def test_metrics_and_state_land_under_the_flux_namespace(ticket: TicketContext) -> None:
    """ADR 0006: one folder, and checkpoints stay out of the committed context dir."""
    pipeline, stages = full_pipeline()
    drive(ticket, pipeline, stages)

    assert ticket.metrics_path == ticket.root / ".flux" / "usage" / "metrics.jsonl"
    assert (ticket.root / ".flux" / "state" / "flux-1" / "tests.done.json").exists()
    assert (ticket.root / ".flux" / "context" / "flux-1" / "tests.json").exists()


def test_a_custom_store_and_metrics_path_are_honoured(
    ticket: TicketContext, tmp_path: Path
) -> None:
    pipeline, stages = full_pipeline()
    store = CheckpointStore(tmp_path / "elsewhere")
    metrics = MetricsStore(tmp_path / "elsewhere" / "metrics.jsonl")
    run_ticket(
        ticket, pipeline, make_executor(ticket, *stages.values()), store=store, metrics=metrics
    )
    assert store.completed_stages() == {"tests", "implement", "review", "pr"}
    assert metrics.path.exists()
    assert not ticket.metrics_path.exists()
