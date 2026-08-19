"""The fix stage: the smallest pack in the pipeline, and the same hardening as implement.

Two properties are load-bearing and both are asserted here rather than described. The
first is *reference, not paste* (design.md §2): the pack is the unresolved findings and
the hunks they point at, so it is smaller than the review's pack even though it runs
after it. The second is that the fix stage is the implement stage's twin where it
matters — same guard, same digest backstop, same gates — because it is the second place
a session is told "make the gate go green".
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from flux.config import FluxConfig, ReviewConfig, TestsConfig
from flux.errors import ParkSignal
from flux.executor.types import ExecResult, Usage
from flux.gates.spec import GateSpec
from flux.metrics.record import GateOutcome
from flux.proc import run_command
from flux.runner.artifact import validate_artifact
from flux.runner.context import TicketContext
from flux.stages.fix import FixStage, resolution_check
from flux.stages.implement import ImplementStage
from flux.stages.review import ReviewStage

BRIEF = "Add greet(name) to greet.py returning 'hello, <name>'."

BASE = "def greet(name):\n    return 'hello, ' + name\n"
TEST_SOURCE = "def test_greets():\n    import greet\n\n    assert greet.greet('ada')\n"

TESTS_ARTIFACT: dict[str, object] = {
    "test_files": ["tests/test_greet.py"],
    "cases": [{"test": "tests/test_greet.py::test_greets", "criterion": "greet greets"}],
    "test_digests": {},
}


def git(root: Path, *args: str) -> None:
    run = run_command(["git", *args], cwd=root)
    assert run.returncode == 0, run.output


def make(
    tmp_path: Path, *, review: ReviewConfig | None = None
) -> tuple[FixStage, TicketContext, FluxConfig]:
    root = tmp_path / "target"
    (root / "tests").mkdir(parents=True)
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "dev@example.com")
    git(root, "config", "user.name", "Dev")
    (root / "pyproject.toml").write_text("[project]\nname='target'\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "base")

    settings = FluxConfig(
        root=root,
        gates=(GateSpec(name="test", kind="pytest", command=("true",)),),
        stage_commits=False,
        tests=TestsConfig(),
        review=review if review is not None else ReviewConfig(),
    )
    ticket = TicketContext(ticket_id="flux-1", root=root, brief=BRIEF)
    ticket.context_dir.mkdir(parents=True, exist_ok=True)

    (root / "tests" / "test_greet.py").write_text(TEST_SOURCE, encoding="utf-8")
    (root / "greet.py").write_text(BASE, encoding="utf-8")
    (root / "helper.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "flux(flux-1): implement")
    git(root, "tag", "-f", "flux/flux-1/implement")

    (ticket.context_dir / "tests.json").write_text(json.dumps(TESTS_ARTIFACT), encoding="utf-8")
    return FixStage(settings=settings), ticket, settings


def write_review(ticket: TicketContext, findings: list[dict[str, object]]) -> None:
    (ticket.context_dir / "review.json").write_text(
        json.dumps({"summary": "a verdict", "findings": findings}, indent=2), encoding="utf-8"
    )


def finding(**kwargs: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": "R1",
        "severity": "blocker",
        "axis": "correctness",
        "file": "greet.py",
        "line": 2,
        "finding": "greet raises TypeError when name is None",
        "suggestion": "coerce or reject None",
        "resolved": False,
        "resolution": "",
    }
    base.update(kwargs)
    return base


def session() -> ExecResult:
    return ExecResult(
        ok=True,
        text="done",
        session_id="s-1",
        model="claude-sonnet-5",
        effort="high",
        billing_mode="subscription",
        usage=Usage(input_tokens=10, output_tokens=5),
    )


def resolve(ticket: TicketContext, note: str = "guarded the None case") -> None:
    payload = json.loads((ticket.context_dir / "review.json").read_text())
    for entry in payload["findings"]:
        entry["resolved"] = True
        entry["resolution"] = note
    (ticket.context_dir / "review.json").write_text(json.dumps(payload), encoding="utf-8")


# -- hydration -------------------------------------------------------------------


def test_hydration_is_deterministic(tmp_path: Path) -> None:
    stage, ticket, _ = make(tmp_path)
    write_review(ticket, [finding()])
    assert stage.hydrate(ticket) == stage.hydrate(ticket)


def test_the_pack_is_the_findings_and_the_hunks_they_point_at(tmp_path: Path) -> None:
    stage, ticket, _ = make(tmp_path)
    write_review(ticket, [finding()])

    prompt = stage.hydrate(ticket).prompt

    assert "R1" in prompt
    assert "greet raises TypeError" in prompt
    assert "'hello, ' + name" in prompt, "the hunk the finding points at"
    assert "def helper()" not in prompt, "an untouched-by-findings file is not carried"


def test_a_resolved_finding_is_not_carried_again(tmp_path: Path) -> None:
    stage, ticket, _ = make(tmp_path)
    write_review(
        ticket,
        [
            finding(),
            finding(
                id="R2", line=1, finding="already dealt with", resolved=True, resolution="done"
            ),
        ],
    )

    prompt = stage.hydrate(ticket).prompt

    assert "R1" in prompt
    assert "already dealt with" not in prompt


def test_findings_below_the_blocking_severity_are_not_the_fix_stages_job(tmp_path: Path) -> None:
    stage, ticket, _ = make(tmp_path)
    write_review(ticket, [finding(), finding(id="R2", severity="nit", finding="terse name")])

    prompt = stage.hydrate(ticket).prompt

    assert "R1" in prompt
    assert "terse name" not in prompt


def test_the_fix_stage_never_sees_the_tests(tmp_path: Path) -> None:
    stage, ticket, _ = make(tmp_path)
    write_review(ticket, [finding(file="tests/test_greet.py", line=1)])

    prompt = stage.hydrate(ticket).prompt

    assert "def test_greets" not in prompt
    assert "not in this ticket's diff" in prompt, "a finding about a test resolves to nothing"


def test_reaching_the_fix_stage_with_nothing_to_fix_parks(tmp_path: Path) -> None:
    stage, ticket, _ = make(tmp_path)
    write_review(ticket, [])

    with pytest.raises(ParkSignal) as parked:
        stage.hydrate(ticket)

    assert parked.value.reason == "nothing-to-fix"


def test_the_hunk_budget_is_bounded(tmp_path: Path) -> None:
    stage, ticket, settings = make(tmp_path, review=ReviewConfig(max_hunks=1))
    for name in ("one", "two", "three"):
        (ticket.worktree / f"{name}.py").write_text("x = 1\n", encoding="utf-8")
    write_review(
        ticket,
        [
            finding(id=f"R{n}", file=f"{name}.py", line=1)
            for n, name in enumerate(("one", "two"), 1)
        ],
    )

    assert stage.settings.review.max_hunks == 1
    assert stage.hydrate(ticket).prompt.count("```diff") <= 1
    assert settings.review.max_hunks == 1


def test_the_fix_pack_is_smaller_than_the_review_pack(tmp_path: Path) -> None:
    """The reference-not-paste invariant: packs must not grow monotonically (design.md §2)."""
    stage, ticket, settings = make(tmp_path)
    for name in ("mod_a", "mod_b", "mod_c"):
        (ticket.worktree / f"{name}.py").write_text(
            "def f():\n    return 1\n" * 40, encoding="utf-8"
        )
    write_review(ticket, [finding()])

    review_pack = ReviewStage(settings=settings).hydrate(ticket)
    fix_pack = stage.hydrate(ticket)

    assert fix_pack.size_chars < review_pack.size_chars


# -- policy ----------------------------------------------------------------------


def test_the_fix_stage_is_guarded_exactly_like_the_implement_stage(tmp_path: Path) -> None:
    """Any difference here is somewhere a session could game the second stage but not the first."""
    stage, ticket, settings = make(tmp_path)

    fix_cfg = stage.config(ticket)
    implement_cfg = ImplementStage(settings=settings).config(ticket)

    assert fix_cfg.guards == implement_cfg.guards
    assert fix_cfg.allowed_tools == implement_cfg.allowed_tools
    assert fix_cfg.add_dirs == implement_cfg.add_dirs


def test_the_fix_stage_reruns_the_whole_suite(tmp_path: Path) -> None:
    stage, ticket, _ = make(tmp_path)
    assert [gate.name for gate in stage.gates(ticket)] == ["test"]


def test_held_out_tests_run_again_after_a_fix(tmp_path: Path) -> None:
    stage, ticket, _ = make(tmp_path)
    held = ticket.root / ".flux" / "held-out" / "flux-1"
    held.mkdir(parents=True)
    (held / "test_held.py").write_text("def test_held(): pass\n", encoding="utf-8")

    assert "held-out" in [gate.name for gate in stage.gates(ticket)]


# -- the artifact contract -------------------------------------------------------


def test_an_unresolved_blocker_is_not_a_finished_fix_stage(tmp_path: Path) -> None:
    stage, ticket, _ = make(tmp_path)
    write_review(ticket, [finding()])

    check = validate_artifact(ticket, stage.required_artifact())

    assert not check.ok
    assert "R1" in check.problem


def test_a_resolution_with_no_words_in_it_does_not_count(tmp_path: Path) -> None:
    stage, ticket, _ = make(tmp_path)
    write_review(ticket, [finding(resolved=True, resolution="")])

    assert not validate_artifact(ticket, stage.required_artifact()).ok


def test_every_blocker_resolved_is_a_valid_artifact(tmp_path: Path) -> None:
    stage, ticket, _ = make(tmp_path)
    write_review(ticket, [finding()])
    resolve(ticket)

    assert validate_artifact(ticket, stage.required_artifact()).ok


def test_the_contract_follows_the_repos_own_blocking_severities(tmp_path: Path) -> None:
    settings = FluxConfig(root=tmp_path, review=ReviewConfig(fix_severities=("blocker", "major")))
    payload = {"findings": [finding(severity="major")]}

    check = resolution_check(settings).check
    assert check is not None
    assert "not resolved" in check(payload)


def test_a_minor_finding_is_never_something_the_fix_stage_must_close(tmp_path: Path) -> None:
    settings = FluxConfig(root=tmp_path)
    check = resolution_check(settings).check
    assert check is not None
    assert check({"findings": [finding(severity="minor")]}) == ""


# -- what commit() concludes ------------------------------------------------------


def test_a_clean_fix_stands_and_closes_its_findings(tmp_path: Path) -> None:
    stage, ticket, _ = make(tmp_path)
    write_review(ticket, [finding()])
    resolve(ticket)

    outcome = stage.commit(ticket, session(), (GateOutcome(name="test", passed=True),))

    assert outcome.ok and not outcome.parked
    assert outcome.open_findings is False
    assert outcome.detail["resolved"] == ["R1"]


def test_a_failed_gate_parks_the_ticket(tmp_path: Path) -> None:
    stage, ticket, _ = make(tmp_path)
    write_review(ticket, [finding()])
    resolve(ticket)

    outcome = stage.commit(
        ticket, session(), (GateOutcome(name="test", passed=False, detail="1 failed"),)
    )

    assert outcome.parked and outcome.reason == "gates-failed"
    assert "1 failed" in outcome.note


def test_a_test_edited_during_the_fix_fails_the_stage(tmp_path: Path) -> None:
    """The same digest backstop as implement: the guard is the block, this is the guarantee."""
    stage, ticket, _ = make(tmp_path)
    (ticket.context_dir / "tests.json").write_text(
        json.dumps({**TESTS_ARTIFACT, "test_digests": {"tests/test_greet.py": "0" * 64}}),
        encoding="utf-8",
    )
    write_review(ticket, [finding()])
    resolve(ticket)

    outcome = stage.commit(ticket, session(), (GateOutcome(name="test", passed=True),))

    assert outcome.parked and outcome.reason == "tests-modified"


def test_a_modified_test_is_reported_before_the_green_gates_are(tmp_path: Path) -> None:
    """A suite that went green after a test changed is not evidence about the code."""
    stage, ticket, _ = make(tmp_path)
    (ticket.context_dir / "tests.json").write_text(
        json.dumps({**TESTS_ARTIFACT, "test_digests": {"tests/test_greet.py": "0" * 64}}),
        encoding="utf-8",
    )
    write_review(ticket, [finding()])
    resolve(ticket)

    outcome = stage.commit(
        ticket, session(), (GateOutcome(name="test", passed=False, detail="whatever"),)
    )

    assert outcome.reason == "tests-modified", "the tests verdict outranks the gate verdict"
