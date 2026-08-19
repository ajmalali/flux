"""Stage commits: one commit per stage, tagged ``flux/<ticket>/<stage>`` (design.md §1).

This is what makes "reset to the last good stage" a ``git reset --hard`` instead of
bookkeeping the runner would have to invent. A stage's work is therefore recorded where
the work already is — in the worktree's history — and the checkpoint only has to name
the commit.

Nothing here is allowed to break a pipeline: a worktree that is not a git repo, a repo
with nothing to commit, and a git that is not installed all come back as an unsuccessful
:class:`CommitResult` the caller can record. Committing is provenance, not a gate.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from flux.proc import CommandRun, run_command, tail

GIT_TIMEOUT_S = 120

EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
"""Git's constant hash for the empty tree — the base a root commit is diffed against."""

MAX_UNTRACKED_FILES = 25
"""Untracked files rendered into a review diff before the rest are only named. A stage
that created two dozen new files has a review problem the diff cannot fix."""

FALLBACK_NAME = "flux"
FALLBACK_EMAIL = "flux@localhost"

# Git refuses control characters, spaces, '~^:?*[', '..', '@{' and a trailing '.' in
# ref names. Ticket ids are already restricted by TicketContext; stage names are ours.
_UNSAFE_REF = re.compile(r"[^A-Za-z0-9._/-]")


@dataclass(frozen=True, slots=True)
class CommitResult:
    """What a stage commit attempt did."""

    ok: bool
    committed: bool = False
    """False with ``ok`` means the tree was already clean — nothing to record."""

    sha: str = ""
    tag: str = ""
    detail: str = ""

    def to_detail(self) -> dict[str, str | bool]:
        """The checkpoint-friendly form, for ``Outcome.detail``."""
        return {"committed": self.committed, "sha": self.sha, "tag": self.tag}


def is_git_repo(worktree: Path) -> bool:
    return _git(["rev-parse", "--git-dir"], worktree).returncode == 0


def head_sha(worktree: Path) -> str:
    """The worktree's current commit, or ``""`` if there is none to read.

    Used as the staleness signal for generated artifacts: what a cached map describes
    is the tree at this commit.
    """
    run = _git(["rev-parse", "HEAD"], worktree)
    return run.stdout.strip() if run.returncode == 0 else ""


def stage_tag_prefix(ticket: str) -> str:
    """Everything this ticket's stage tags share. The handle for finding them again."""
    return f"flux/{_safe(ticket)}/"


def stage_tag(ticket: str, stage: str) -> str:
    """The tag naming a stage's commit. Sanitised so it is always a legal ref."""
    return f"{stage_tag_prefix(ticket)}{_safe(stage)}"


def stage_commit(worktree: Path, *, ticket: str, stage: str, message: str) -> CommitResult:
    """Commit everything in ``worktree`` and tag it for this ``(ticket, stage)``.

    ``git add -A`` is deliberate: a stage's output is whatever it left in the worktree,
    and a stage that created an untracked file did work the next stage must see.
    """
    tag = stage_tag(ticket, stage)
    if not is_git_repo(worktree):
        return CommitResult(ok=False, tag=tag, detail=f"{worktree} is not a git repository")

    status = _git(["status", "--porcelain"], worktree)
    if status.returncode != 0:
        return CommitResult(ok=False, tag=tag, detail=_why("git status", status))
    if not status.stdout.strip():
        return CommitResult(ok=True, committed=False, tag=tag, detail="nothing to commit")

    added = _git(["add", "-A"], worktree)
    if added.returncode != 0:
        return CommitResult(ok=False, tag=tag, detail=_why("git add", added))

    commit = _git([*_identity(worktree), "commit", "-m", message], worktree)
    if commit.returncode != 0:
        return CommitResult(ok=False, tag=tag, detail=_why("git commit", commit))

    head = _git(["rev-parse", "HEAD"], worktree)
    sha = head.stdout.strip() if head.returncode == 0 else ""
    tagged = _git(["tag", "-f", tag], worktree)
    detail = "" if tagged.returncode == 0 else _why("git tag", tagged)
    return CommitResult(ok=True, committed=True, sha=sha, tag=tag, detail=detail)


@dataclass(frozen=True, slots=True)
class DiffResult:
    """The change a ticket has made so far, as text plus how it was located."""

    ok: bool
    text: str = ""
    base: str = ""
    """The commit the diff starts from. Empty when there was none to find."""

    source: str = ""
    """``stage-commits`` when the ticket's own tags bounded it, ``worktree`` when
    nothing was committed and the diff is against HEAD. Recorded because the two
    answer slightly different questions and a reviewer should not have to guess."""

    untracked: tuple[str, ...] = ()
    """New files the diff includes by way of ``--no-index``, plus any it had to omit."""

    omitted: tuple[str, ...] = ()
    detail: str = ""
    """Why there is no diff, when there is none."""

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()


