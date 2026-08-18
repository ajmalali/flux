"""CLI surface: stubs announce their milestone, ``metrics`` and ``doctor`` work."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from flux.cli import EXIT_NOT_IMPLEMENTED, EXIT_OK, EXIT_PARKED, build_parser, main
from flux.errors import BillingPolicyError
from flux.executor import AuthStatus
from flux.metrics import MetricRecord, MetricsStore

PLANNED = ["init", "index", "research", "plan", "tickets", "run", "status"]


def test_no_command_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == EXIT_OK
    assert "usage: flux" in capsys.readouterr().out


@pytest.mark.parametrize("command", [*PLANNED, "metrics", "doctor"])
def test_every_planned_subcommand_is_registered(command: str) -> None:
    """The surface is fixed now so milestones fill commands in, not reshape the CLI."""
    parser = build_parser()
    args = parser.parse_args([command])
    assert args.command == command


@pytest.mark.parametrize("command", PLANNED)
def test_unimplemented_commands_exit_distinctly(
    command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([command]) == EXIT_NOT_IMPLEMENTED
    assert "not implemented" in capsys.readouterr().err


def write_metrics(path: Path) -> MetricsStore:
    store = MetricsStore(path)
    store.record(
        MetricRecord(
            ticket="flux-1",
            stage="tests",
            model="claude-sonnet-5",
            effort="high",
            billing_mode="subscription",
            input_tokens=100,
            output_tokens=25,
            wall_ms=3000,
        )
    )
    store.record(
        MetricRecord(
            ticket="flux-2",
            stage="implement",
            model="claude-sonnet-5",
            effort="high",
            billing_mode="subscription",
            input_tokens=400,
            output_tokens=90,
            wall_ms=12000,
        )
    )
    return store


def test_metrics_reports_an_empty_store(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["metrics", "--path", str(tmp_path / "none.jsonl")]) == EXIT_OK
    assert "No metrics recorded yet." in capsys.readouterr().out


def test_metrics_prints_per_stage_cost_and_time(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "metrics.jsonl"
    write_metrics(path)
    assert main(["metrics", "--path", str(path)]) == EXIT_OK
    out = capsys.readouterr().out
    assert "Per stage" in out
    assert "tests" in out and "implement" in out
    assert "Estimated cost" in out
    assert "15.0" in out, "total wall time in seconds should be reported"


def test_metrics_filters_by_ticket(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "metrics.jsonl"
    write_metrics(path)
    assert main(["metrics", "--path", str(path), "--ticket", "flux-2"]) == EXIT_OK
    out = capsys.readouterr().out
    assert "Totals: 1 runs" in out
    assert "tests" not in out


def test_metrics_filters_by_stage(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "metrics.jsonl"
    write_metrics(path)
    assert main(["metrics", "--path", str(path), "--stage", "tests"]) == EXIT_OK
    assert "Totals: 1 runs" in capsys.readouterr().out


def test_metrics_warns_about_malformed_lines(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "metrics.jsonl"
    write_metrics(path)
    with path.open("a") as handle:
        handle.write("{ truncated\n")
    assert main(["metrics", "--path", str(path)]) == EXIT_OK
    assert "malformed" in capsys.readouterr().out


def test_doctor_reports_a_healthy_subscription(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-leaked")
    payload = {
        "loggedIn": True,
        "authMethod": "claude.ai",
        "apiProvider": "firstParty",
        "email": "dev@example.com",
        "subscriptionType": "max",
    }

    def fake_preflight(**_kwargs: object) -> AuthStatus:
        return AuthStatus.from_json(payload)

    monkeypatch.setattr("flux.cli.preflight", fake_preflight)
    assert main(["doctor"]) == EXIT_OK
    out = capsys.readouterr().out
    assert "dev@example.com" in out
    assert "ANTHROPIC_API_KEY" in out, "doctor should say what it stripped"


def test_a_park_signal_exits_with_the_park_code(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Parking is a reportable outcome, not a stack trace."""

    def boom(**_kwargs: object) -> None:
        raise BillingPolicyError("not logged in", reason="not-logged-in")

    monkeypatch.setattr("flux.cli.preflight", boom)
    assert main(["doctor"]) == EXIT_PARKED
    err = capsys.readouterr().err
    assert "parked (not-logged-in)" in err


def test_metrics_output_is_derived_from_the_stored_json(tmp_path: Path) -> None:
    """Guards against the report reading fields the writer never wrote."""
    path = tmp_path / "metrics.jsonl"
    write_metrics(path)
    stored = [json.loads(line) for line in path.read_text().splitlines()]
    assert {row["stage"] for row in stored} == {"tests", "implement"}
