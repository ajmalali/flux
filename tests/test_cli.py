"""CLI surface: stubs announce their milestone, ``metrics`` and ``doctor`` work."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from flux.cli import (
    EXIT_ERROR,
    EXIT_NOT_IMPLEMENTED,
    EXIT_OK,
    EXIT_PARKED,
    build_parser,
    main,
)
from flux.config import FluxConfig
from flux.errors import BillingPolicyError
from flux.executor import AuthStatus
from flux.metrics import MetricRecord, MetricsStore
from flux.runner.checkpoint import Checkpoint, CheckpointStore, ParkRecord, RunState
from flux.runner.context import TicketContext
from flux.stages import build_pipeline

PLANNED = ["research", "plan", "tickets"]
IMPLEMENTED = ["metrics", "doctor", "status", "init", "run", "unpark", "index"]


def test_no_command_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == EXIT_OK
    assert "usage: flux" in capsys.readouterr().out


@pytest.mark.parametrize("command", [*PLANNED, *IMPLEMENTED])
def test_every_planned_subcommand_is_registered(command: str) -> None:
    """The surface is fixed now so milestones fill commands in, not reshape the CLI."""
    parser = build_parser()
    argv = [command, "flux-1"] if command in ("status", "run", "unpark") else [command]
    args = parser.parse_args(argv)
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


def test_status_on_a_ticket_that_has_not_started(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["status", "flux-1", "--root", str(tmp_path)]) == EXIT_OK
    out = capsys.readouterr().out
    assert "(none run yet)" in out
    assert "active" in out


def test_status_lists_checkpoints_and_the_park_note(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ticket = TicketContext(ticket_id="flux-1", root=tmp_path)
    store = CheckpointStore(ticket.state_dir)
    store.write(Checkpoint(stage="implement", note="landed"))
    store.write(Checkpoint(stage="review", ok=False, attempts=2))
    store.save_state(
        RunState(
            ticket="flux-1",
            review_iterations=3,
            open_findings=True,
            parked=ParkRecord(stage="review", reason="review-loop-exhausted", note="3 passes"),
        )
    )

    assert main(["status", "flux-1", "--root", str(tmp_path)]) == EXIT_OK
    out = capsys.readouterr().out
    assert "implement" in out and "done" in out
    assert "review" in out and "failed" in out
    assert "3 pass(es), findings open" in out
    assert "PARKED at review (review-loop-exhausted)" in out


def test_status_rejects_a_ticket_id_that_is_not_a_safe_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The id becomes a directory name, so ``flux status ../../etc`` must not read it."""
    assert main(["status", "../escape", "--root", str(tmp_path)]) == EXIT_ERROR
    assert "safe path component" in capsys.readouterr().err


def test_metrics_output_is_derived_from_the_stored_json(tmp_path: Path) -> None:
    """Guards against the report reading fields the writer never wrote."""
    path = tmp_path / "metrics.jsonl"
    write_metrics(path)
    stored = [json.loads(line) for line in path.read_text().splitlines()]
    assert {row["stage"] for row in stored} == {"tests", "implement"}


def test_init_reports_what_it_created(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")

    assert main(["init", "--root", str(tmp_path)]) == EXIT_OK

    out = capsys.readouterr().out
    assert "target:  python" in out
    assert ".flux/flux.toml" in out
    assert "flux run" in out
    assert (tmp_path / ".flux" / "flux.toml").exists()


def test_init_warns_on_stderr_when_it_cannot_gate_the_repo(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["init", "--root", str(tmp_path)]) == EXIT_OK
    assert "no gates" in capsys.readouterr().err


def test_run_on_a_ticket_with_no_brief_explains_rather_than_crashing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["run", "flux-1", "--root", str(tmp_path)]) == EXIT_ERROR
    assert "ticket.md" in capsys.readouterr().err