def ticket_diff(
    worktree: Path,
    *,
    ticket: str,
    exclude: Sequence[str] = (),
) -> DiffResult:
    """Everything this ticket changed, from its first stage commit to the working tree.

    The base is derived from the ticket's own stage tags (``flux/<ticket>/<stage>``), so
    a review sees the ticket's work and not whatever else the branch already carried.
    The end is the *working tree* rather than HEAD: a stage whose commit failed, or a
    repo with ``stage_commits`` off, has still done the work, and a review that silently
    omitted it would be a review of nothing.

    ``exclude`` takes git pathspecs — the review diff uses them to keep the test files
    out, since the stages downstream of ``tests`` may not read them (ADR 0005).
    """
    if not is_git_repo(worktree):
        return DiffResult(ok=False, detail=f"{worktree} is not a git repository")

    base, source, problem = _diff_base(worktree, ticket)
    if problem:
        return DiffResult(ok=False, detail=problem)

    pathspecs = ["--", ".", *exclude]
    tracked = _git(["diff", base, *pathspecs], worktree)
    if tracked.returncode != 0:
        return DiffResult(ok=False, base=base, source=source, detail=_why("git diff", tracked))

    new_files, omitted, rendered = _untracked_diffs(worktree, exclude)
    text = "\n".join(part for part in (tracked.stdout, rendered) if part.strip())
    return DiffResult(
        ok=True,
        text=text,
        base=base,
        source=source,
        untracked=new_files,
        omitted=omitted,
    )


def _diff_base(worktree: Path, ticket: str) -> tuple[str, str, str]:
    """``(base, source, problem)`` — where this ticket's changes start.

    With stage tags present the base is the *parent* of the earliest of them, which is
    the tree as it stood before flux touched it. With none, HEAD is the only honest
    answer: nothing has been committed, so everything in the working tree is the work.
    """
    shas = _stage_commits(worktree, ticket)
    if not shas:
        return "HEAD", "worktree", ""
    earliest = _earliest(worktree, shas)
    if not earliest:
        return "", "", f"could not order the stage commits for ticket {ticket!r}"
    parent = _git(["rev-parse", "--verify", f"{earliest}^"], worktree)
    if parent.returncode != 0:
        # The first stage commit is the repo's root commit: diff against the empty tree
        # rather than reporting no base, or the review would see nothing at all.
        return EMPTY_TREE, "stage-commits", ""
    return parent.stdout.strip(), "stage-commits", ""


def _stage_commits(worktree: Path, ticket: str) -> tuple[str, ...]:
    """Commit shas behind this ticket's ``flux/<ticket>/*`` tags."""
    listed = _git(["tag", "--list", f"{stage_tag_prefix(ticket)}*"], worktree)
    if listed.returncode != 0:
        return ()
    shas: list[str] = []
    for tag in listed.stdout.split():
        run = _git(["rev-parse", "--verify", f"{tag}^{{commit}}"], worktree)
        if run.returncode == 0 and run.stdout.strip():
            shas.append(run.stdout.strip())
    return tuple(dict.fromkeys(shas))


def _earliest(worktree: Path, shas: Sequence[str]) -> str:
    """The oldest of ``shas``. On the linear history stages produce, their merge base."""
    if len(shas) == 1:
        return shas[0]
    run = _git(["merge-base", "--octopus", *shas], worktree)
    return run.stdout.strip() if run.returncode == 0 else ""


def _untracked_diffs(
    worktree: Path, exclude: Sequence[str]
) -> tuple[tuple[str, ...], tuple[str, ...], str]:
    """New files rendered as diffs, since ``git diff`` alone cannot see them.

    A whole new module is the most reviewable thing a ticket produces and the easiest
    to lose: it is untracked until something commits it, and ``git diff`` shows nothing.
    ``--no-index`` against ``/dev/null`` produces the ordinary diff shape for one.
    """
    listed = _git(["ls-files", "--others", "--exclude-standard", "--", ".", *exclude], worktree)
    if listed.returncode != 0:
        return (), (), ""
    paths = [line for line in listed.stdout.splitlines() if line.strip()]
    shown, omitted = paths[:MAX_UNTRACKED_FILES], tuple(paths[MAX_UNTRACKED_FILES:])
    blocks: list[str] = []
    included: list[str] = []
    for path in shown:
        run = _git(["diff", "--no-index", "--", "/dev/null", path], worktree)
        # --no-index exits 1 when the files differ, which is always the case here.
        if run.stdout.strip():
            blocks.append(run.stdout.rstrip())
            included.append(path)
    return tuple(included), omitted, "\n".join(blocks)


def _identity(worktree: Path) -> list[str]:
    """A committer identity only when the repo has none.

    A scratch or CI checkout often has no ``user.email``, and a stage failing on that
    would be a confusing way to learn it. A repo that *has* an identity keeps it.
    """
    configured = _git(["config", "--get", "user.email"], worktree)
    if configured.returncode == 0 and configured.stdout.strip():
        return []
    return ["-c", f"user.name={FALLBACK_NAME}", "-c", f"user.email={FALLBACK_EMAIL}"]


def _git(args: list[str], worktree: Path) -> CommandRun:
    return run_command(["git", *args], cwd=worktree, timeout_s=GIT_TIMEOUT_S)


def _why(what: str, run: CommandRun) -> str:
    if not run.launched:
        return f"{what} could not run: {run.fault}"
    if run.timed_out:
        return f"{what} timed out"
    return f"{what} failed: {tail(run.output, lines=3, limit=400) or run.returncode}"


def _safe(part: str) -> str:
    return _UNSAFE_REF.sub("-", part).strip("./-") or "unnamed"
