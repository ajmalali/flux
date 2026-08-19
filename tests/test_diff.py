"""Diffs: parsed from git's real output, addressed by ``file:line``, and bounded.

The review stage hydrates from a diff and the fix stage hydrates from *slices* of one,
so two things have to hold: the parser must survive what git actually emits (not a
hand-written approximation of it), and a finding at ``file:line`` must resolve to the
hunk containing that line. Both are checked here against diffs produced by running git.
"""

from __future__ import annotations

from pathlib import Path

from flux.diff import Diff, FileDiff, Hunk, parse, select_hunks
from flux.git import ticket_diff
from flux.proc import run_command

A_PY = "\n".join(f"line {n}" for n in range(1, 21)) + "\n"


def git(root: Path, *args: str) -> str:
    run = run_command(["git", *args], cwd=root)
    assert run.returncode == 0, f"git {' '.join(args)} failed: {run.output}"
    return run.stdout


def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "dev@example.com")
    git(root, "config", "user.name", "Dev")
    (root / "src" / "a.py").write_text(A_PY, encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "base")
    return root


def commit(root: Path, message: str, tag: str = "") -> None:
    git(root, "add", "-A")
    git(root, "commit", "-qm", message)
    if tag:
        git(root, "tag", "-f", tag)


# -- parsing ---------------------------------------------------------------------


def test_a_real_git_diff_parses_into_files_and_hunks(tmp_path: Path) -> None:
    root = repo(tmp_path)
    lines = A_PY.splitlines()
    lines[2] = "line 3 CHANGED"
    lines[17] = "line 18 CHANGED"
    (root / "src" / "a.py").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (root / "src" / "b.py").write_text("new module\n", encoding="utf-8")
    git(root, "add", "-A")

    diff = parse(git(root, "diff", "--cached"))

    assert diff.paths == ("src/a.py", "src/b.py")
    assert len(diff.file("src/a.py").hunks) == 2  # pyright: ignore[reportOptionalMemberAccess]
    assert diff.changed_lines == 5  # two changed lines (+/- each) plus one added file


def test_an_empty_diff_is_empty() -> None:
    assert parse("").is_empty
    assert parse("   \n").is_empty
    assert not parse("diff --git a/x b/x\n--- a/x\n+++ b/x\n").is_empty


def test_a_hunk_knows_which_lines_it_covers(tmp_path: Path) -> None:
    root = repo(tmp_path)
    lines = A_PY.splitlines()
    lines[9] = "line 10 CHANGED"
    (root / "src" / "a.py").write_text("\n".join(lines) + "\n", encoding="utf-8")

    diff = parse(git(root, "diff"))
    hunk = diff.hunk_at("src/a.py", 10)

    assert hunk is not None
    assert hunk.covers(10)
    assert diff.hunk_at("src/a.py", 1) is None, "line 1 is outside the changed hunk"


def test_a_deleted_file_keeps_its_old_path(tmp_path: Path) -> None:
    root = repo(tmp_path)
    (root / "src" / "a.py").unlink()

    diff = parse(git(root, "diff"))

    assert diff.paths == ("src/a.py",)


def test_a_binary_file_survives_as_a_block_with_no_hunks(tmp_path: Path) -> None:
    root = repo(tmp_path)
    (root / "src" / "blob.bin").write_bytes(bytes(range(256)))
    git(root, "add", "-A")

    diff = parse(git(root, "diff", "--cached"))
    block = diff.file("src/blob.bin")

    assert block is not None, "a binary change must not vanish from the review"
    assert block.hunks == ()
    assert "Binary" in block.text or "GIT binary patch" in block.text


def test_a_path_resolves_by_suffix_when_the_finding_shortened_it(tmp_path: Path) -> None:
    """A model writes ``a.py`` where git wrote ``src/a.py``; the hunk is still the hunk."""
    root = repo(tmp_path)
    (root / "src" / "a.py").write_text(A_PY + "extra\n", encoding="utf-8")

    diff = parse(git(root, "diff"))

    assert diff.file("a.py") is diff.file("src/a.py")
    assert diff.file("nowhere.py") is None


def test_an_ambiguous_suffix_resolves_to_nothing(tmp_path: Path) -> None:
    """Two ``util.py`` files and a bare ``util.py`` finding: guessing would be worse."""
    diff = Diff(
        files=(
            FileDiff(path="a/util.py", header="diff --git a/a/util.py b/a/util.py"),
            FileDiff(path="b/util.py", header="diff --git a/b/util.py b/b/util.py"),
        )
    )
    assert diff.file("util.py") is None


# -- rendering -------------------------------------------------------------------


def test_rendering_truncates_whole_files_and_names_the_ones_it_dropped(tmp_path: Path) -> None:
    root = repo(tmp_path)
    for name in ("b", "c", "d"):
        (root / "src" / f"{name}.py").write_text(A_PY, encoding="utf-8")
    git(root, "add", "-A")
    diff = parse(git(root, "diff", "--cached"))

    rendered = diff.render(limit=200)

    assert "truncated" in rendered
    assert "src/d.py" in rendered, "a dropped file must still be named"
    assert rendered.count("@@") < sum(len(f.hunks) for f in diff.files)


def test_rendering_without_a_limit_keeps_everything(tmp_path: Path) -> None:
    root = repo(tmp_path)
    (root / "src" / "b.py").write_text("x\n", encoding="utf-8")
    git(root, "add", "-A")
    diff = parse(git(root, "diff", "--cached"))

    assert "truncated" not in diff.render()
    assert diff.render().count("diff --git") == 1


# -- selecting hunks for the fix stage -------------------------------------------


