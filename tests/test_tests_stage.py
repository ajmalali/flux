"""The tests stage: what the model is told, and what the runner checks for itself.

The red step is the reason this stage exists, so most of this file is about the one
question a transcript cannot answer — do the tests the session wrote actually fail,
and do they fail for a reason the implementation can fix. The executor is scripted
throughout; no model appears in this file.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from flux.config import CONFIG_FILENAME, FluxConfig, TestsConfig
from flux.executor.types import ExecConfig, ExecResult, PromptPack, Usage
from flux.gates.spec import GateSpec
from flux.metrics.record import GateOutcome
from flux.proc import run_command
from flux.runner.artifact import validate_artifact
from flux.runner.checkpoint import CheckpointStore
from flux.runner.context import TicketContext
from flux.runner.loop import run_ticket
from flux.scaffold import init_repo
from flux.stages import TestsStage, build_pipeline
from flux.stages.tests import ARTIFACT_SPEC, check_artifact, modified_tests, red_step_problem
from flux.testrun import TestReport
from flux.tickets import load_ticket, ticket_path

PY = sys.executable

BRIEF = "Add greet(name) to greet.py returning 'hello, <name>'."

RED_TEST = """\
def test_greets_by_name():
    import greet

    assert greet.greet("ada") == "hello, ada"
"""

GREEN_TEST = """\
def test_arithmetic_still_works():
    assert 1 + 1 == 2
"""

BROKEN_TEST = """\
import greet


def test_greets_by_name():
    assert greet.greet("ada") == "hello, ada"
