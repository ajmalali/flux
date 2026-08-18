"""The M0 exit benchmark, without a model: a hand-written ticket through implement + gates.

Everything here is real except the session — the config is read from a ``flux.toml``
``flux init`` wrote, the gates are real subprocesses, the commit is a real commit, and
the metrics line is read back off disk. The executor is scripted because the benchmark
is about the *harness*: whether the pipeline carries a ticket from a brief to a gated,
committed change and an auditable cost record.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from flux.cli import EXIT_OK, EXIT_PARKED, main
from flux.config import CONFIG_FILENAME, FluxConfig
from flux.executor.types import ExecConfig, ExecResult, PromptPack, Usage
from flux.metrics.record import MetricsStore
from flux.proc import run_command
from flux.runner.checkpoint import CheckpointStore
from flux.runner.loop import run_ticket
from flux.scaffold import init_repo
from flux.stages import build_pipeline
from flux.tickets import load_ticket, ticket_path

PY = sys.executable

NOTES = """\
## Changed

`greet.py`: added `greet(name)` returning the required string.

## Deviations

None.

## Discovered work

None.
"""

BRIEF = "Add a greet(name) function to greet.py that returns 'hello, <name>'."


@dataclass
class ScriptedExecutor:
    """Stands in for the session: writes the files an obedient implement stage would.

    It is handed the same :class:`PromptPack` the real executor would get, and the
    tests assert on that pack — so the substitution does not hide the handoff.
    """

    worktree: Path
    context_dir: Path
    notes: str = NOTES
    source: str = "def greet(name):\n    return f'hello, {name}'\n"
    calls: list[tuple[PromptPack, ExecConfig]] = field(
        default_factory=list[tuple[PromptPack, ExecConfig]]
    )

    def run(self, pack: PromptPack, cfg: ExecConfig) -> ExecResult:
        self.calls.append((pack, cfg))
        if self.source:
            (self.worktree / "greet.py").write_text(self.source, encoding="utf-8")
        if self.notes:
            self.context_dir.mkdir(parents=True, exist_ok=True)
            (self.context_dir / "impl-notes.md").write_text(self.notes, encoding="utf-8")
        return ExecResult(
            ok=True,
            text="done",
            session_id=f"session-{len(self.calls)}",
            model=cfg.model,
            effort=cfg.effort,
            billing_mode=cfg.billing_mode,
            usage=Usage(input_tokens=1_200, output_tokens=300, cache_read_tokens=400),
            num_turns=4,
            tool_uses={"Read": 2, "Edit": 1},
            pack_chars=pack.size_chars,
        )


def scratch_repo(tmp_path: Path, *, gate_passes: bool = True) -> Path:
    """A target repo: git-initialised, ``flux init``-ed, with one real gate."""
    root = tmp_path / "target"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='target'\n", encoding="utf-8")
    run_command(["git", "init", "-q", "-b", "main"], cwd=root)
    run_command(["git", "config", "user.email", "dev@example.com"], cwd=root)
    run_command(["git", "config", "user.name", "Dev"], cwd=root)

    init_repo(root)
    green = "import greet; assert greet.greet('a') == 'hello, a'"
    check = green if gate_passes else "raise SystemExit(1)"
    (root / ".flux" / CONFIG_FILENAME).write_text(
        "\n".join(
            [
                "schema_version = 1",
                'target = "python"',
                "[[gates]]",
                'name = "test"',
                'kind = "pytest"',
                f'command = ["{PY}", "-c", "{check}"]',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    path = ticket_path(root, "flux-1")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(BRIEF, encoding="utf-8")
    return root


def drive(root: Path, **kwargs: object):
    settings = FluxConfig.load(root)
    ticket = load_ticket("flux-1", root=root, config=settings)
    executor = ScriptedExecutor(
        worktree=ticket.worktree,
        context_dir=ticket.context_dir,
        **kwargs,  # pyright: ignore[reportArgumentType]
    )
    return run_ticket(ticket, build_pipeline(settings), executor), ticket, executor


def test_a_hand_written_ticket_flows_through_implement_and_gates(tmp_path: Path) -> None:
    root = scratch_repo(tmp_path)

    result, ticket, executor = drive(root)

    assert result.completed
    assert result.stages_run == ("implement",)
    assert (root / "greet.py").exists()
    assert (ticket.context_dir / "impl-notes.md").exists()
    assert len(executor.calls) == 1


def test_the_session_was_given_the_brief_and_the_gate_it_would_face(tmp_path: Path) -> None:
    root = scratch_repo(tmp_path)
    _, _, executor = drive(root)

    pack, cfg = executor.calls[0]
    assert BRIEF in pack.prompt
    assert "impl-notes.md" in pack.prompt
    assert cfg.model and cfg.effort  # never an SDK default (ADR 0007)
    assert cfg.cwd == root.resolve()


def test_the_checkpoint_records_the_validated_artifact(tmp_path: Path) -> None:
    root = scratch_repo(tmp_path)
    _, ticket, _ = drive(root)

    checkpoint = CheckpointStore(ticket.state_dir).read("implement")
    assert checkpoint is not None
    assert checkpoint.ok
    assert checkpoint.artifact_path == "impl-notes.md"
    assert len(checkpoint.artifact_digest) == 64


def test_the_work_lands_as_a_tagged_commit(tmp_path: Path) -> None:
    root = scratch_repo(tmp_path)
    drive(root)

    tags = run_command(["git", "tag", "--list"], cwd=root)
    assert "flux/flux-1/implement" in tags.stdout
    files = run_command(["git", "show", "--name-only", "--pretty=", "HEAD"], cwd=root)
    assert "greet.py" in files.stdout
    assert ".flux/context/flux-1/impl-notes.md" in files.stdout


def test_state_is_committed_but_checkpoints_are_not(tmp_path: Path) -> None:
    """ADR 0006: artifacts are the durable record; machine state is rebuildable."""
    root = scratch_repo(tmp_path)
    drive(root)

    tracked = run_command(["git", "ls-files"], cwd=root).stdout
    assert ".flux/context/flux-1/ticket.md" in tracked
    assert ".flux/state" not in tracked
    assert ".flux/usage" not in tracked


def test_metrics_record_the_stage_with_its_gate_verdict(tmp_path: Path) -> None:
    root = scratch_repo(tmp_path)
    _, ticket, _ = drive(root)

    records = MetricsStore(ticket.metrics_path).read()
    assert len(records) == 1
    line = records[0]
    assert (line.ticket, line.stage, line.ok) == ("flux-1", "implement", True)
    assert line.total_tokens == 1_900
    assert line.pack_chars > 0
    assert [(g.name, g.passed) for g in line.gates] == [("test", True)]
    assert line.exploratory_calls == 2


def test_flux_metrics_prints_the_per_stage_table(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = scratch_repo(tmp_path)
    _, ticket, _ = drive(root)

    assert main(["metrics", "--path", str(ticket.metrics_path)]) == EXIT_OK
    printed = capsys.readouterr().out
    assert "implement" in printed


def test_a_rerun_skips_the_completed_stage(tmp_path: Path) -> None:
    """Resume is rerun (design.md §1): the second invocation costs nothing."""
    root = scratch_repo(tmp_path)
    drive(root)

    second, ticket, executor = drive(root)

    assert second.completed
    assert second.stages_run == ()
    assert executor.calls == []
    assert len(MetricsStore(ticket.metrics_path).read()) == 1


def test_a_failing_gate_parks_the_ticket_for_a_human(tmp_path: Path) -> None:
    root = scratch_repo(tmp_path, gate_passes=False)

    result, ticket, _ = drive(root)

    assert result.status == "parked"
    assert result.park is not None
    assert result.park.reason == "gates-failed"
    assert "test" in result.park.note
    assert not run_command(["git", "log", "--oneline"], cwd=root).stdout.strip()
    records = MetricsStore(ticket.metrics_path).read()
    assert records[0].ok is False


def test_a_parked_ticket_stays_parked_until_a_human_clears_it(tmp_path: Path) -> None:
    root = scratch_repo(tmp_path, gate_passes=False)
    drive(root)

    again, _, executor = drive(root)

    assert again.status == "parked"
    assert executor.calls == []


def test_a_missing_artifact_costs_exactly_one_retry_then_parks(tmp_path: Path) -> None:
    root = scratch_repo(tmp_path)

    result, ticket, executor = drive(root, notes="")

    assert result.status == "parked"
    assert result.park is not None
    assert result.park.reason == "artifact-invalid"
    assert len(executor.calls) == 2
    assert "Required artifact missing" in executor.calls[1][0].prompt
    assert len(MetricsStore(ticket.metrics_path).read()) == 2


def test_notes_missing_a_required_heading_are_not_a_valid_handoff(tmp_path: Path) -> None:
    root = scratch_repo(tmp_path)

    partial = "## Changed\n\nAdded greet() to greet.py, which is a fair amount of prose.\n"
    result, _, _ = drive(root, notes=partial)

    assert result.status == "parked"
    assert result.park is not None
    assert "Deviations" in result.park.note


def test_the_cli_reports_a_park_with_a_distinct_exit_code(tmp_path: Path) -> None:
    root = scratch_repo(tmp_path, gate_passes=False)
    settings = FluxConfig.load(root)
    ticket = load_ticket("flux-1", root=root, config=settings)
    CheckpointStore(ticket.state_dir).save_state(
        CheckpointStore(ticket.state_dir).load_state("flux-1")
    )

    assert main(["status", "flux-1", "--root", str(root)]) == EXIT_OK
    assert main(["run", "flux-1", "--root", str(root), "--dry-run"]) == EXIT_OK


def test_dry_run_shows_the_pack_without_spending_anything(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = scratch_repo(tmp_path)

    assert main(["run", "flux-1", "--root", str(root), "--dry-run"]) == EXIT_OK

    printed = capsys.readouterr().out
    assert "next:    implement" in printed
    assert BRIEF in printed
    assert not (root / ".flux" / "usage" / "metrics.jsonl").exists()
    assert not (root / "greet.py").exists()


def test_dry_run_on_a_parked_ticket_says_so(tmp_path: Path) -> None:
    root = scratch_repo(tmp_path, gate_passes=False)
    drive(root)
    assert main(["run", "flux-1", "--root", str(root), "--dry-run"]) == EXIT_PARKED