def test_select_hunks_returns_one_slice_per_place_not_per_finding(tmp_path: Path) -> None:
    root = repo(tmp_path)
    lines = A_PY.splitlines()
    lines[2] = "line 3 CHANGED"
    (root / "src" / "a.py").write_text("\n".join(lines) + "\n", encoding="utf-8")
    diff = parse(git(root, "diff"))

    refs = select_hunks(diff, [("src/a.py", 3), ("src/a.py", 4)])

    assert len(refs) == 1, "two findings inside one hunk cost one hunk"
    assert refs[0].hunk is not None
    assert "line 3 CHANGED" in refs[0].render()


def test_select_hunks_says_so_when_a_finding_points_outside_the_diff(tmp_path: Path) -> None:
    root = repo(tmp_path)
    (root / "src" / "a.py").write_text(A_PY + "added\n", encoding="utf-8")
    diff = parse(git(root, "diff"))

    (missing,) = select_hunks(diff, [("src/elsewhere.py", 4)])

    assert missing.hunk is None
    assert "not in this ticket's diff" in missing.render()


def test_select_hunks_says_so_when_the_line_is_not_in_a_changed_hunk(tmp_path: Path) -> None:
    root = repo(tmp_path)
    lines = A_PY.splitlines()
    lines[19] = "line 20 CHANGED"
    (root / "src" / "a.py").write_text("\n".join(lines) + "\n", encoding="utf-8")
    diff = parse(git(root, "diff"))

    (ref,) = select_hunks(diff, [("src/a.py", 1)])

    assert ref.hunk is None
    assert "not inside a changed hunk" in ref.render()


def test_a_pure_deletion_hunk_still_covers_the_line_it_removed() -> None:
    hunk = Hunk(text="@@ -4,2 +3,0 @@", start=3, count=0)
    assert hunk.covers(3) and hunk.covers(4)
    assert not hunk.covers(9)


# -- ticket_diff: what the review stage actually gets ------------------------------


def test_ticket_diff_starts_at_the_first_stage_commit(tmp_path: Path) -> None:
    root = repo(tmp_path)
    (root / "src" / "unrelated.py").write_text("before the ticket\n", encoding="utf-8")
    commit(root, "someone else's work")

    (root / "src" / "feature.py").write_text("the ticket's work\n", encoding="utf-8")
    commit(root, "flux(flux-1): implement", tag="flux/flux-1/implement")

    result = ticket_diff(root, ticket="flux-1")

    assert result.ok
    assert "feature.py" in result.text
    assert "unrelated.py" not in result.text, "the base is the ticket's own first commit"
    assert result.source == "stage-commits"


def test_ticket_diff_spans_every_stage_commit(tmp_path: Path) -> None:
    root = repo(tmp_path)
    (root / "tests" / "test_f.py").write_text("def test_f(): pass\n", encoding="utf-8")
    commit(root, "flux(flux-1): tests", tag="flux/flux-1/tests")
    (root / "src" / "feature.py").write_text("code\n", encoding="utf-8")
    commit(root, "flux(flux-1): implement", tag="flux/flux-1/implement")

    result = ticket_diff(root, ticket="flux-1")

    assert "test_f.py" in result.text
    assert "feature.py" in result.text


def test_ticket_diff_excludes_what_it_is_told_to(tmp_path: Path) -> None:
    root = repo(tmp_path)
    (root / "tests" / "test_f.py").write_text("def test_f(): pass\n", encoding="utf-8")
    (root / "src" / "test_beside.py").write_text("def test_g(): pass\n", encoding="utf-8")
    (root / "src" / "feature.py").write_text("code\n", encoding="utf-8")
    commit(root, "flux(flux-1): implement", tag="flux/flux-1/implement")

    result = ticket_diff(
        root,
        ticket="flux-1",
        exclude=(":(exclude,glob)tests/**", ":(exclude,glob)**/test_*.py"),
    )

    assert "feature.py" in result.text
    assert "test_f.py" not in result.text
    assert "test_beside.py" not in result.text, "a test beside the code is still a test"


def test_ticket_diff_includes_work_that_was_never_committed(tmp_path: Path) -> None:
    """``stage_commits = false``, or a commit that failed: the work is still the work."""
    root = repo(tmp_path)
    (root / "src" / "a.py").write_text(A_PY + "uncommitted change\n", encoding="utf-8")
    (root / "src" / "brand_new.py").write_text("never added to the index\n", encoding="utf-8")

    result = ticket_diff(root, ticket="flux-1")

    assert result.source == "worktree"
    assert "uncommitted change" in result.text
    assert "brand_new.py" in result.text, "an untracked new file is the most reviewable thing"
    assert result.untracked == ("src/brand_new.py",)


def test_ticket_diff_is_empty_when_nothing_changed(tmp_path: Path) -> None:
    root = repo(tmp_path)
    result = ticket_diff(root, ticket="flux-1")
    assert result.ok
    assert result.is_empty


def test_ticket_diff_reports_a_directory_that_is_not_a_repo(tmp_path: Path) -> None:
    result = ticket_diff(tmp_path, ticket="flux-1")
    assert not result.ok
    assert "not a git repository" in result.detail


def test_a_ticket_whose_first_stage_commit_is_the_root_commit(tmp_path: Path) -> None:
    """Diffing against the empty tree, rather than reporting no base and showing nothing."""
    root = tmp_path / "fresh"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "dev@example.com")
    git(root, "config", "user.name", "Dev")
    (root / "only.py").write_text("first ever commit\n", encoding="utf-8")
    commit(root, "flux(flux-1): implement", tag="flux/flux-1/implement")

    result = ticket_diff(root, ticket="flux-1")

    assert result.ok
    assert "first ever commit" in result.text
