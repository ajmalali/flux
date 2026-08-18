"""Stage commits: provenance in the worktree's own history, and never a blocker.

``stage_commit`` records what a stage did so "reset to the last good stage" is a
``git reset --hard`` (design.md §1). It is deliberately incapable of failing a
pipeline: every problem comes back as an unsuccessful result the stage records.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from flux.git import is_git_repo, stage_commit, stage_tag
from flux.proc import run_command


def git(worktree: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=worktree, capture_output=True, text=True, check=True
    ).stdout


def repo(tmp_path: Path, *, identity: bool = True) -> Path:
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
