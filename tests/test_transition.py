"""The transition function — pure, bounded, and readable without running anything."""

from __future__ import annotations

import pytest

from fakes import FakeStage
from flux.errors import ConfigError
from flux.runner.checkpoint import ParkRecord, RunState
from flux.runner.context import RunnerConfig
from flux.runner.transition import Pipeline, next_stage

CONFIG = RunnerConfig()


def pipeline() -> Pipeline:
    return Pipeline(
        stages=(
            FakeStage("tests"),
            FakeStage("implement"),
            FakeStage("review"),
            FakeStage("fix"),
            FakeStage("pr"),
        )
    )


def decide(
    *,
    completed: set[str] | None = None,
    state: RunState | None = None,
    config: RunnerConfig = CONFIG,
) -> tuple[str, str]:
    """Return ``(kind, stage-or-reason)`` — the whole decision in one comparable pair."""
    decision = next_stage(
        pipeline(),
        completed=frozenset(completed or set()),
        state=state or RunState(ticket="flux-1"),
        config=config,
    )
    if decision.kind == "run":
        assert decision.stage is not None
        return "run", decision.stage.name
    return decision.kind, decision.reason


def test_first_stage_runs_on_a_fresh_ticket() -> None:
    assert decide() == ("run", "tests")


def test_completed_stages_are_skipped() -> None:
    assert decide(completed={"tests"}) == ("run", "implement")
    assert decide(completed={"tests", "implement"}) == ("run", "review")


def test_clean_review_moves_past_the_loop_to_pr() -> None:
    assert decide(completed={"tests", "implement", "review"}) == ("run", "pr")


def test_pipeline_finishes_when_every_stage_is_done() -> None:
    assert decide(completed={"tests", "implement", "review", "pr"}) == ("finished", "unspecified")


def test_fix_is_never_reached_by_the_linear_walk() -> None:
    """Fix exists only to answer findings; nothing else may schedule it."""
    assert decide(completed={"tests", "implement", "review", "pr"})[0] == "finished"


def test_open_findings_route_to_the_fix_stage() -> None:
    state = RunState(ticket="flux-1", open_findings=True, review_iterations=1)
    assert decide(completed={"tests", "implement", "review"}, state=state) == ("run", "fix")


def test_review_loop_parks_once_the_iteration_budget_is_spent() -> None:
    state = RunState(ticket="flux-1", open_findings=True, review_iterations=3)
    assert decide(completed={"tests", "implement", "review"}, state=state) == (
        "park",
        "review-loop-exhausted",
    )


def test_review_budget_is_configurable() -> None:
    state = RunState(ticket="flux-1", open_findings=True, review_iterations=1)
    assert decide(
        completed={"tests", "implement", "review"},
        state=state,
        config=RunnerConfig(max_review_iters=1),
    ) == ("park", "review-loop-exhausted")


def test_human_acceptance_lets_the_ticket_move_on_with_findings_open() -> None:
    state = RunState(ticket="flux-1", open_findings=True, review_iterations=9, human_accepted=True)
    assert decide(completed={"tests", "implement", "review"}, state=state) == ("run", "pr")


def test_a_parked_ticket_stays_parked() -> None:
    state = RunState(
        ticket="flux-1",
        parked=ParkRecord(stage="implement", reason="artifact-invalid", note="no notes file"),
    )
    assert decide(state=state) == ("park", "artifact-invalid")


def test_next_stage_reads_nothing_but_its_arguments() -> None:
    """The same inputs always give the same answer — no disk, no clock, no memory."""
    args = {"completed": {"tests"}, "state": RunState(ticket="flux-1")}
    assert decide(**args) == decide(**args)  # type: ignore[arg-type]


# -- pipeline construction --


def test_pipeline_rejects_duplicate_stage_names() -> None:
    with pytest.raises(ConfigError, match="unique"):
        Pipeline(stages=(FakeStage("tests"), FakeStage("tests")))


def test_pipeline_rejects_an_empty_stage_list() -> None:
    with pytest.raises(ConfigError, match="at least one stage"):
        Pipeline(stages=())


def test_pipeline_rejects_a_review_stage_with_no_fix_stage() -> None:
    with pytest.raises(ConfigError, match="no 'fix' stage"):
        Pipeline(stages=(FakeStage("review"), FakeStage("pr")))


def test_a_pipeline_without_a_review_loop_is_allowed() -> None:
    linear = Pipeline(stages=(FakeStage("implement"), FakeStage("pr")))
    assert linear.names == ("implement", "pr")
    decision = next_stage(
        linear,
        completed=frozenset({"implement"}),
        state=RunState(ticket="flux-1", open_findings=True),
        config=CONFIG,
    )
    assert decision.stage is not None
    assert decision.stage.name == "pr"


def test_by_name_reports_an_unknown_stage() -> None:
    with pytest.raises(ConfigError, match="no stage named"):
        pipeline().by_name("nope")
