"""Stage commits: provenance in the worktree's own history, and never a blocker.

``stage_commit`` records what a stage did so "reset to the last good stage" is a
``git reset --hard`` (design.md §1). It is deliberately incapable of failing a
pipeline: every problem comes back as an unsuccessful result the stage records.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from flux.git import (
    current_branch,
    is_git_repo,
    push_head,
    remote_sha,
    stage_commit,
    stage_tag,
    ticket_diff,
    ticket_log,
)
from flux.proc import run_command


def git(worktree: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=worktree, capture_output=True, text=True, check=True
    ).stdout


def repo(tmp_path: Path, *, identity: bool = True) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    run_command(["git", "init", "-q", "-b", "main"], cwd=tmp_path)
    if identity:
        run_command(["git", "config", "user.email", "dev@example.com"], cwd=tmp_path)
        run_command(["git", "config", "user.name", "Dev"], cwd=tmp_path)
    (tmp_path / "seed.txt").write_text("seed\n", encoding="utf-8")
    run_command(["git", "add", "-A"], cwd=tmp_path)
    run_command(
        ["git", "-c", "user.email=s@e.com", "-c", "user.name=s", "commit", "-qm", "seed"],
        cwd=tmp_path,
    )
    return tmp_path


def test_a_stage_commit_records_the_work_and_tags_it(tmp_path: Path) -> None:
    worktree = repo(tmp_path)
    (worktree / "feature.py").write_text("value = 1\n", encoding="utf-8")

    result = stage_commit(worktree, ticket="flux-1", stage="implement", message="flux: implement")

    assert result.ok and result.committed
    assert result.sha
    assert result.tag == "flux/flux-1/implement"
    assert git(worktree, "log", "-1", "--pretty=%s").strip() == "flux: implement"
    assert "flux/flux-1/implement" in git(worktree, "tag", "--list")


def test_untracked_files_are_included(tmp_path: Path) -> None:
    """A stage that created a new file did work the next stage must see."""
    worktree = repo(tmp_path)
    (worktree / "new" / "deep").mkdir(parents=True)
    (worktree / "new" / "deep" / "mod.py").write_text("x = 1\n", encoding="utf-8")

    stage_commit(worktree, ticket="t", stage="implement", message="m")
    assert "new/deep/mod.py" in git(worktree, "show", "--name-only", "--pretty=", "HEAD")


def test_a_clean_tree_commits_nothing_and_still_succeeds(tmp_path: Path) -> None:
    worktree = repo(tmp_path)
    before = git(worktree, "rev-parse", "HEAD")

    result = stage_commit(worktree, ticket="t", stage="implement", message="m")

    assert result.ok and not result.committed
    assert result.detail == "nothing to commit"
    assert git(worktree, "rev-parse", "HEAD") == before


def test_a_repo_without_an_identity_still_commits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A scratch checkout with no user.email must not fail a stage over bookkeeping."""
    # The developer's own ~/.gitconfig would otherwise supply the identity being tested for.
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "absent-global"))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(tmp_path / "absent-system"))
    worktree = repo(tmp_path, identity=False)
    (worktree / "feature.py").write_text("value = 1\n", encoding="utf-8")

    result = stage_commit(worktree, ticket="t", stage="implement", message="m")

    assert result.ok and result.committed
    assert "flux" in git(worktree, "log", "-1", "--pretty=%an")


def test_a_configured_identity_is_left_alone(tmp_path: Path) -> None:
    worktree = repo(tmp_path)
    (worktree / "feature.py").write_text("value = 1\n", encoding="utf-8")

    stage_commit(worktree, ticket="t", stage="implement", message="m")
    assert git(worktree, "log", "-1", "--pretty=%ae").strip() == "dev@example.com"


def test_a_rerun_moves_the_tag_rather_than_failing(tmp_path: Path) -> None:
    worktree = repo(tmp_path)
    (worktree / "a.py").write_text("1\n", encoding="utf-8")
    first = stage_commit(worktree, ticket="t", stage="implement", message="first")
    (worktree / "b.py").write_text("2\n", encoding="utf-8")
    second = stage_commit(worktree, ticket="t", stage="implement", message="second")

    assert second.ok and second.sha != first.sha
    assert git(worktree, "rev-parse", second.tag).strip() == second.sha


def test_a_worktree_that_is_not_a_repo_reports_rather_than_raises(tmp_path: Path) -> None:
    result = stage_commit(tmp_path, ticket="t", stage="implement", message="m")
    assert not result.ok
    assert "not a git repository" in result.detail


def test_is_git_repo_distinguishes_the_two(tmp_path: Path) -> None:
    assert not is_git_repo(tmp_path)
    assert is_git_repo(repo(tmp_path))


def test_tags_are_sanitised_into_legal_refs() -> None:
    assert stage_tag("flux-1", "implement") == "flux/flux-1/implement"
    assert stage_tag("odd ticket~1", "im:plement") == "flux/odd-ticket-1/im-plement"


def test_a_sanitised_tag_is_one_git_accepts(tmp_path: Path) -> None:
    worktree = repo(tmp_path)
    (worktree / "a.py").write_text("1\n", encoding="utf-8")
    result = stage_commit(worktree, ticket="odd.ticket-1", stage="implement", message="m")
    assert result.ok
    assert result.tag in git(worktree, "tag", "--list")


# -- build output never becomes part of a ticket ---------------------------------


