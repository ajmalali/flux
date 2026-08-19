"""The review stage: what the reviewer is shown, what it may touch, and what counts.

Two questions dominate this file. The first is what the pack contains — the diff of the
ticket's own commits, the acceptance criteria, the rubric, and demonstrably *not* the
tests. The second is what happens to the findings after the session: they are deduped,
numbered and sorted by the runner, and only the configured severities set the flag the
transition function reads. No model appears here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from flux.config import FluxConfig, ReviewConfig, StageProfile, TestsConfig
from flux.errors import ConfigError, ParkSignal
from flux.executor.types import ExecResult, Usage
from flux.gates.spec import GateSpec
from flux.proc import run_command
from flux.runner.artifact import validate_artifact
from flux.runner.context import TicketContext
from flux.stages.review import (
    ARTIFACT_SPEC,
    Finding,
    ReviewStage,
    check_artifact,
    dedupe,
    number,
    read_artifact,
    read_findings,
    sort_findings,
)

BRIEF = "Add greet(name) to greet.py returning 'hello, <name>'."

IMPLEMENTATION = "def greet(name):\n    return f'hello, {name}'\n"
TEST_SOURCE = (
    'def test_greets():\n    import greet\n\n    assert greet.greet("ada") == "hello, ada"\n'
)

TESTS_ARTIFACT = {
    "test_files": ["tests/test_greet.py"],
    "cases": [
        {"test": "tests/test_greet.py::test_greets", "criterion": "greet returns a greeting"}
    ],
}


def git(root: Path, *args: str) -> None:
    run = run_command(["git", *args], cwd=root)
    assert run.returncode == 0, run.output


def make(
    tmp_path: Path, *, review: ReviewConfig | None = None, implemented: bool = True
) -> tuple[ReviewStage, TicketContext]:
    """A scratch repo standing where the implement stage would have left it."""
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
    (ticket.context_dir / "tests.json").write_text(json.dumps(TESTS_ARTIFACT), encoding="utf-8")

    (root / "tests" / "test_greet.py").write_text(TEST_SOURCE, encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "flux(flux-1): tests")
    git(root, "tag", "-f", "flux/flux-1/tests")
    if implemented:
        (root / "greet.py").write_text(IMPLEMENTATION, encoding="utf-8")
        git(root, "add", "-A")
        git(root, "commit", "-qm", "flux(flux-1): implement")
        git(root, "tag", "-f", "flux/flux-1/implement")
    return ReviewStage(settings=settings), ticket


def session(session_id: str = "s-1") -> ExecResult:
    return ExecResult(
        ok=True,
        text="done",
        session_id=session_id,
        model="claude-opus-5",
        effort="high",
        billing_mode="subscription",
        usage=Usage(input_tokens=10, output_tokens=5),
    )


def write_review(ticket: TicketContext, findings: list[dict[str, object]]) -> None:
    (ticket.context_dir / "review.json").write_text(
        json.dumps({"summary": "a verdict", "findings": findings}, indent=2), encoding="utf-8"
    )


def finding(**kwargs: object) -> dict[str, object]:
    base: dict[str, object] = {
        "severity": "blocker",
        "axis": "correctness",
        "file": "greet.py",
        "line": 2,
        "finding": "greet crashes on an empty name",
        "suggestion": "guard the empty case",
    }
    base.update(kwargs)
    return base


# -- hydration -------------------------------------------------------------------


def test_hydration_is_deterministic(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path)
    assert stage.hydrate(ticket) == stage.hydrate(ticket)


def test_the_pack_carries_the_diff_the_criteria_and_the_rubric(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path)

    pack = stage.hydrate(ticket)

    assert BRIEF in pack.prompt
    assert "greet.py" in pack.prompt and "hello, {name}" in pack.prompt
    assert "greet returns a greeting" in pack.prompt, "the acceptance criteria"
    assert "correctness" in pack.prompt and "design-fit" in pack.prompt
    assert "review.json" in pack.prompt


def test_the_reviewer_is_never_shown_the_tests(tmp_path: Path) -> None:
    """The findings are read by the fix stage, so a quoted assertion would leak past it."""
    stage, ticket = make(tmp_path)

    pack = stage.hydrate(ticket)

    assert 'greet.greet("ada")' not in pack.prompt
    assert "tests/test_greet.py" not in pack.prompt


def test_the_pack_does_not_carry_the_implementation_notes(tmp_path: Path) -> None:
    """design.md's stage I/O table: brief, diff, rubric, plan summary. Not everything."""
    stage, ticket = make(tmp_path)
    (ticket.context_dir / "impl-notes.md").write_text(
        "## Changed\n\nI took a shortcut nobody should trust.\n", encoding="utf-8"
    )

    assert "shortcut nobody should trust" not in stage.hydrate(ticket).prompt


