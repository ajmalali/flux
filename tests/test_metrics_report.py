"""Aggregation and rendering behind ``gus metrics`` (ADR 0008)."""

from __future__ import annotations

from gus.metrics import (
    GateOutcome,
    MetricRecord,
    aggregate,
    build_report,
    group_by_stage,
    group_by_variant,
    latest_window,
    render,
)


def rec(
    stage: str = "implement",
    *,
    ticket: str = "gus-1",
    variant: str = "harness",
    ok: bool = True,
    tokens: tuple[int, int, int, int] = (0, 0, 0, 0),
    cost: float | None = None,
    wall_ms: int = 0,
    retries: int = 0,
    explore: int = 0,
    gates: tuple[GateOutcome, ...] = (),
    window: tuple[str, float, int] | None = None,
    ts: str = "2026-01-01T00:00:00.000Z",
) -> MetricRecord:
    inp, out, cread, ccreate = tokens
    return MetricRecord(
        ticket=ticket,
        stage=stage,
        model="claude-sonnet-5",
        effort="high",
        billing_mode="subscription",
        ok=ok,
        ts=ts,
        input_tokens=inp,
        output_tokens=out,
        cache_read_tokens=cread,
        cache_creation_tokens=ccreate,
        total_cost_usd=cost,
        wall_ms=wall_ms,
        retry_count=retries,
        exploratory_calls=explore,
        variant=variant,
        gates=gates,
        window_status=window[0] if window else None,
        window_utilization=window[1] if window else None,
        window_resets_at=window[2] if window else None,
    )


def test_aggregate_of_nothing_is_empty_not_a_crash() -> None:
    agg = aggregate([])
    assert agg.runs == 0
    assert agg.ok_rate == 0.0
    assert agg.mean_tokens == 0.0
    assert agg.gate_pass_rate == 0.0


def test_aggregate_sums_tokens_and_separates_uncached_input() -> None:
    agg = aggregate([rec(tokens=(100, 10, 900, 50)), rec(tokens=(200, 20, 100, 0))])
    assert agg.total_tokens == 1380
    assert agg.output_tokens == 30
    assert agg.billable_input_tokens == 350
    assert agg.cache_read_tokens == 1000


def test_aggregate_tracks_failures_retries_and_exploration() -> None:
    agg = aggregate([rec(ok=True, retries=1, explore=2), rec(ok=False, retries=0, explore=5)])
    assert agg.runs == 2
    assert agg.ok_runs == 1
    assert agg.ok_rate == 0.5
    assert agg.retries == 1
    assert agg.exploratory_calls == 7


def test_aggregate_computes_gate_pass_rate() -> None:
    gates = (GateOutcome(name="ruff", passed=True), GateOutcome(name="pytest", passed=False))
    agg = aggregate([rec(gates=gates), rec(gates=(GateOutcome(name="ruff", passed=True),))])
    assert agg.gates_run == 3
    assert agg.gates_passed == 2
    assert agg.gate_pass_rate == 2 / 3


def test_missing_cost_is_treated_as_zero_not_an_error() -> None:
    """On a subscription most records carry no dollar figure at all (ADR 0010)."""
    agg = aggregate([rec(cost=None), rec(cost=0.25)])
    assert agg.cost_usd == 0.25


def test_group_by_stage_preserves_pipeline_order() -> None:
    records = [rec("tests"), rec("implement"), rec("review"), rec("implement")]
    groups = group_by_stage(records)
    assert [g.key for g in groups] == ["tests", "implement", "review"]
    assert groups[1].runs == 2


def test_group_by_variant_separates_harness_from_vanilla() -> None:
    records = [
        rec(variant="harness", tokens=(100, 0, 0, 0)),
        rec(variant="vanilla", tokens=(400, 0, 0, 0)),
    ]
    by_variant = {g.key: g for g in group_by_variant(records)}
    assert by_variant["harness"].total_tokens == 100
    assert by_variant["vanilla"].total_tokens == 400


def test_blank_group_keys_are_labelled_not_dropped() -> None:
    assert group_by_stage([rec(stage="")])[0].key == "(unset)"


def test_latest_window_takes_the_most_recent_reading() -> None:
    records = [
        rec(window=("allowed", 0.1, 1)),
        rec(window=("allowed_warning", 0.85, 2)),
        rec(window=None),
    ]
    window = latest_window(records)
    assert window is not None
    assert window.status == "allowed_warning"
    assert window.utilization == 0.85


def test_latest_window_is_none_when_never_reported() -> None:
    assert latest_window([rec()]) is None


def test_render_of_an_empty_report_says_so() -> None:
    assert render(build_report([])) == "No metrics recorded yet."


def test_render_shows_per_stage_rows_and_totals() -> None:
    records = [
        rec("tests", tokens=(100, 50, 0, 0), wall_ms=4000),
        rec("implement", tokens=(200, 80, 1000, 0), wall_ms=9000, retries=1),
    ]
    text = render(build_report(records))
    assert "Per stage" in text
    assert "tests" in text and "implement" in text
    assert "Totals: 2 runs" in text
    assert "1 retries" in text


def test_render_shows_the_ab_block_only_when_both_variants_exist() -> None:
    harness_only = render(build_report([rec(variant="harness")]))
    assert "kill-criterion" not in harness_only

    both = render(build_report([rec(variant="harness"), rec(variant="vanilla")]))
    assert "Harness vs vanilla" in both


def test_render_surfaces_window_pressure_and_malformed_lines() -> None:
    text = render(build_report([rec(window=("allowed_warning", 0.82, 5))], malformed_lines=3))
    assert "Usage window: allowed_warning" in text
    assert "82% consumed" in text
    assert "skipped 3 malformed" in text