"""

IMPLEMENTATION = "def greet(name):\n    return f'hello, {name}'\n"

NOTES = "## Changed\n\ngreet.py\n\n## Deviations\n\nNone.\n\n## Discovered work\n\nNone.\n"


def artifact(files: list[str]) -> str:
    return json.dumps(
        {
            "test_files": files,
            "cases": [
                {"test": f"{path}::test_greets_by_name", "criterion": "greet returns a greeting"}
                for path in files
            ],
        },
        indent=2,
    )


def make(tmp_path: Path, **kwargs: object) -> tuple[TestsStage, TicketContext]:
    settings = FluxConfig(
        root=tmp_path,
        gates=(
            GateSpec(name="lint", kind="ruff", command=("true",)),
            GateSpec(name="test", kind="pytest", command=(PY, "-m", "pytest", "-q", "-rf")),
        ),
        stage_commits=False,
        **kwargs,  # pyright: ignore[reportArgumentType]
    )
    ticket = TicketContext(ticket_id="flux-1", root=tmp_path, brief=BRIEF)
    ticket.context_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "tests").mkdir(exist_ok=True)
    return TestsStage(settings=settings), ticket


def write(ticket: TicketContext, *, tests: dict[str, str], files: list[str] | None = None) -> None:
    """Do what an obedient tests session would: write the tests, then the artifact."""
    for name, body in tests.items():
        path = ticket.worktree / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    listed = list(tests) if files is None else files
    (ticket.context_dir / "tests.json").write_text(artifact(listed), encoding="utf-8")


def session(session_id: str = "s-1") -> ExecResult:
    return ExecResult(
        ok=True,
        text="done",
        session_id=session_id,
        model="claude-sonnet-5",
        effort="high",
        billing_mode="subscription",
        usage=Usage(input_tokens=10, output_tokens=5),
    )


# -- hydration -------------------------------------------------------------------


def test_hydration_is_deterministic(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path)
    assert stage.hydrate(ticket) == stage.hydrate(ticket)


def test_the_pack_carries_the_brief_and_the_red_rule(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path)
    pack = stage.hydrate(ticket)

    assert BRIEF in pack.context_pack
    assert "every one of those tests fails" in pack.prompt
    assert "collects cleanly" in pack.prompt


def test_the_pack_teaches_the_one_technique_the_red_rule_needs(tmp_path: Path) -> None:
    """Requiring an assertion failure for code that does not exist yet is unfair
    unless the session is told how: import inside the test."""
    stage, ticket = make(tmp_path)
    assert "INSIDE the test function" in stage.hydrate(ticket).system_prompt


def test_the_pack_names_where_tests_go_and_how_they_will_be_run(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path)
    prompt = stage.hydrate(ticket).prompt

    assert "tests/" in prompt
    assert "-m pytest -q -rf" in prompt


def test_the_pack_shows_the_artifact_shape_it_will_be_validated_against(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path)
    prompt = stage.hydrate(ticket).prompt

    assert "tests.json" in prompt
    assert "criterion" in prompt


def test_held_out_tests_are_mentioned_but_never_shown(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path)
    held = tmp_path / ".flux" / "held-out" / "flux-1"
    held.mkdir(parents=True)
    (held / "test_secret.py").write_text("SECRET_HELD_OUT_BODY = 1\n", encoding="utf-8")

    prompt = stage.hydrate(ticket).prompt

    assert "held-out tests you cannot see" in prompt
    assert "SECRET_HELD_OUT_BODY" not in prompt


# -- policy ----------------------------------------------------------------------


def test_the_session_can_only_write_tests(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path)
    (guard,) = stage.config(ticket).guards

    assert guard.decide("Write", {"file_path": str(tmp_path / "greet.py")})
    assert guard.decide("Write", {"file_path": str(tmp_path / "tests" / "test_a.py")}) == ""


def test_the_session_may_run_the_suite_it_is_judged_on(tmp_path: Path) -> None:
    """A headless session that cannot run the tests reasons about them instead."""
    stage, ticket = make(tmp_path)
    assert any("pytest" in tool for tool in stage.config(ticket).allowed_tools)


def test_the_context_directory_is_reachable_from_a_worktree(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path)
    assert ticket.context_dir in stage.config(ticket).add_dirs


def test_the_suite_is_not_a_gate_on_the_stage_that_makes_it_red(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path)
    names = [gate.name for gate in stage.gates(ticket)]

    assert "lint" in names
    assert "test" not in names


# -- the artifact contract -------------------------------------------------------


def test_an_empty_cases_map_is_invalid_and_therefore_retried(tmp_path: Path) -> None:
    """It satisfies required_keys, and tells the implement stage nothing."""
    _, ticket = make(tmp_path)
    payload = {"test_files": ["tests/test_a.py"], "cases": []}
    (ticket.context_dir / "tests.json").write_text(json.dumps(payload), encoding="utf-8")

    check = validate_artifact(ticket, ARTIFACT_SPEC)

    assert not check.ok
    assert "cases" in check.problem


def test_a_case_without_a_criterion_is_invalid() -> None:
    problem = check_artifact({"test_files": ["a.py"], "cases": [{"test": "a.py::b"}]})
    assert "criterion" in problem


def test_a_well_formed_artifact_validates() -> None:
    assert check_artifact(json.loads(artifact(["tests/test_a.py"]))) == ""


# -- the red step ----------------------------------------------------------------


def test_tests_that_fail_on_an_assertion_stand(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path)
    write(ticket, tests={"tests/test_greet.py": RED_TEST})

    outcome = stage.commit(ticket, session(), ())

    assert outcome.ok and not outcome.parked
    assert "verified red" in outcome.note


def test_the_red_run_is_stored_for_the_implement_stage(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path)
    write(ticket, tests={"tests/test_greet.py": RED_TEST})

    stage.commit(ticket, session(), ())

    payload = json.loads((ticket.context_dir / "tests.json").read_text(encoding="utf-8"))
    assert payload["red"]["failed"] == 1
    assert "test_greets_by_name" in payload["red_output"]
    assert payload["test_digests"]["tests/test_greet.py"]


def test_the_stored_red_output_does_not_carry_test_source(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path)
    marked = RED_TEST.replace("ada", "SECRET_TEST_LITERAL")
    write(ticket, tests={"tests/test_greet.py": marked})

    stage.commit(ticket, session(), ())

    payload = (ticket.context_dir / "tests.json").read_text(encoding="utf-8")
    assert "import greet" not in payload


def test_a_test_that_already_passes_is_not_a_red_step(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path)
    write(ticket, tests={"tests/test_greet.py": RED_TEST, "tests/test_ok.py": GREEN_TEST})

    outcome = stage.commit(ticket, session(), ())

    assert outcome.parked and outcome.reason == "red-step-failed"
    assert "already pass" in outcome.note


def test_a_collection_error_is_not_a_red_step(tmp_path: Path) -> None:
    """The module does not exist, so the failure is one no implementation can fix."""
    stage, ticket = make(tmp_path)
    write(ticket, tests={"tests/test_greet.py": BROKEN_TEST})

    outcome = stage.commit(ticket, session(), ())

    assert outcome.parked and outcome.reason == "red-step-failed"
    assert "errored instead of failing" in outcome.note


def test_the_evidence_is_stored_even_when_the_red_step_fails(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path)
    write(ticket, tests={"tests/test_greet.py": BROKEN_TEST})

    stage.commit(ticket, session(), ())

    payload = json.loads((ticket.context_dir / "tests.json").read_text(encoding="utf-8"))
    assert payload["red"]["collection_error"]


def test_an_artifact_naming_a_file_that_was_never_written_parks(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path)
    write(ticket, tests={"tests/test_greet.py": RED_TEST}, files=["tests/test_ghost.py"])

    outcome = stage.commit(ticket, session(), ())

    assert outcome.parked and outcome.reason == "tests-misplaced"


def test_a_test_written_outside_the_tests_directory_parks(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path)
    write(ticket, tests={"test_sneaky.py": RED_TEST})

    outcome = stage.commit(ticket, session(), ())

    assert outcome.parked and outcome.reason == "tests-misplaced"


def test_a_failed_gate_parks_before_the_red_step_is_even_asked(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path)
    write(ticket, tests={"tests/test_greet.py": RED_TEST})

    outcome = stage.commit(ticket, session(), (GateOutcome(name="lint", passed=False),))

    assert outcome.parked and outcome.reason == "gates-failed"


def test_a_repo_with_no_way_to_run_tests_parks_rather_than_claiming_red(tmp_path: Path) -> None:
    settings = FluxConfig(root=tmp_path, gates=(), stage_commits=False)
    ticket = TicketContext(ticket_id="flux-1", root=tmp_path, brief=BRIEF)
    ticket.context_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "tests").mkdir()
    write(ticket, tests={"tests/test_greet.py": RED_TEST})

    outcome = TestsStage(settings=settings).commit(ticket, session(), ())

    assert outcome.parked and outcome.reason == "no-test-command"


def test_red_step_problem_names_each_way_a_run_falls_short() -> None:
    assert "did not run" in red_step_problem(TestReport(ran=False))
    assert "no tests ran" in red_step_problem(TestReport(ran=True, summary="no tests ran in 0.1s"))
    assert red_step_problem(TestReport(ran=True, counts={"failed": 2})) == ""


# -- the pipeline ----------------------------------------------------------------


def test_the_shipping_pipeline_writes_tests_before_it_writes_code(tmp_path: Path) -> None:
    stage, _ = make(tmp_path)
    assert build_pipeline(stage.settings).names == ("tests", "implement")


# -- end to end: tests, then implement, in a real repo ----------------------------


@dataclass
class ScriptedExecutor:
    """Plays both stages: writes the tests, then the code and the handoff note."""

    ticket: TicketContext
    implementation: str = IMPLEMENTATION
    edit_tests_at_implement: str = ""
    """Content a misbehaving implement session writes over the test file."""

    calls: list[tuple[PromptPack, ExecConfig]] = field(
        default_factory=list[tuple[PromptPack, ExecConfig]]
    )

    def run(self, pack: PromptPack, cfg: ExecConfig) -> ExecResult:
        self.calls.append((pack, cfg))
        if "tests stage" in pack.system_prompt:
            write(self.ticket, tests={"tests/test_greet.py": RED_TEST})
        else:
            (self.ticket.worktree / "greet.py").write_text(self.implementation, encoding="utf-8")
            if self.edit_tests_at_implement:
                (self.ticket.worktree / "tests" / "test_greet.py").write_text(
                    self.edit_tests_at_implement, encoding="utf-8"
                )
            (self.ticket.context_dir / "impl-notes.md").write_text(NOTES, encoding="utf-8")
        return ExecResult(
            ok=True,
            text="done",
            session_id=f"session-{len(self.calls)}",
            model=cfg.model,
            effort=cfg.effort,
            billing_mode=cfg.billing_mode,
            usage=Usage(input_tokens=100, output_tokens=20),
            num_turns=3,
            pack_chars=pack.size_chars,
        )


def scratch_repo(tmp_path: Path) -> Path:
    root = tmp_path / "target"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='target'\n", encoding="utf-8")
    (root / "tests").mkdir()
    run_command(["git", "init", "-q", "-b", "main"], cwd=root)
    run_command(["git", "config", "user.email", "dev@example.com"], cwd=root)
    run_command(["git", "config", "user.name", "Dev"], cwd=root)
    init_repo(root)
    (root / ".flux" / CONFIG_FILENAME).write_text(
        "\n".join(
            [
                "schema_version = 1",
                'target = "python"',
                "[[gates]]",
                'name = "test"',
                'kind = "pytest"',
                f'command = ["{PY}", "-m", "pytest", "-q", "-rf"]',
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
    executor = ScriptedExecutor(ticket=ticket, **kwargs)  # pyright: ignore[reportArgumentType]
    return run_ticket(ticket, build_pipeline(settings), executor), ticket, executor


def test_a_ticket_flows_red_tests_then_green_implementation(tmp_path: Path) -> None:
    root = scratch_repo(tmp_path)

    result, _, executor = drive(root)

    assert result.completed
    assert result.stages_run == ("tests", "implement")
    assert (root / "greet.py").exists()
    assert len(executor.calls) == 2


def test_the_implement_session_is_handed_paths_and_failures_never_bodies(tmp_path: Path) -> None:
    root = scratch_repo(tmp_path)
    _, _, executor = drive(root)

    implement_pack = executor.calls[1][0].prompt

    assert "tests/test_greet.py" in implement_pack
    assert "test_greets_by_name" in implement_pack
    assert 'greet.greet("ada")' not in implement_pack


def test_the_implement_session_cannot_reach_the_tests(tmp_path: Path) -> None:
    root = scratch_repo(tmp_path)
    _, ticket, executor = drive(root)

    (guard,) = executor.calls[1][1].guards

    assert guard.decide("Read", {"file_path": str(ticket.worktree / "tests" / "test_greet.py")})


def test_a_test_edited_during_implement_fails_the_stage(tmp_path: Path) -> None:
    """The guard blocks the tool calls; the digest catches every other route."""
    root = scratch_repo(tmp_path)

    gamed = "def test_greets_by_name():\n    pass\n"
    result, ticket, _ = drive(root, edit_tests_at_implement=gamed)

    assert result.park is not None
    assert result.park.reason == "tests-modified"
    assert modified_tests(ticket) == ("tests/test_greet.py",)


def test_held_out_tests_run_at_implement_time(tmp_path: Path) -> None:
    root = scratch_repo(tmp_path)
    held = root / ".flux" / "held-out" / "flux-1"
    held.mkdir(parents=True)
    (held / "test_held.py").write_text(
        "def test_held():\n    import greet\n\n    assert greet.greet('x') == 'hello, x'\n",
        encoding="utf-8",
    )

    result, ticket, _ = drive(root)

    assert result.completed
    checkpoint = CheckpointStore(ticket.state_dir).read("implement")
    assert checkpoint is not None
    assert "held-out" in checkpoint.detail["gates"]


def test_an_implementation_that_only_satisfies_the_visible_test_is_caught(tmp_path: Path) -> None:
    root = scratch_repo(tmp_path)
    held = root / ".flux" / "held-out" / "flux-1"
    held.mkdir(parents=True)
    (held / "test_held.py").write_text(
        "def test_held():\n    import greet\n\n    assert greet.greet('bob') == 'hello, bob'\n",
        encoding="utf-8",
    )

    # Passes the one visible assertion and nothing else — the shape of a gamed ticket.
    result, _, _ = drive(root, implementation="def greet(name):\n    return 'hello, ada'\n")

    assert result.park is not None
    assert result.park.reason == "gates-failed"
    assert "held-out" in result.park.note


def test_the_tests_are_committed_before_the_implementation_is_written(tmp_path: Path) -> None:
    root = scratch_repo(tmp_path)
    drive(root)

    tags = run_command(["git", "tag", "--list"], cwd=root).stdout
    assert "flux/flux-1/tests" in tags
    assert "flux/flux-1/implement" in tags


def test_the_config_can_move_the_tests_directory(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path, tests=TestsConfig(dir="spec"))
    (guard,) = stage.config(ticket).guards

    assert guard.decide("Write", {"file_path": str(tmp_path / "spec" / "test_a.py")}) == ""
    assert guard.decide("Write", {"file_path": str(tmp_path / "tests" / "test_a.py")})