def test_build_output_is_not_committed_by_a_stage(tmp_path: Path) -> None:
    """T5.3's live finding: in a repo with no .gitignore, `git add -A` committed
    `__pycache__/*.pyc`, the reviewer reported them, and no fix could take them back out
    of the diff — so the review loop could not converge."""
    worktree = repo(tmp_path)
    (worktree / "__pycache__").mkdir()
    (worktree / "__pycache__" / "greet.cpython-312.pyc").write_bytes(b"\x00binary")
    (worktree / ".DS_Store").write_bytes(b"\x00")
    (worktree / "feature.py").write_text("value = 1\n", encoding="utf-8")

    result = stage_commit(worktree, ticket="flux-1", stage="implement", message="m")

    assert result.ok and result.committed
    tracked = git(worktree, "ls-files").split()
    assert "feature.py" in tracked
    assert not [path for path in tracked if ".pyc" in path or path == ".DS_Store"]


def test_a_tree_dirty_with_only_build_output_commits_nothing(tmp_path: Path) -> None:
    worktree = repo(tmp_path)
    (worktree / "__pycache__").mkdir()
    (worktree / "__pycache__" / "x.pyc").write_bytes(b"\x00")

    result = stage_commit(worktree, ticket="flux-1", stage="implement", message="m")

    assert result.ok and not result.committed
    assert "build output" in result.detail, "the reason is stated, not hidden as 'clean'"


def test_build_output_stays_out_of_the_diff_a_reviewer_is_shown(tmp_path: Path) -> None:
    worktree = repo(tmp_path)
    (worktree / "feature.py").write_text("value = 1\n", encoding="utf-8")
    stage_commit(worktree, ticket="flux-1", stage="implement", message="m")
    (worktree / "__pycache__").mkdir()
    (worktree / "__pycache__" / "x.pyc").write_bytes(b"\x00")

    result = ticket_diff(worktree, ticket="flux-1")

    assert result.ok
    assert "feature.py" in result.text
    assert "__pycache__" not in result.text
    assert not result.untracked


# -- branches, remotes, and the push ---------------------------------------------


def bare_remote(worktree: Path, tmp_path: Path) -> Path:
    origin = tmp_path / "origin.git"
    run_command(["git", "init", "-q", "--bare", str(origin)], cwd=worktree)
    run_command(["git", "remote", "add", "origin", str(origin)], cwd=worktree)
    return origin


def test_current_branch_reads_the_checkout_and_says_nothing_when_detached(
    tmp_path: Path,
) -> None:
    worktree = repo(tmp_path / "r")
    assert current_branch(worktree) == "main"

    run_command(["git", "checkout", "-q", "--detach", "HEAD"], cwd=worktree)

    assert current_branch(worktree) == ""


def test_a_push_that_landed_is_confirmed_from_the_remote(tmp_path: Path) -> None:
    worktree = repo(tmp_path / "r")
    bare_remote(worktree, tmp_path)

    result = push_head(worktree, remote="origin", branch="feature")

    assert result.ok and result.created
    assert result.sha == git(worktree, "rev-parse", "HEAD").strip()
    assert remote_sha(worktree, remote="origin", branch="feature") == result.sha


def test_pushing_head_to_another_name_does_not_move_the_checkout(tmp_path: Path) -> None:
    worktree = repo(tmp_path / "r")
    bare_remote(worktree, tmp_path)

    push_head(worktree, remote="origin", branch="flux/flux-1")

    assert current_branch(worktree) == "main"
    assert remote_sha(worktree, remote="origin", branch="main") == ""


def test_a_push_to_a_remote_that_is_not_there_reports_rather_than_raises(
    tmp_path: Path,
) -> None:
    worktree = repo(tmp_path / "r")

    result = push_head(worktree, remote="origin", branch="feature")

    assert not result.ok
    assert result.detail


def test_a_second_push_of_the_same_branch_is_not_a_new_branch(tmp_path: Path) -> None:
    worktree = repo(tmp_path / "r")
    bare_remote(worktree, tmp_path)
    push_head(worktree, remote="origin", branch="feature")

    (worktree / "again.txt").write_text("x\n", encoding="utf-8")
    stage_commit(worktree, ticket="flux-1", stage="implement", message="m")
    again = push_head(worktree, remote="origin", branch="feature")

    assert again.ok and not again.created


def test_the_ticket_log_is_bounded_by_the_same_tags_as_the_diff(tmp_path: Path) -> None:
    worktree = repo(tmp_path / "r")
    (worktree / "a.py").write_text("a = 1\n", encoding="utf-8")
    stage_commit(worktree, ticket="flux-1", stage="tests", message="flux(flux-1): tests")
    (worktree / "b.py").write_text("b = 2\n", encoding="utf-8")
    stage_commit(worktree, ticket="flux-1", stage="implement", message="flux(flux-1): implement")

    log = ticket_log(worktree, ticket="flux-1")

    assert [line.split(" ", 1)[1] for line in log] == [
        "flux(flux-1): tests",
        "flux(flux-1): implement",
    ], "oldest first, and the seed commit is not this ticket's"


def test_a_ticket_with_no_stage_commits_has_no_log(tmp_path: Path) -> None:
    worktree = repo(tmp_path / "r")
    (worktree / "a.py").write_text("a = 1\n", encoding="utf-8")

    assert ticket_log(worktree, ticket="flux-1") == ()