def test_a_ticket_with_nothing_to_review_parks_before_it_spends_anything(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path, implemented=False)
    # Only the tests were committed, and the reviewer may not see those.
    with pytest.raises(ParkSignal) as parked:
        stage.hydrate(ticket)

    assert parked.value.reason == "empty-diff"


def test_a_worktree_that_is_not_a_repo_parks_rather_than_reviewing_nothing(
    tmp_path: Path,
) -> None:
    stage, ticket = make(tmp_path)
    elsewhere = tmp_path / "not-a-repo"
    elsewhere.mkdir()
    detached = TicketContext(
        ticket_id=ticket.ticket_id, root=ticket.root, worktree=elsewhere, brief=BRIEF
    )

    with pytest.raises(ParkSignal) as parked:
        stage.hydrate(detached)

    assert parked.value.reason == "diff-unavailable"


def test_a_large_diff_is_truncated_at_whole_files(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path)
    for name in ("big_one", "big_two", "big_three"):
        (ticket.worktree / f"{name}.py").write_text("x = 1\n" * 400, encoding="utf-8")
    stage = ReviewStage(
        settings=FluxConfig(
            root=stage.settings.root,
            gates=stage.settings.gates,
            stage_commits=False,
            review=ReviewConfig(max_diff_chars=1_500),
        )
    )

    prompt = stage.hydrate(ticket).prompt

    assert "diff truncated at 1500 characters" in prompt
    assert "big_three.py" in prompt, "a dropped file is still named"


# -- policy ----------------------------------------------------------------------


def test_the_reviewer_runs_a_different_model_from_the_implementer(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path)
    cfg = stage.config(ticket)
    assert cfg.model != stage.settings.profile("implement").model


def test_the_reviewer_cannot_write_to_the_repository(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path)
    write_guard = next(g for g in stage.config(ticket).guards if g.name == "review-read-only")

    assert write_guard.decide("Write", {"file_path": str(ticket.worktree / "greet.py")})
    assert not write_guard.decide(
        "Write", {"file_path": str(ticket.context_dir / "review.json")}
    ), "the one file it is judged on must be writable"


def test_the_reviewer_cannot_read_the_tests(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path)
    guard = next(g for g in stage.config(ticket).guards if g.name == "no-test-edits")

    assert guard.decide("Read", {"file_path": str(ticket.worktree / "tests" / "test_greet.py")})


def test_the_reviewer_gets_no_tool_permissions_and_no_gates(tmp_path: Path) -> None:
    """The gates ran at implement time; re-running them would re-measure an unchanged tree."""
    stage, ticket = make(tmp_path)
    assert stage.config(ticket).allowed_tools == ()
    assert stage.gates(ticket) == ()


# -- the artifact contract -------------------------------------------------------


def test_a_clean_review_is_a_valid_review(tmp_path: Path) -> None:
    _, ticket = make(tmp_path)
    write_review(ticket, [])
    assert validate_artifact(ticket, ARTIFACT_SPEC).ok


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"summary": "", "findings": []}, "summary"),
        ({"summary": "ok", "findings": "none"}, "findings"),
        (
            {"summary": "ok", "findings": [{"severity": "urgent", "file": "a", "finding": "x"}]},
            "severity",
        ),
        ({"summary": "ok", "findings": [{"severity": "blocker", "file": "a"}]}, "finding"),
        ({"summary": "ok", "findings": [{"severity": "blocker", "finding": "x"}]}, "file"),
    ],
)
def test_a_malformed_review_names_what_is_wrong(payload: dict[str, object], expected: str) -> None:
    problem = check_artifact(payload)
    assert expected in problem


def test_the_structural_check_costs_a_nudge_rather_than_a_park(tmp_path: Path) -> None:
    """``required_keys`` alone would accept a findings list of junk (design.md §2)."""
    _, ticket = make(tmp_path)
    (ticket.context_dir / "review.json").write_text(
        json.dumps({"summary": "ok", "findings": [{"severity": "blocker"}]}), encoding="utf-8"
    )
    check = validate_artifact(ticket, ARTIFACT_SPEC)
    assert not check.ok
    assert "finding" in check.problem


