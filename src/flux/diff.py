"""Unified diffs, parsed into files and hunks (design.md §2, stage I/O table).

The review stage hydrates from the ``git diff`` of the ticket's stage commits, and the
fix stage hydrates from *the hunks its findings point at* — never the whole diff again.
That second requirement is the whole reason this module exists: "referenced, not
pasted" (change-doc B4) is only implementable if a diff can be addressed by
``file:line``, which means parsing it rather than passing a string around.

Parsing is deliberately tolerant. A diff flux cannot fully understand still yields its
file blocks, because a review that silently drops a changed file is worse than one that
shows a block it could not decompose — the same rule the gate layer follows about
"could not check" never looking like "nothing to find".
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

_FILE_START = "diff --git "
_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$")
_GIT_PATHS = re.compile(r"^diff --git a/(.+) b/(.+)$")


@dataclass(frozen=True, slots=True)
class Hunk:
    """One ``@@`` block, addressed by its line range in the *new* file."""

    text: str
    """The hunk verbatim, header line included."""

    start: int
    """First line of the range this hunk covers in the new file."""

    count: int
    """How many lines of the new file it covers. Zero for a pure deletion."""

    heading: str = ""
    """Whatever git put after the second ``@@`` — usually the enclosing function."""

    @property
    def end(self) -> int:
        """One past the last line covered. ``start == end`` for a pure deletion."""
        return self.start + self.count

    def covers(self, line: int) -> bool:
        """Does this hunk contain ``line`` of the new file?

        A deletion covers the line it was deleted from: a finding about removed code
        points at the line where the removal happened, and there is nothing else to
        show for it.
        """
        if self.count == 0:
            return line == self.start or line == self.start + 1
        return self.start <= line < self.end


@dataclass(frozen=True, slots=True)
class FileDiff:
    """Every change to one file."""

    path: str
    """The new path, or the old one for a deletion. Relative to the repo root."""

    header: str
    """``diff --git`` through ``+++``: mode changes, renames, similarity — the part
    that is *about* the file rather than about a range inside it."""

    hunks: tuple[Hunk, ...] = ()
    """Empty for a block with no ranges — a binary file, a pure rename, a mode change.
    The header still carries what git said about it, so nothing disappears silently."""

    @property
    def text(self) -> str:
        parts = [self.header, *(hunk.text for hunk in self.hunks)]
        return "\n".join(part for part in parts if part).rstrip() + "\n"

    @property
    def changed_lines(self) -> int:
        """Added plus removed lines. The cheap size signal a summary line wants."""
        return sum(
            1
            for hunk in self.hunks
            for line in hunk.text.splitlines()[1:]
            if line[:1] in ("+", "-")
        )

    def hunk_at(self, line: int) -> Hunk | None:
        """The hunk covering ``line``, or ``None`` when no change touched it."""
        return next((hunk for hunk in self.hunks if hunk.covers(line)), None)


@dataclass(frozen=True, slots=True)
class Diff:
    """A parsed unified diff."""

    files: tuple[FileDiff, ...] = ()
    unparsed: str = ""
    """Anything before the first ``diff --git`` line. Normally empty."""

    @property
    def is_empty(self) -> bool:
        return not self.files and not self.unparsed.strip()

    @property
    def paths(self) -> tuple[str, ...]:
        return tuple(f.path for f in self.files)

    @property
    def changed_lines(self) -> int:
        return sum(f.changed_lines for f in self.files)

    def file(self, path: str) -> FileDiff | None:
        """The block for ``path``, matched exactly then by suffix.

        Suffix matching is there because a finding's ``file`` comes from a model, which
        writes ``src/flux/x.py`` or ``flux/x.py`` or ``x.py`` depending on what it was
        looking at. Refusing to resolve those would drop the hunk a finding is *about*,
        which is the only thing the fix stage is given.
        """
        exact = next((f for f in self.files if f.path == path), None)
        if exact is not None or not path:
            return exact
        needle = path.lstrip("./")
        matches = [f for f in self.files if f.path.endswith(f"/{needle}") or f.path == needle]
        return matches[0] if len(matches) == 1 else None

    def hunk_at(self, path: str, line: int) -> Hunk | None:
        block = self.file(path)
        return block.hunk_at(line) if block is not None else None

    def render(self, *, limit: int = 0) -> str:
        """The diff as text, truncated at whole files rather than mid-hunk.

        A half-shown hunk reads as a complete one, so the reviewer would judge code it
        cannot see. Dropping whole files and *naming* them keeps the omission visible.
        """
        rendered = self.unparsed.strip()
        kept: list[str] = [rendered] if rendered else []
        used = len(rendered)
        dropped: list[FileDiff] = []
        for block in self.files:
            text = block.text
            if limit and dropped:
                dropped.append(block)
                continue
            if limit and used + len(text) > limit and kept:
                dropped.append(block)
                continue
            kept.append(text)
            used += len(text)
        if dropped:
            names = "\n".join(
                f"- {block.path} ({block.changed_lines} changed line(s))" for block in dropped
            )
            kept.append(
                f"[diff truncated at {limit} characters — {len(dropped)} more changed "
                f"file(s) are NOT shown below:\n{names}\nJudge only what you can see, and "
                f"say in your summary that the diff was truncated.]"
            )
        return "\n".join(part.rstrip() for part in kept).strip()


def parse(text: str) -> Diff:
    """Split a unified diff into :class:`FileDiff` blocks. Never raises."""
    if not text.strip():
        return Diff()
    blocks: list[list[str]] = []
    preamble: list[str] = []
    for line in text.splitlines():
        if line.startswith(_FILE_START):
            blocks.append([line])
        elif blocks:
            blocks[-1].append(line)
        else:
            preamble.append(line)
    return Diff(
        files=tuple(_file_diff(block) for block in blocks),
        unparsed="\n".join(preamble),
    )


def _file_diff(lines: Sequence[str]) -> FileDiff:
    header: list[str] = []
    hunks: list[Hunk] = []
    current: list[str] = []
    started = False
    for line in lines:
        match = _HUNK.match(line)
        if match is not None:
            if current:
                hunks.append(_hunk(current))
            current = [line]
            started = True
        elif started:
            current.append(line)
        else:
            header.append(line)
    if current:
        hunks.append(_hunk(current))
    return FileDiff(
        path=_path(header),
        header="\n".join(header).rstrip(),
        hunks=tuple(hunks),
    )


def _hunk(lines: Sequence[str]) -> Hunk:
    match = _HUNK.match(lines[0])
    if match is None:  # unreachable: _file_diff only starts a hunk on a match
        return Hunk(text="\n".join(lines), start=0, count=0)
    start = int(match.group(3))
    count = 1 if match.group(4) is None else int(match.group(4))
    return Hunk(
        text="\n".join(lines).rstrip(),
        start=start,
        count=count,
        heading=match.group(5).strip(),
    )


def _path(header: Sequence[str]) -> str:
    """The file this block is about, preferring the new path.

    ``+++ /dev/null`` is a deletion, so the old path is the file's name; ``--- /dev/null``
    is a new file, which is the shape ``git diff --no-index`` produces for the untracked
    files the review diff has to reach for.
    """
    new = _marker(header, "+++ ")
    if new and new != "/dev/null":
        return new
    old = _marker(header, "--- ")
    if old and old != "/dev/null":
        return old
    match = _GIT_PATHS.match(header[0]) if header else None
    return match.group(2) if match else ""


def _marker(header: Sequence[str], prefix: str) -> str:
    line = next((entry for entry in header if entry.startswith(prefix)), "")
    if not line:
        return ""
    path = line[len(prefix) :].split("\t")[0].strip()
    return path[2:] if path[:2] in ("a/", "b/") else path


@dataclass(frozen=True, slots=True)
class HunkRef:
    """One hunk selected for a pack, plus why it was selected."""

    path: str
    hunk: Hunk | None
    note: str = ""
    """Why there is no hunk, when there is none — an unchanged line, an unchanged file."""

    key: tuple[str, int] = field(default=("", 0))

    def render(self) -> str:
        if self.hunk is None:
            return f"`{self.path}` — {self.note}"
        return f"`{self.path}`\n\n```diff\n{self.hunk.text}\n```"


def select_hunks(diff: Diff, targets: Iterable[tuple[str, int]]) -> tuple[HunkRef, ...]:
    """The hunks ``targets`` (``path``, ``line``) point at, deduplicated, in order.

    This is the fix stage's whole input from the diff: two findings inside one hunk
    cost one hunk, and a finding about a file the diff never touched costs a sentence
    saying so rather than the file's contents.
    """
    selected: list[HunkRef] = []
    seen: set[tuple[str, int]] = set()
    for path, line in targets:
        block = diff.file(path)
        if block is None:
            ref = HunkRef(path=path, hunk=None, note="not in this ticket's diff", key=(path, -1))
        else:
            hunk = block.hunk_at(line) if line > 0 else None
            if hunk is None:
                ref = HunkRef(
                    path=block.path,
                    hunk=None,
                    note=(
                        f"changed by this ticket, but line {line} is not inside a changed hunk"
                        if line > 0
                        else "changed by this ticket; no line was given"
                    ),
                    key=(block.path, -1),
                )
            else:
                ref = HunkRef(path=block.path, hunk=hunk, key=(block.path, hunk.start))
        if ref.key in seen:
            continue
        seen.add(ref.key)
        selected.append(ref)
    return tuple(selected)
