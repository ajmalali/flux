"""The implement stage: what the model is told, and what decides whether it stood.

Hydration is pure code over files, so the whole of "did the handoff work?" is a
pytest question (design.md §2, Rule 3) — no model appears in this file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from flux.config import FluxConfig, StageProfile
from flux.executor.types import ExecResult, Usage
from flux.gates.spec import GateSpec
from flux.metrics.record import GateOutcome
from flux.proc import run_command
from flux.runner.context import TicketContext
from flux.runner.stage import Outcome
from flux.stages.implement import NOTES_SPEC, ImplementStage

BRIEF = "Add a --json flag to `report` so it can be piped."


def make(tmp_path: Path, **kwargs: object) -> tuple[ImplementStage, TicketContext]:
    settings = FluxConfig(
        root=tmp_path,
        gates=(GateSpec(name="test", kind="pytest", command=("pytest", "-q")),),
        **kwargs,  # pyright: ignore[reportArgumentType]
    )
    ticket = TicketContext(ticket_id="flux-1", root=tmp_path, brief=BRIEF)
    ticket.context_dir.mkdir(parents=True, exist_ok=True)
    return ImplementStage(settings=settings), ticket


def result(session_id: str = "s-1") -> ExecResult:
    return ExecResult(
        ok=True,
        text="done",
        session_id=session_id,
        model="claude-sonnet-5",
        effort="high",
        billing_mode="subscription",
        usage=Usage(input_tokens=10, output_tokens=5),
    )


def commit_detail(outcome: Outcome) -> dict[str, object]:
    """The stage-commit record the stage persisted into its checkpoint detail."""
    commit = outcome.detail["commit"]
    assert isinstance(commit, dict)
    return cast(dict[str, object], commit)


def git_repo(path: Path) -> Path:
    run_command(["git", "init", "-q", "-b", "main"], cwd=path)
    return path


# -- hydration -------------------------------------------------------------------


def test_hydration_is_deterministic(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path)
    assert stage.hydrate(ticket) == stage.hydrate(ticket)


def test_the_pack_carries_the_ticket_brief(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path)
    assert BRIEF in stage.hydrate(ticket).context_pack


def test_optional_context_files_are_folded_in_when_present(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path)
    (ticket.context_dir / "context-pack.md").write_text("relevant: src/report.py", "utf-8")
    (ticket.context_dir / "plan-summary.md").write_text("ADR 0011 pins the flag name", "utf-8")

    pack = stage.hydrate(ticket)
    assert "src/report.py" in pack.context_pack
    assert "ADR 0011" in pack.plan_summary


def test_absent_context_files_are_normal_not_fatal(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path)
    pack = stage.hydrate(ticket)
    assert pack.plan_summary == ""
    assert BRIEF in pack.prompt


def test_the_pack_names_the_artifact_and_its_headings(tmp_path: Path) -> None:
    """Rule 1 is enforced runner-side, but the prompt has to make it achievable."""
    stage, ticket = make(tmp_path)
    prompt = stage.hydrate(ticket).prompt
    assert str(NOTES_SPEC.resolve(ticket)) in prompt
    for heading in NOTES_SPEC.required_sections:
        assert f"## {heading}" in prompt


def test_the_pack_names_the_gates_that_will_judge_it(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path)
    assert "`pytest -q`" in stage.hydrate(ticket).stage_tail


def test_an_ungated_repo_is_told_so_rather_than_left_to_assume(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path)
    bare = ImplementStage(settings=FluxConfig(root=tmp_path, gates=()))
    assert "No gates are configured" in bare.hydrate(ticket).stage_tail
    assert "No gates" not in stage.hydrate(ticket).stage_tail


def test_the_tests_artifact_is_sliced_not_pasted(tmp_path: Path) -> None:
    """Reference-and-resolve (design.md §2): test paths and the red run, never bodies."""
    stage, ticket = make(tmp_path)
    (ticket.context_dir / "tests.json").write_text(
        json.dumps(
            {
                "test_files": ["tests/test_report.py"],
                "red_output": "1 failed",
                "cases": {"json flag": "tests/test_report.py::test_json"},
                "test_source": "def test_json(): assert report(json=True) == {}",
                "transcript": "a long chatty transcript",
            }
        ),
        encoding="utf-8",
    )

    tail = stage.hydrate(ticket).stage_tail
    assert "tests/test_report.py" in tail
    assert "1 failed" in tail
    assert "test_source" not in tail
    assert "transcript" not in tail


def test_no_tests_artifact_means_no_tests_section(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path)
    assert "Tests already written" not in stage.hydrate(ticket).stage_tail


def test_the_system_prompt_states_the_rules_the_harness_enforces(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path)
    system = stage.hydrate(ticket).system_prompt
    assert "gates" in system.lower()
    assert "carried forward" in system
    assert "delete tests" in system


# -- policy ----------------------------------------------------------------------


def test_model_and_effort_come_from_the_repo_config(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path)
    cfg = stage.config(ticket)
    profile = stage.settings.profile("implement")
    assert (cfg.model, cfg.effort) == (profile.model, profile.effort)
    assert cfg.permission_mode == "acceptEdits"
    assert cfg.cwd == ticket.worktree


def test_a_configured_profile_overrides_the_default(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path)
    tuned = ImplementStage(
        settings=FluxConfig(
            root=tmp_path,
            stages={"implement": StageProfile(model="claude-opus-5", effort="max", max_turns=3)},
        )
    )
    assert tuned.config(ticket).max_turns == 3
    assert stage.config(ticket).max_turns == 40


def test_the_stage_declares_its_required_artifact(tmp_path: Path) -> None:
    stage, _ = make(tmp_path)
    spec = stage.required_artifact()
    assert spec is not None
    assert spec.path == "impl-notes.md"
    assert spec.kind == "text"


def test_gates_are_built_from_the_configured_suite(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path)
    assert [g.name for g in stage.gates(ticket)] == ["test"]


# -- verification ----------------------------------------------------------------


def test_green_gates_make_the_stage_stand(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path, stage_commits=False)
    outcome = stage.commit(ticket, result(), [GateOutcome(name="test", passed=True)])
    assert outcome.ok and not outcome.parked
    assert outcome.detail["gates"] == ["test"]
    assert outcome.detail["session_id"] == "s-1"


def test_a_failed_gate_parks_with_the_reason_in_the_note(tmp_path: Path) -> None:
    """At M0 there is no fix stage to route to, so re-prompting would only burn budget."""
    stage, ticket = make(tmp_path, stage_commits=False)
    gates = [
        GateOutcome(name="lint", passed=True),
        GateOutcome(name="test", passed=False, detail="1 failed, 4 passed"),
    ]

    outcome = stage.commit(ticket, result(), gates)

    assert outcome.parked and not outcome.ok
    assert outcome.reason == "gates-failed"
    assert "test" in outcome.note
    assert "1 failed" in outcome.note
    assert outcome.detail["failed_gates"] == ["test"]


def test_a_failed_gate_leaves_no_stage_commit(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path)
    git_repo(tmp_path)
    (tmp_path / "work.py").write_text("x = 1\n", encoding="utf-8")

    stage.commit(ticket, result(), [GateOutcome(name="test", passed=False)])

    log = run_command(["git", "log", "--oneline"], cwd=tmp_path)
    assert log.returncode != 0 or not log.stdout.strip()


def test_standing_records_a_tagged_commit(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path)
    git_repo(tmp_path)
    (tmp_path / "work.py").write_text("x = 1\n", encoding="utf-8")

    outcome = stage.commit(ticket, result(), [GateOutcome(name="test", passed=True)])

    commit = commit_detail(outcome)
    assert commit["committed"] is True
    assert commit["tag"] == "flux/flux-1/implement"
    tags = run_command(["git", "tag", "--list"], cwd=tmp_path)
    assert "flux/flux-1/implement" in tags.stdout


def test_stage_commits_can_be_turned_off(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path, stage_commits=False)
    git_repo(tmp_path)
    (tmp_path / "work.py").write_text("x = 1\n", encoding="utf-8")

    outcome = stage.commit(ticket, result(), [GateOutcome(name="test", passed=True)])

    commit = commit_detail(outcome)
    assert commit["committed"] is False
    assert run_command(["git", "log", "--oneline"], cwd=tmp_path).stdout.strip() == ""


def test_a_worktree_that_is_not_a_repo_records_the_problem_but_still_stands(
    tmp_path: Path,
) -> None:
    """Good work that passed its gates must not be thrown away over bookkeeping."""
    stage, ticket = make(tmp_path)
    outcome = stage.commit(ticket, result(), [GateOutcome(name="test", passed=True)])

    assert outcome.ok and not outcome.parked
    assert "not a git repository" in str(commit_detail(outcome)["problem"])


def test_the_session_may_run_exactly_the_gates_it_will_be_judged_by(tmp_path: Path) -> None:
    """A headless session cannot answer a permission prompt, so "run the gates" needs this."""
    stage, ticket = make(tmp_path)
    assert stage.config(ticket).allowed_tools == ("Bash(pytest -q:*)",)


def test_no_gates_means_no_bash_permission_is_granted(tmp_path: Path) -> None:
    stage = ImplementStage(settings=FluxConfig(root=tmp_path, gates=()))
    ticket = TicketContext(ticket_id="flux-1", root=tmp_path, brief=BRIEF)
    assert stage.config(ticket).allowed_tools == ()
