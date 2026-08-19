"""The pr stage: the session writes prose, the runner lands the plane.

The stage is unusual in that almost nothing it concludes comes from the model, so
almost nothing here mocks one. A bare repository stands in for the forge: pushes are
real pushes, and "the branch landed" is asserted by reading the ref back out of the
remote — which is the same thing the stage itself does, and the reason the assertion
is worth making.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from flux.config import FluxConfig, PrConfig, ReviewConfig, TestsConfig
from flux.errors import ConfigError, ParkSignal
from flux.executor.types import ExecResult, Usage
from flux.gates.spec import GateSpec
from flux.git import remote_sha
from flux.metrics.record import GateOutcome
from flux.proc import run_command
from flux.runner.artifact import validate_artifact
from flux.runner.context import TicketContext
from flux.stages.pr import ARTIFACT_SPEC, MAX_TITLE_CHARS, PrStage, parse_artifact, provenance

BRIEF = "Add greet(name) to greet.py returning 'hello, <name>'."

NOTES = (
    "## Changed\n\ngreet.py — added greet(name).\n\n"
    "## Deviations\n\nNone.\n\n"
    "## Discovered work\n\nNone.\n"
)

TEST_SOURCE = "def test_greets():\n    import greet\n\n    assert greet.greet('ada')\n"

PR_MD = (
    "## Title\n\nAdd greet(name) to the greeter\n\n"
    "## Summary\n\nAdds a greeting helper and rejects an empty name.\n\n"
    "## Changes\n\n- `greet.py`: new `greet(name)`\n\n"
    "## Review\n\nOne blocker about the empty name, resolved.\n\n"
    "## Risk\n\nNone worth naming.\n"
)

REVIEW = {
    "summary": "sound once the empty name was handled",
    "findings": [
        {
            "id": "R1",
            "severity": "blocker",
            "axis": "correctness",
            "file": "greet.py",
            "line": 2,
            "finding": "greet('') returns a bare greeting",
            "resolved": True,
            "resolution": "raised ValueError on an empty name",
        }
    ],
}


def git(root: Path, *args: str) -> str:
    run = run_command(["git", *args], cwd=root)
    assert run.returncode == 0, run.output
    return run.stdout.strip()


def make(
    tmp_path: Path,
    *,
    pr: PrConfig | None = None,
    remote: bool = True,
    branch: str = "main",
) -> tuple[PrStage, TicketContext, FluxConfig]:
    """A repo with one ticket's work committed under its stage tags, and somewhere to push."""
    root = tmp_path / "target"
    (root / "tests").mkdir(parents=True)
    git(root, "init", "-q", "-b", branch)
    git(root, "config", "user.email", "dev@example.com")
    git(root, "config", "user.name", "Dev")
    (root / "pyproject.toml").write_text("[project]\nname='target'\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "base")

    if remote:
        origin = tmp_path / "origin.git"
        git(root, "init", "-q", "--bare", str(origin))
        git(root, "remote", "add", "origin", str(origin))

    settings = FluxConfig(
        root=root,
        gates=(GateSpec(name="test", kind="pytest", command=("true",)),),
        stage_commits=False,
        tests=TestsConfig(),
        review=ReviewConfig(),
        pr=pr if pr is not None else PrConfig(),
    )
    ticket = TicketContext(ticket_id="flux-1", root=root, brief=BRIEF)
    ticket.context_dir.mkdir(parents=True, exist_ok=True)

    (root / "tests" / "test_greet.py").write_text(TEST_SOURCE, encoding="utf-8")
    (root / "greet.py").write_text("def greet(name):\n    return f'hello, {name}'\n", "utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "flux(flux-1): implement")
    git(root, "tag", "-f", "flux/flux-1/implement")

    (ticket.context_dir / "impl-notes.md").write_text(NOTES, encoding="utf-8")
    (ticket.context_dir / "review.json").write_text(json.dumps(REVIEW), encoding="utf-8")
    (ticket.context_dir / "pr.md").write_text(PR_MD, encoding="utf-8")
    return PrStage(settings=settings), ticket, settings


def session() -> ExecResult:
    return ExecResult(
        ok=True,
        text="done",
        session_id="s-1",
        model="claude-haiku-4-5-20251001",
        effort="low",
        billing_mode="subscription",
        usage=Usage(input_tokens=10, output_tokens=5),
    )


GREEN = (GateOutcome(name="test", passed=True, duration_ms=1),)


# -- pr.md, parsed into the two fields a forge takes -----------------------------


def test_the_artifact_splits_into_a_one_line_title_and_the_rest() -> None:
    pull = parse_artifact(PR_MD)

    assert pull.title == "Add greet(name) to the greeter"
    assert pull.body.startswith("## Summary")
    assert "## Risk" in pull.body
    assert "## Title" not in pull.body, "the title is a field, not part of the body"


def test_a_title_written_as_a_heading_is_still_a_title() -> None:
    """The instruction says one line of text; a model that writes `# Thing` meant the same."""
    assert parse_artifact("## Title\n\n# Do the thing\n\n## Summary\n\nx\n").title == "Do the thing"


def test_a_long_title_is_cut_rather_than_passed_on() -> None:
    long_title = "word " * 40
    pull = parse_artifact(f"## Title\n\n{long_title}\n\n## Summary\n\nx\n")

    assert len(pull.title) <= MAX_TITLE_CHARS


def test_an_empty_body_is_not_a_pull_request() -> None:
    assert not parse_artifact("## Title\n\nA title\n").ok


def test_the_artifact_spec_rejects_a_body_with_no_risk_section(tmp_path: Path) -> None:
    _, ticket, _ = make(tmp_path)
    (ticket.context_dir / "pr.md").write_text(
        "## Title\n\nT\n\n## Summary\n\n" + "s" * 100 + "\n\n## Changes\n\nc\n\n## Review\n\nr\n",
        encoding="utf-8",
    )

    check = validate_artifact(ticket, ARTIFACT_SPEC)

    assert not check.ok
    assert "Risk" in check.problem


# -- what the session is given ---------------------------------------------------


def test_the_pack_carries_the_notes_the_resolutions_and_the_log(tmp_path: Path) -> None:
    stage, ticket, _ = make(tmp_path)

    prompt = stage.hydrate(ticket).prompt

    assert "added greet(name)" in prompt, "the implementation notes"
    assert "raised ValueError on an empty name" in prompt, "the resolution"
    assert "flux(flux-1): implement" in prompt, "the commit log"
    assert "greet.py" in prompt


def test_the_pack_names_the_changed_files_without_carrying_the_diff(tmp_path: Path) -> None:
    """A stage that writes four paragraphs does not need the change, only its shape."""
    stage, ticket, _ = make(tmp_path)

    prompt = stage.hydrate(ticket).prompt

    assert "changed line(s)" in prompt
    assert "def greet(name):" not in prompt, "the diff body is not hydrated"
    assert "greet.greet('ada')" not in prompt, "and never the test source"


def test_a_ticket_with_no_stage_commits_parks_before_it_costs_a_session(tmp_path: Path) -> None:
    stage, ticket, _ = make(tmp_path)
    git(ticket.worktree, "tag", "-d", "flux/flux-1/implement")

    with pytest.raises(ParkSignal) as parked:
        stage.hydrate(ticket)

    assert parked.value.reason == "nothing-to-push"


def test_with_push_off_a_ticket_without_commits_still_gets_a_body(tmp_path: Path) -> None:
    """Nothing to push is only a problem for a repo that pushes."""
    stage, ticket, _ = make(tmp_path, pr=PrConfig(push=False))
    git(ticket.worktree, "tag", "-d", "flux/flux-1/implement")

    assert stage.hydrate(ticket).prompt


# -- what the session may do -----------------------------------------------------


def test_the_pr_session_can_write_its_body_and_nothing_else(tmp_path: Path) -> None:
    stage, ticket, _ = make(tmp_path)

    guard, _ = stage.config(ticket).guards

    assert guard.decide("Write", {"file_path": str(ticket.worktree / "greet.py")})
    assert guard.decide("Write", {"file_path": str(ticket.context_dir / "pr.md")}) == ""


def test_the_pr_session_cannot_read_the_tests(tmp_path: Path) -> None:
    stage, ticket, _ = make(tmp_path)

    _, tests_guard = stage.config(ticket).guards

    assert tests_guard.decide("Read", {"file_path": str(ticket.worktree / "tests/test_greet.py")})


def test_the_pr_session_gets_no_shell(tmp_path: Path) -> None:
    """The stage's contract is that it does not touch the remote; no Bash is how."""
    stage, ticket, _ = make(tmp_path)

    cfg = stage.config(ticket)

    assert cfg.allowed_tools == ()
    assert cfg.model.startswith("claude-haiku")
    assert cfg.effort == "low"


def test_the_full_gate_suite_runs_again_on_the_tree_about_to_be_pushed(tmp_path: Path) -> None:
    stage, ticket, _ = make(tmp_path)

    assert [g.name for g in stage.gates(ticket)] == ["test"]


# -- landing the plane -----------------------------------------------------------


def test_the_branch_is_pushed_and_the_remote_is_read_back(tmp_path: Path) -> None:
    stage, ticket, settings = make(tmp_path, pr=PrConfig(create="never"), branch="feature/greet")

    outcome = stage.commit(ticket, session(), GREEN)

    assert outcome.ok and not outcome.parked
    assert outcome.detail["pushed"] is True
    assert outcome.detail["branch"] == "feature/greet", "an unprotected branch keeps its name"
    landed = remote_sha(ticket.worktree, remote=settings.pr.remote, branch="feature/greet")
    assert landed == outcome.detail["sha"] == git(ticket.worktree, "rev-parse", "HEAD")


def test_a_protected_branch_is_never_pushed_to(tmp_path: Path) -> None:
    """The work is real and green; it goes somewhere safe rather than nowhere."""
    stage, ticket, _ = make(tmp_path, pr=PrConfig(create="never", protected_branches=("main",)))

    outcome = stage.commit(ticket, session(), GREEN)

    assert outcome.ok
    assert outcome.detail["branch"] == "flux/flux-1"
    assert remote_sha(ticket.worktree, remote="origin", branch="main") == "", "main is untouched"
    assert remote_sha(ticket.worktree, remote="origin", branch="flux/flux-1")


def test_the_local_checkout_is_not_moved_by_the_push(tmp_path: Path) -> None:
    stage, ticket, _ = make(tmp_path, pr=PrConfig(create="never", protected_branches=("main",)))

    stage.commit(ticket, session(), GREEN)

    assert git(ticket.worktree, "rev-parse", "--abbrev-ref", "HEAD") == "main"


def test_a_repo_with_nowhere_to_land_parks_rather_than_reporting_success(tmp_path: Path) -> None:
    """ADR 0005's rule, applied to the push: a check that cannot run has failed."""
    stage, ticket, _ = make(tmp_path, remote=False)

    outcome = stage.commit(ticket, session(), GREEN)

    assert outcome.parked
    assert outcome.reason == "no-remote"
    assert "push = false" in outcome.note, "the note names the supported way to mean this"


def test_push_off_writes_the_body_and_stands(tmp_path: Path) -> None:
    stage, ticket, _ = make(tmp_path, pr=PrConfig(push=False), remote=False)

    outcome = stage.commit(ticket, session(), GREEN)

    assert outcome.ok and not outcome.parked
    assert outcome.detail["pushed"] is False
    assert outcome.detail["title"] == "Add greet(name) to the greeter"


def test_a_failed_gate_stops_the_push_before_anything_leaves_the_machine(tmp_path: Path) -> None:
    stage, ticket, _ = make(tmp_path)
    red = (GateOutcome(name="test", passed=False, duration_ms=1, detail="1 failed"),)

    outcome = stage.commit(ticket, session(), red)

    assert outcome.parked and outcome.reason == "gates-failed"
    assert remote_sha(ticket.worktree, remote="origin", branch="main") == ""


def test_an_unparseable_body_parks_rather_than_pushing_an_empty_pull_request(
    tmp_path: Path,
) -> None:
    stage, ticket, _ = make(tmp_path)
    (ticket.context_dir / "pr.md").write_text("## Title\n\nJust a title\n", encoding="utf-8")

    outcome = stage.commit(ticket, session(), GREEN)

    assert outcome.parked and outcome.reason == "artifact-invalid"


def test_create_always_parks_when_the_pull_request_cannot_be_opened(tmp_path: Path) -> None:
    """A bare repo on disk is not a forge, so `gh` cannot open anything against it."""
    stage, ticket, _ = make(tmp_path, pr=PrConfig(create="always"))

    outcome = stage.commit(ticket, session(), GREEN)

    assert outcome.parked and outcome.reason == "pr-not-opened"
    assert outcome.detail["pushed"] is True, "the branch still landed; only the PR did not"


def test_create_auto_reports_the_missing_pull_request_without_parking(tmp_path: Path) -> None:
    stage, ticket, _ = make(tmp_path, pr=PrConfig(create="auto"))

    outcome = stage.commit(ticket, session(), GREEN)

    assert outcome.ok and not outcome.parked
    assert outcome.detail["pr_url"] == ""
    assert outcome.detail["pr_problem"]


# -- the footer flux writes itself ------------------------------------------------


def test_the_provenance_footer_states_the_gates_flux_measured(tmp_path: Path) -> None:
    _, ticket, _ = make(tmp_path)

    footer = provenance(
        ticket,
        gates=(
            GateOutcome(name="lint", passed=True, duration_ms=1),
            GateOutcome(name="test", passed=False, duration_ms=1),
        ),
        commits=("abc1234 flux(flux-1): implement",),
    )

    assert "lint pass, test FAIL" in footer
    assert "flux-1" in footer
    assert "abc1234" in footer


def test_the_footer_says_so_when_nothing_verified_the_change(tmp_path: Path) -> None:
    _, ticket, _ = make(tmp_path)

    assert "nothing verified this" in provenance(ticket, gates=(), commits=())


# -- configuration ----------------------------------------------------------------


def test_an_unknown_create_mode_is_refused() -> None:
    with pytest.raises(ConfigError, match="create"):
        PrConfig(create="sometimes")


def test_a_repo_that_pushes_must_name_a_remote() -> None:
    with pytest.raises(ConfigError, match="remote"):
        PrConfig(push=True, remote=" ")


def test_an_empty_branch_prefix_is_refused() -> None:
    """Without it, a ticket on a protected branch would have nowhere to be pushed."""
    with pytest.raises(ConfigError, match="branch_prefix"):
        PrConfig(branch_prefix="")


def test_the_pr_block_round_trips_through_flux_toml(tmp_path: Path) -> None:
    settings = FluxConfig(root=tmp_path, pr=PrConfig(draft=False, create="never", base="trunk"))

    reloaded = FluxConfig.parse(_toml(settings.to_toml()), root=tmp_path)

    assert reloaded.pr == settings.pr


def _toml(text: str) -> dict[str, object]:
    import tomllib

    return tomllib.loads(text)
