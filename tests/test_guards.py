"""The PreToolUse guards: what each stage cannot touch, decided without a session.

The policy is pure data and the decision is a pure function, so ADR 0005's structural
hardening is provable in plain pytest — which is the point of keeping it on the flux
side of the executor seam.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from flux.config import FluxConfig
from flux.errors import ConfigError
from flux.executor.guard import EDIT_TOOLS, PathGuard, guarded_dirs
from flux.executor.sdk import build_hooks, guard_hook
from flux.executor.types import ExecConfig
from flux.gates.spec import GateSpec
from flux.runner.context import TicketContext
from flux.stages.guards import source_stage_guard, tests_stage_guard


def make(tmp_path: Path) -> tuple[FluxConfig, TicketContext]:
    settings = FluxConfig(
        root=tmp_path,
        gates=(GateSpec(name="test", kind="pytest", command=("pytest", "-q")),),
    )
    ticket = TicketContext(ticket_id="flux-1", root=tmp_path, brief="do the thing")
    return settings, ticket


def decide(guard: PathGuard, tool: str, path: Path | str) -> str:
    return guard.decide(tool, {"file_path": str(path)})


# -- the deny shape: implement and fix may not reach the tests --------------------


def test_the_implement_guard_blocks_writing_a_test(tmp_path: Path) -> None:
    settings, ticket = make(tmp_path)
    guard = source_stage_guard(ticket, settings)

    problem = decide(guard, "Edit", tmp_path / "tests" / "test_greet.py")

    assert problem
    assert "may not read or change them" in problem


def test_the_implement_guard_blocks_reading_a_test_too(tmp_path: Path) -> None:
    """Reading the assertion is how a session writes code shaped to the assertion."""
    settings, ticket = make(tmp_path)

    assert decide(source_stage_guard(ticket, settings), "Read", tmp_path / "tests" / "test_a.py")


def test_a_test_beside_the_code_it_tests_is_still_a_test(tmp_path: Path) -> None:
    settings, ticket = make(tmp_path)
    guard = source_stage_guard(ticket, settings)

    assert decide(guard, "Write", tmp_path / "src" / "pkg" / "test_helpers.py")
    assert decide(guard, "Write", tmp_path / "src" / "conftest.py")


def test_the_implement_guard_leaves_the_implementation_alone(tmp_path: Path) -> None:
    settings, ticket = make(tmp_path)
    guard = source_stage_guard(ticket, settings)

    assert decide(guard, "Edit", tmp_path / "src" / "greet.py") == ""
    assert decide(guard, "Read", tmp_path / "README.md") == ""


def test_held_out_tests_are_out_of_reach_of_the_implementer(tmp_path: Path) -> None:
    settings, ticket = make(tmp_path)
    held_out = tmp_path / ".flux" / "held-out" / "flux-1" / "test_extra.py"

    assert decide(source_stage_guard(ticket, settings), "Read", held_out)


def test_a_relative_path_is_resolved_against_the_worktree(tmp_path: Path) -> None:
    """Tool input names paths relative to cwd as often as not."""
    settings, ticket = make(tmp_path)

    assert decide(source_stage_guard(ticket, settings), "Edit", "tests/test_greet.py")


def test_an_unguarded_tool_is_not_the_guards_business(tmp_path: Path) -> None:
    settings, ticket = make(tmp_path)

    assert source_stage_guard(ticket, settings).decide("Bash", {"command": "pytest"}) == ""


# -- the allow-only shape: the tests stage writes tests, and nothing else ---------


def test_the_tests_guard_blocks_writing_the_implementation(tmp_path: Path) -> None:
    settings, ticket = make(tmp_path)
    guard = tests_stage_guard(ticket, settings)

    problem = decide(guard, "Write", tmp_path / "src" / "greet.py")

    assert "may only write test files" in problem


def test_the_tests_guard_allows_the_tests_dir_and_the_handoff_artifact(tmp_path: Path) -> None:
    settings, ticket = make(tmp_path)
    guard = tests_stage_guard(ticket, settings)

    assert decide(guard, "Write", tmp_path / "tests" / "test_greet.py") == ""
    assert decide(guard, "Write", ticket.context_dir / "tests.json") == ""


def test_the_tests_guard_does_not_stop_the_stage_reading_the_code(tmp_path: Path) -> None:
    """A test written without reading the code it exercises is a worse test."""
    settings, ticket = make(tmp_path)

    assert decide(tests_stage_guard(ticket, settings), "Read", tmp_path / "src" / "greet.py") == ""


# -- the guard object itself ------------------------------------------------------


def test_a_guard_that_forbids_nothing_is_a_configuration_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="forbids nothing"):
        PathGuard(name="empty", reason="because", root=tmp_path)


def test_a_guard_needs_a_reason_the_model_can_act_on(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="reason"):
        PathGuard(name="mute", reason="  ", deny_dirs=(tmp_path,))


def test_guarded_directories_must_be_absolute() -> None:
    with pytest.raises(ConfigError, match="absolute"):
        PathGuard(name="relative", reason="no", deny_dirs=(Path("tests"),))


def test_guarded_dirs_drops_absences_and_deduplicates(tmp_path: Path) -> None:
    assert guarded_dirs(tmp_path, None, tmp_path) == (tmp_path.resolve(),)


def test_two_guards_may_not_share_a_name(tmp_path: Path) -> None:
    guard = PathGuard(name="same", reason="no", deny_dirs=(tmp_path,))
    with pytest.raises(ConfigError, match="unique"):
        ExecConfig(model="m", effort="high", guards=(guard, guard))


# -- the SDK bridge ---------------------------------------------------------------


def test_guards_compile_into_a_pretooluse_hook(tmp_path: Path) -> None:
    settings, ticket = make(tmp_path)
    cfg = ExecConfig(model="m", effort="high", guards=(source_stage_guard(ticket, settings),))

    hooks = build_hooks(cfg)

    assert hooks is not None
    matchers = hooks["PreToolUse"]
    assert len(matchers) == 1
    assert set(matchers[0].matcher.split("|")) >= set(EDIT_TOOLS)


def test_a_session_with_no_guards_gets_no_hooks() -> None:
    assert build_hooks(ExecConfig(model="m", effort="high")) is None


def test_the_hook_denies_the_call_and_says_why(tmp_path: Path) -> None:
    settings, ticket = make(tmp_path)
    hook = guard_hook(source_stage_guard(ticket, settings))

    payload = {
        "tool_name": "Edit",
        "tool_input": {"file_path": str(tmp_path / "tests" / "test_greet.py")},
    }
    decision = asyncio.run(hook(payload, None, {}))

    specific = decision["hookSpecificOutput"]
    assert specific["permissionDecision"] == "deny"
    assert "test_greet.py" in specific["permissionDecisionReason"]


def test_the_hook_lets_ordinary_work_through(tmp_path: Path) -> None:
    settings, ticket = make(tmp_path)
    hook = guard_hook(source_stage_guard(ticket, settings))

    payload = {"tool_name": "Edit", "tool_input": {"file_path": str(tmp_path / "greet.py")}}

    assert asyncio.run(hook(payload, None, {})) == {}
