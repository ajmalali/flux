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
from dataclasses import dataclass
from pathlib import Path

from flux.proc import CommandRun, run_command, tail

GIT_TIMEOUT_S = 120

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


def stage_tag(ticket: str, stage: str) -> str:
    """The tag naming a stage's commit. Sanitised so it is always a legal ref."""
    return f"flux/{_safe(ticket)}/{_safe(stage)}"


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