# -- what commit() concludes ------------------------------------------------------


def test_a_blocker_opens_the_fix_loop(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path)
    write_review(ticket, [finding()])

    outcome = stage.commit(ticket, session(), ())

    assert outcome.ok
    assert outcome.open_findings is True
    assert outcome.detail["blocking"] == ["R1"]


def test_findings_below_the_blocking_severity_do_not_turn_the_loop(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path)
    write_review(ticket, [finding(severity="minor"), finding(severity="nit", line=3)])

    outcome = stage.commit(ticket, session(), ())

    assert outcome.open_findings is False
    assert outcome.detail["findings"] == {"blocker": 0, "major": 0, "minor": 1, "nit": 1}


def test_a_repo_can_block_on_more_than_blockers(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path, review=ReviewConfig(fix_severities=("blocker", "major")))
    write_review(ticket, [finding(severity="major")])

    assert stage.commit(ticket, session(), ()).open_findings is True


def test_a_clean_review_lets_the_ticket_move_on(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path)
    write_review(ticket, [])

    outcome = stage.commit(ticket, session(), ())

    assert outcome.ok and outcome.open_findings is False
    assert "no findings" in outcome.note


def test_the_same_finding_twice_is_one_finding(tmp_path: Path) -> None:
    """A duplicated blocker is one extra paid fix session and one more chance to park."""
    stage, ticket = make(tmp_path)
    write_review(ticket, [finding(), finding(severity="major"), finding(line=9)])

    outcome = stage.commit(ticket, session(), ())
    stored = read_findings(read_artifact(ticket) or {})

    assert len(stored) == 2, "the restated finding is merged; a different line is not"
    assert outcome.detail["duplicates_merged"] == 1
    assert stored[0].severity == "blocker", "the more severe reading of a repeat is kept"


def test_findings_come_back_numbered_and_sorted(tmp_path: Path) -> None:
    stage, ticket = make(tmp_path)
    write_review(
        ticket,
        [finding(severity="nit", line=8, finding="name is terse"), finding()],
    )

    stage.commit(ticket, session(), ())
    stored = read_findings(read_artifact(ticket) or {})

    assert [f.id for f in stored] == ["R1", "R2"]
    assert [f.severity for f in stored] == ["blocker", "nit"]


def test_normalising_keeps_fields_the_reviewer_invented(tmp_path: Path) -> None:
    """Rewriting the artifact must not quietly delete what a model chose to record."""
    stage, ticket = make(tmp_path)
    write_review(ticket, [finding(confidence="low")])

    stage.commit(ticket, session(), ())
    stored = json.loads((ticket.context_dir / "review.json").read_text())

    assert stored["findings"][0]["confidence"] == "low"
    assert stored["summary"] == "a verdict"


# -- the pieces, directly ---------------------------------------------------------


def test_dedupe_keeps_the_most_severe_reading_of_one_defect() -> None:
    same = {"file": "a.py", "line": 4, "axis": "correctness", "finding": "It  is\nwrong"}
    findings = (
        Finding.from_json({**same, "severity": "minor"}),
        Finding.from_json({**same, "severity": "blocker"}),
    )
    (kept,) = dedupe(findings)
    assert kept.severity == "blocker"


def test_numbering_never_repeats_an_id_the_model_chose() -> None:
    findings = [
        Finding(severity="blocker", finding="a", id="X"),
        Finding(severity="blocker", finding="b", id="X"),
    ]
    ids = [f.id for f in number(findings)]
    assert len(set(ids)) == 2


def test_sorting_puts_the_most_serious_first() -> None:
    findings = [
        Finding(severity="nit", finding="a", file="z.py"),
        Finding(severity="blocker", finding="b", file="a.py"),
        Finding(severity="minor", finding="c", file="m.py"),
    ]
    assert [f.severity for f in sort_findings(findings)] == ["blocker", "minor", "nit"]


def test_a_severity_no_one_defined_is_rejected_by_config() -> None:
    with pytest.raises(ConfigError, match="fix_severities"):
        ReviewConfig(fix_severities=("urgent",))


def test_a_review_stage_with_no_profile_says_which_one_is_missing(tmp_path: Path) -> None:
    settings = FluxConfig(
        root=tmp_path,
        stages={"implement": StageProfile(model="claude-sonnet-5", effort="high")},
    )
    with pytest.raises(ConfigError, match=r"\[stages.review\]"):
        settings.profile("review")