def test_status_names_the_next_stage(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Status and run read the same transition function, so they cannot disagree."""
    assert main(["status", "flux-1", "--root", str(tmp_path)]) == EXIT_OK
    assert "next:    tests" in capsys.readouterr().out


def test_status_says_so_once_the_pipeline_is_complete(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ticket = TicketContext(ticket_id="flux-1", root=tmp_path)
    store = CheckpointStore(ticket.state_dir)
    for stage in build_pipeline(FluxConfig.load(tmp_path)).names:
        store.write(Checkpoint(stage=stage))

    assert main(["status", "flux-1", "--root", str(tmp_path)]) == EXIT_OK
    assert "pipeline is complete" in capsys.readouterr().out


def test_unpark_clears_the_park_so_the_ticket_runs_again(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ticket = TicketContext(ticket_id="flux-1", root=tmp_path)
    store = CheckpointStore(ticket.state_dir)
    store.write(Checkpoint(stage="tests", ok=True))
    store.write(Checkpoint(stage="implement", ok=False, note="gates failed"))
    store.save_state(
        RunState(
            ticket="flux-1",
            stage_runs=40,
            parked=ParkRecord(stage="implement", reason="gates-failed", note="test failed"),
        )
    )

    assert main(["unpark", "flux-1", "--root", str(tmp_path)]) == EXIT_OK

    state = store.load_state("flux-1")
    assert state.parked is None
    assert state.stage_runs == 0
    assert "gates-failed" in capsys.readouterr().out
    # The failed checkpoint stays: it is not ok, so the stage reruns and triage keeps it.
    checkpoint = store.read("implement")
    assert checkpoint is not None and not checkpoint.ok
    assert main(["status", "flux-1", "--root", str(tmp_path)]) == EXIT_OK
    assert "next:    implement" in capsys.readouterr().out


def test_unpark_on_a_running_ticket_says_so(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["unpark", "flux-1", "--root", str(tmp_path)]) == EXIT_OK
    assert "is not parked" in capsys.readouterr().out


def test_index_generates_and_reports_the_map(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = json.dumps(
        {"file_count": 9, "entries": [{"path": "src/core.py", "score": 1.0, "lines": 12}]}
    )
    script = tmp_path / "ranker.py"
    script.write_text(f"print({payload!r})", encoding="utf-8")
    config = tmp_path / ".flux" / "flux.toml"
    config.parent.mkdir(parents=True)
    config.write_text(f'[repo_map]\ncommand = ["{sys.executable}", "{script}"]\n', encoding="utf-8")

    assert main(["index", "--root", str(tmp_path)]) == EXIT_OK

    out = capsys.readouterr().out
    assert "mapped:  9 file(s) -> 1 ranked" in out
    assert "src/core.py" in out
    assert (tmp_path / ".flux" / "cache" / "repo-map.json").exists()


def test_index_reports_a_broken_ranker_rather_than_caching_an_empty_map(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = tmp_path / ".flux" / "flux.toml"
    config.parent.mkdir(parents=True)
    config.write_text('[repo_map]\ncommand = "flux-no-such-ranker"\n', encoding="utf-8")

    assert main(["index", "--root", str(tmp_path)]) == EXIT_ERROR
    assert "not on PATH" in capsys.readouterr().err
    assert not (tmp_path / ".flux" / "cache" / "repo-map.json").exists()


def write_ticket(root: Path, ticket_id: str, brief: str) -> Path:
    path = root / ".flux" / "context" / ticket_id / "ticket.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(brief, encoding="utf-8")
    return path


def test_vanilla_dry_run_shows_the_ticket_and_nothing_else(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The baseline's whole input is inspectable before a penny is spent (ADR 0008)."""
    write_ticket(tmp_path, "flux-1", "Add a --json flag to report.")
    assert main(["run", "flux-1", "--root", str(tmp_path), "--vanilla", "--dry-run"]) == EXIT_OK
    out = capsys.readouterr().out
    assert "next:    vanilla" in out
    assert "Add a --json flag to report." in out
    assert "Repo map" not in out


def test_vanilla_refuses_a_worktree_the_harness_already_worked(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_ticket(tmp_path, "flux-1", "Add a --json flag to report.")
    ticket = TicketContext(ticket_id="flux-1", root=tmp_path)
    CheckpointStore(ticket.state_dir).write(Checkpoint(stage="implement", ok=True))

    assert main(["run", "flux-1", "--root", str(tmp_path), "--vanilla"]) == EXIT_ERROR
    assert "already run through the harness" in capsys.readouterr().err


def test_metrics_says_when_no_baseline_has_ever_been_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Silence would read as "nothing to report"; the honest answer is "never checked"."""
    path = tmp_path / "metrics.jsonl"
    write_metrics(path)
    assert main(["metrics", "--path", str(path)]) == EXIT_OK
    out = capsys.readouterr().out
    assert "A/B vs vanilla Claude Code" in out
    assert "no paired samples yet" in out


def test_metrics_prints_the_paired_comparison(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "metrics.jsonl"
    store = MetricsStore(path)
    for variant, tokens in (("harness", 900), ("vanilla", 300)):
        store.record(
            MetricRecord(
                ticket="flux-9",
                stage="implement" if variant == "harness" else "vanilla",
                model="claude-sonnet-5",
                effort="high",
                billing_mode="subscription",
                variant=variant,
                input_tokens=tokens,
            )
        )
    assert main(["metrics", "--path", str(path)]) == EXIT_OK
    out = capsys.readouterr().out
    assert "flux-9" in out
    assert "3.00x" in out, "the harness cost three times the baseline"
    assert "vanilla won 1/1" in out
