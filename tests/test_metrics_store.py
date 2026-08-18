"""The metrics JSONL store (ADR 0008, design.md §3)."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from flux.executor import ExecResult, PromptPack, Usage, WindowPressure
from flux.executor.stub import StubExecutor, ok_result
from flux.executor.types import ExecConfig
from flux.metrics import GateOutcome, MetricRecord, MetricsStore


def make_record(**overrides: object) -> MetricRecord:
    base: dict[str, object] = {
        "ticket": "flux-1",
        "stage": "implement",
        "model": "claude-sonnet-5",
        "effort": "high",
        "billing_mode": "subscription",
    }
    base.update(overrides)
    return MetricRecord(**base)  # type: ignore[arg-type]


def test_record_round_trips_through_jsonl(tmp_path: Path) -> None:
    store = MetricsStore(tmp_path / "usage" / "metrics.jsonl")
    written = store.record(
        make_record(
            input_tokens=100,
            output_tokens=20,
            gates=(GateOutcome(name="ruff", passed=True, duration_ms=300),),
        )
    )
    (read_back,) = store.read()
    assert read_back == written


def test_record_creates_missing_parent_directories(tmp_path: Path) -> None:
    store = MetricsStore(tmp_path / "deep" / "nested" / "metrics.jsonl")
    store.record(make_record())
    assert store.path.exists()


def test_records_append_rather_than_overwrite(tmp_path: Path) -> None:
    store = MetricsStore(tmp_path / "metrics.jsonl")
    for stage in ("tests", "implement", "review"):
        store.record(make_record(stage=stage))
    assert [r.stage for r in store.read()] == ["tests", "implement", "review"]


def test_each_record_is_exactly_one_line(tmp_path: Path) -> None:
    """Parallel tickets (M5) append to a shared file; multi-line records would interleave."""
    store = MetricsStore(tmp_path / "metrics.jsonl")
    store.record(make_record(stage="a"))
    store.record(make_record(stage="b"))
    lines = store.path.read_text().splitlines()
    assert len(lines) == 2
    assert all(json.loads(line)["stage"] for line in lines)


def test_timestamp_is_stamped_when_absent(tmp_path: Path) -> None:
    store = MetricsStore(tmp_path / "metrics.jsonl")
    written = store.record(make_record())
    assert written.ts.endswith("Z")
    assert store.read()[0].ts == written.ts


def test_explicit_timestamp_is_preserved(tmp_path: Path) -> None:
    store = MetricsStore(tmp_path / "metrics.jsonl")
    store.record(make_record(ts="2026-01-01T00:00:00.000Z"))
    assert store.read()[0].ts == "2026-01-01T00:00:00.000Z"


def test_reading_a_missing_file_yields_nothing(tmp_path: Path) -> None:
    assert MetricsStore(tmp_path / "nope.jsonl").read() == []


def test_malformed_lines_are_skipped_not_fatal(tmp_path: Path) -> None:
    """A run killed mid-append must not make the whole history unreadable."""
    store = MetricsStore(tmp_path / "metrics.jsonl")
    store.record(make_record(stage="tests"))
    with store.path.open("a") as handle:
        handle.write('{"ticket": "flux-1", "stage": "impleme\n')  # truncated
        handle.write("\n")
        handle.write("[1, 2, 3]\n")  # valid JSON, wrong shape
    store.record(make_record(stage="review"))

    assert [r.stage for r in store.read()] == ["tests", "review"]
    assert store.count_malformed() == 2


def test_unknown_fields_are_ignored_on_read(tmp_path: Path) -> None:
    """Schema growth must not break older readers, or the history is worthless."""
    store = MetricsStore(tmp_path / "metrics.jsonl")
    with store.path.open("w") as handle:
        handle.write(json.dumps({"ticket": "t", "stage": "s", "future_field": 1}) + "\n")
    (record,) = store.read()
    assert record.ticket == "t"
    assert record.schema_version == 1


def test_gates_survive_the_round_trip(tmp_path: Path) -> None:
    store = MetricsStore(tmp_path / "metrics.jsonl")
    gates = (
        GateOutcome(name="ruff", passed=True, duration_ms=100),
        GateOutcome(name="pytest", passed=False, duration_ms=4000, detail="2 failed"),
    )
    store.record(make_record(gates=gates))
    (record,) = store.read()
    assert record.gates == gates
    assert record.gates_passed is False


def test_from_exec_result_captures_the_session(tmp_path: Path) -> None:
    result = ExecResult(
        ok=True,
        text="done",
        session_id="sess-7",
        model="claude-sonnet-5",
        effort="high",
        billing_mode="subscription",
        usage=Usage(input_tokens=11, output_tokens=22, cache_read_tokens=33),
        total_cost_usd=0.5,
        num_turns=4,
        duration_ms=8000,
        duration_api_ms=6000,
        tool_uses={"Read": 3, "Edit": 1},
        window=WindowPressure(status="allowed_warning", utilization=0.4, resets_at=99),
        pack_chars=2048,
    )
    record = MetricRecord.from_exec_result(
        ticket="flux-1",
        stage="implement",
        result=result,
        gates=[GateOutcome(name="ruff", passed=True)],
        retry_count=1,
    )
    assert record.input_tokens == 11
    assert record.cache_read_tokens == 33
    assert record.exploratory_calls == 3
    assert record.pack_chars == 2048
    assert record.retry_count == 1
    assert record.window_status == "allowed_warning"
    assert record.window_utilization == pytest.approx(0.4)
    assert record.ok is True

    MetricsStore(tmp_path / "m.jsonl").record(record)


def test_failure_reason_survives_the_round_trip(tmp_path: Path) -> None:
    """Triage needs to know why a stage failed without opening the transcript."""
    cfg = ExecConfig(model="m", effort="high")
    failed = replace(ok_result(cfg), ok=False, error="Reached maximum number of turns (3)")
    store = MetricsStore(tmp_path / "metrics.jsonl")
    store.record(MetricRecord.from_exec_result(ticket="t", stage="implement", result=failed))
    (record,) = store.read()
    assert record.ok is False
    assert record.error == "Reached maximum number of turns (3)"


def test_from_exec_result_is_not_ok_when_a_gate_failed() -> None:
    """Gates are the merge authority — a green session with a red gate is a failure."""
    cfg = ExecConfig(model="m", effort="high")
    record = MetricRecord.from_exec_result(
        ticket="t",
        stage="implement",
        result=ok_result(cfg),
        gates=[GateOutcome(name="pytest", passed=False)],
    )
    assert record.ok is False


def test_from_exec_result_prefers_the_runner_measured_wall_time() -> None:
    cfg = ExecConfig(model="m", effort="high")
    result = ok_result(cfg)
    assert (
        MetricRecord.from_exec_result(ticket="t", stage="s", result=result, wall_ms=12345).wall_ms
        == 12345
    )


def test_stub_executor_records_calls_and_repeats_its_last_response() -> None:
    """The stub is what proves the runner spine without an LLM (T3)."""
    cfg = ExecConfig(model="m", effort="high")
    pack = PromptPack(system_prompt="sys", stage_tail="tail")
    first = ok_result(cfg, text="first")
    second = ok_result(cfg, text="second")
    executor = StubExecutor(responses=[first, second])

    assert executor.run(pack, cfg).text == "first"
    assert executor.run(pack, cfg).text == "second"
    assert executor.run(pack, cfg).text == "second"
    assert executor.call_count == 3
    assert executor.calls[0][0] is pack
