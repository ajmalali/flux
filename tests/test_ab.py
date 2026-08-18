"""The A/B baseline arm: what a vanilla sample is given, and what it refuses to do.

No model appears here. Whether the baseline is *fair* is decided entirely by what
`flux.ab` builds before the session starts — the pack, the config, and the refusal —
so all three are plain assertions over pure code (design.md §3, ADR 0008).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from flux.ab import VANILLA_VARIANT, run_vanilla, vanilla_config, vanilla_pack
from flux.config import FluxConfig, StageProfile
from flux.errors import FluxError
from flux.executor.types import ExecConfig, ExecResult, PromptPack, Usage
from flux.gates.spec import GateSpec
from flux.metrics.record import GateOutcome, MetricsStore
from flux.runner.checkpoint import Checkpoint, CheckpointStore
from flux.runner.context import TicketContext

BRIEF = "Add a --json flag to `report` so it can be piped."


@dataclass
class RecordingExecutor:
    """Captures what the baseline session was handed, and reports a fixed usage."""

    calls: list[tuple[PromptPack, ExecConfig]] = field(
        default_factory=list[tuple[PromptPack, ExecConfig]]
    )
    ok: bool = True

    def run(self, pack: PromptPack, cfg: ExecConfig) -> ExecResult:
        self.calls.append((pack, cfg))
        return ExecResult(
            ok=self.ok,
            text="done",
            session_id="vanilla-1",
            model=cfg.model,
            effort=cfg.effort,
            billing_mode=cfg.billing_mode,
            usage=Usage(input_tokens=100, output_tokens=40, cache_read_tokens=9_000),
            num_turns=3,
        )


@dataclass
class StubGate:
    """A gate whose verdict the test picks."""

    name: str = "test"
    passed: bool = True

    def run(self, worktree: Path) -> GateOutcome:
        return GateOutcome(name=self.name, passed=self.passed)


def make(tmp_path: Path, **kwargs: object) -> tuple[FluxConfig, TicketContext]:
    settings = FluxConfig(
        root=tmp_path,
        gates=(GateSpec(name="test", kind="pytest", command=("pytest", "-q")),),
        **kwargs,  # pyright: ignore[reportArgumentType]
    )
    ticket = TicketContext(ticket_id="flux-1", root=tmp_path, brief=BRIEF)
    ticket.context_dir.mkdir(parents=True, exist_ok=True)
    return settings, ticket


def test_pack_is_the_ticket_and_nothing_else(tmp_path: Path) -> None:
    """The baseline gets the brief. No pack, no repo map, no stage framing."""
    _, ticket = make(tmp_path)
    pack = vanilla_pack(ticket)
    assert pack.prompt == BRIEF
    assert pack.system_prompt == ""
    assert pack.stage_tail == ""


def test_baseline_mirrors_the_implement_profile(tmp_path: Path) -> None:
    """Same model and effort, so the comparison isolates the harness, not the model."""
    settings, ticket = make(tmp_path)
    assert vanilla_config(ticket, settings).model == settings.profile("implement").model
    assert vanilla_config(ticket, settings).effort == settings.profile("implement").effort


def test_rerouting_implement_reroutes_the_baseline(tmp_path: Path) -> None:
    """The mirror is live: changing the stage's model must change the baseline's too.

    A copy taken at parse time would leave the baseline on last month's model and turn
    the harness-vs-vanilla comparison into a model comparison without anyone noticing.
    """
    stages = dict(FluxConfig(root=tmp_path).stages)
    stages["implement"] = StageProfile(model="claude-opus-5", effort="max")
    settings, ticket = make(tmp_path, stages=stages)
    cfg = vanilla_config(ticket, settings)
    assert (cfg.model, cfg.effort) == ("claude-opus-5", "max")


def test_explicit_vanilla_profile_breaks_the_mirror(tmp_path: Path) -> None:
    stages = dict(FluxConfig(root=tmp_path).stages)
    stages["vanilla"] = StageProfile(model="claude-haiku-4-5-20251001", effort="low")
    settings, ticket = make(tmp_path, stages=stages)
    assert vanilla_config(ticket, settings).model == "claude-haiku-4-5-20251001"


def test_baseline_may_run_its_own_gates(tmp_path: Path) -> None:
    """The same pre-approval the implement stage gets.

    T4 measured what a headless session does when it cannot run the gates it is told
    about: it argues instead of measuring. Handicapping the baseline that way would
    win the comparison by rigging it.
    """
    settings, ticket = make(tmp_path)
    assert vanilla_config(ticket, settings).allowed_tools == ("Bash(pytest -q:*)",)


def test_run_records_a_vanilla_line_with_gate_results(tmp_path: Path) -> None:
    settings, ticket = make(tmp_path)
    executor = RecordingExecutor()
    store = MetricsStore(ticket.metrics_path)

    result = run_vanilla(ticket, settings, executor, metrics=store, gates=(StubGate(),))

    assert result.ok
    (line,) = store.read()
    assert line.variant == VANILLA_VARIANT
    assert line.stage == "vanilla"
    assert line.ticket == "flux-1"
    assert [g.name for g in line.gates] == ["test"]
    assert line.output_tokens == 40


def test_a_red_gate_makes_the_sample_a_failure(tmp_path: Path) -> None:
    """Vanilla is judged by the same gates as the harness, not by its own report."""
    settings, ticket = make(tmp_path)
    store = MetricsStore(ticket.metrics_path)

    result = run_vanilla(
        ticket, settings, RecordingExecutor(), metrics=store, gates=(StubGate(passed=False),)
    )

    assert not result.ok
    assert not result.gates_passed


def test_baseline_writes_no_checkpoint(tmp_path: Path) -> None:
    """A sample is a measurement, not a pipeline run: it must not look like a done stage."""
    settings, ticket = make(tmp_path)
    run_vanilla(
        ticket,
        settings,
        RecordingExecutor(),
        metrics=MetricsStore(ticket.metrics_path),
        gates=(),
    )
    assert CheckpointStore(ticket.state_dir).completed_stages() == frozenset()


def test_refuses_a_worktree_the_harness_already_worked(tmp_path: Path) -> None:
    """Spending nothing is the point: the refusal happens before the session starts."""
    settings, ticket = make(tmp_path)
    CheckpointStore(ticket.state_dir).write(Checkpoint(stage="implement", ok=True))
    executor = RecordingExecutor()

    with pytest.raises(FluxError, match="already run through the harness"):
        run_vanilla(ticket, settings, executor, metrics=MetricsStore(ticket.metrics_path))

    assert executor.calls == []
    assert not ticket.metrics_path.exists()


def test_force_measures_anyway(tmp_path: Path) -> None:
    settings, ticket = make(tmp_path)
    CheckpointStore(ticket.state_dir).write(Checkpoint(stage="implement", ok=True))
    result = run_vanilla(
        ticket,
        settings,
        RecordingExecutor(),
        metrics=MetricsStore(ticket.metrics_path),
        gates=(),
        force=True,
    )
    assert result.record.variant == VANILLA_VARIANT


def test_a_failed_stage_does_not_count_as_harness_work(tmp_path: Path) -> None:
    """Only a checkpoint that *stood* means the tree has the harness's answer in it."""
    settings, ticket = make(tmp_path)
    CheckpointStore(ticket.state_dir).write(Checkpoint(stage="implement", ok=False))
    result = run_vanilla(
        ticket, settings, RecordingExecutor(), metrics=MetricsStore(ticket.metrics_path), gates=()
    )
    assert result.record.ticket == "flux-1"


def test_gates_default_to_the_configured_suite(tmp_path: Path) -> None:
    """Not passing ``gates`` runs the repo's real suite — the caller does not choose."""
    settings, ticket = make(tmp_path)
    result = run_vanilla(
        ticket, settings, RecordingExecutor(), metrics=MetricsStore(ticket.metrics_path)
    )
    assert [g.name for g in result.gates] == ["test"]
    # The real pytest gate cannot pass in an empty tmp repo; what matters is that it ran.
    assert not result.gates_passed
