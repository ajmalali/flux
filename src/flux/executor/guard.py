"""``PathGuard`` — what a stage's session is structurally prevented from touching.

ADR 0005's hardening is structural, not behavioural: the implement session is not
*asked* to leave the tests alone, it is stopped. The mechanism is a ``PreToolUse``
hook, and this module is its flux-side half — pure data plus one pure decision
function, so the whole policy is testable without a session and without the SDK
(ADR 0007). ``executor/sdk.py`` is the only place that turns a guard into a hook.

Two shapes cover both stages that need one:

* **deny** (``deny_dirs`` / ``deny_globs``) — the implement and fix stages may write
  anything *except* the tests. Pre-written tests plus "make these pass" is the
  canonical reward-hacking target, so the tests are the one thing the stage under
  test may not reach.
* **allow-only** (``only_dirs``) — the tests stage may write *only* tests. A tests
  stage that can also edit the implementation can make its own tests pass, which
  would make the red step it is judged on meaningless.

**What a guard does not cover, on purpose.** It reads the path arguments of
path-taking tools. A session that shells out (``sed -i``, a heredoc) is not stopped
here, and a repo-wide ``Grep`` can still surface a line of a test file. Those are
covered downstream instead, where evidence beats prediction: ``Bash`` is limited to
the pre-approved gate commands, and the implement stage re-hashes every test file
before it is allowed to stand, so a test edited by any route at all fails the stage.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from flux.errors import ConfigError

EDIT_TOOLS: tuple[str, ...] = ("Edit", "Write", "MultiEdit", "NotebookEdit")
"""Tools that change a file. The allow-only guards use exactly these."""

READ_TOOLS: tuple[str, ...] = ("Read", "NotebookRead", "Grep", "Glob")
"""Tools that surface a file's contents and take an explicit path."""

_PATH_KEYS: tuple[str, ...] = ("file_path", "notebook_path", "path")
"""Tool-input keys that name a file or directory. ``Grep``/``Glob`` use ``path``."""


@dataclass(frozen=True, slots=True)
class PathGuard:
    """A ``PreToolUse`` policy over the paths a tool call names."""

    name: str
    reason: str
    """Said back to the model verbatim when a call is denied. It is the only
    explanation the session gets, so it states what to do instead, not just what is
    forbidden — a session that cannot tell why it was blocked retries the same call."""

    tools: tuple[str, ...] = EDIT_TOOLS
    root: Path = Path()
    """Absolute directory relative paths in tool input are resolved against."""

    deny_dirs: tuple[Path, ...] = ()
    deny_globs: tuple[str, ...] = ()
    """Basename patterns denied wherever they appear — a stray ``test_x.py`` next to
    the code it tests is still a test."""

    only_dirs: tuple[Path, ...] = ()
    """When set, every path outside these directories is denied."""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ConfigError("a PathGuard needs a non-empty name")
        if not self.reason.strip():
            raise ConfigError(f"guard {self.name!r} needs a reason to give the model")
        if not self.tools:
            raise ConfigError(f"guard {self.name!r} matches no tools")
        if not (self.deny_dirs or self.deny_globs or self.only_dirs):
            raise ConfigError(f"guard {self.name!r} forbids nothing")
        for directory in (*self.deny_dirs, *self.only_dirs):
            if not directory.is_absolute():
                raise ConfigError(
                    f"guard {self.name!r}: guarded directories must be absolute, got {directory}"
                )

    @property
    def matcher(self) -> str:
        """The SDK's tool-name matcher, e.g. ``Edit|Write|MultiEdit``."""
        return "|".join(self.tools)

    def paths(self, tool_input: Mapping[str, Any]) -> tuple[Path, ...]:
        """Every path this tool call names, resolved. Unknown shapes name none."""
        found: list[Path] = []
        for key in _PATH_KEYS:
            raw: object = tool_input.get(key)
            if isinstance(raw, str) and raw:
                found.append(self._resolve(raw))
        return tuple(found)

    def decide(self, tool: str, tool_input: Mapping[str, Any]) -> str:
        """The denial to send back, or ``""`` to let the call through."""
        if tool not in self.tools:
            return ""
        for path in self.paths(tool_input):
            if self._forbidden(path):
                return f"{tool} on {path} was blocked by flux: {self.reason}"
        return ""

    def _forbidden(self, path: Path) -> bool:
        if self.only_dirs and not any(_within(path, d) for d in self.only_dirs):
            return True
        if any(_within(path, directory) for directory in self.deny_dirs):
            return True
        return any(fnmatch(path.name, pattern) for pattern in self.deny_globs)

    def _resolve(self, raw: str) -> Path:
        path = Path(raw)
        return (path if path.is_absolute() else self.root / path).resolve()


def guarded_dirs(*candidates: Path | None) -> tuple[Path, ...]:
    """Absolute, deduplicated, in order — the shape a guard's directory fields want.

    ``None`` entries drop out so a caller can pass an optional directory (a ticket
    with no held-out tests, say) without branching at every call site.
    """
    seen: dict[Path, None] = {}
    for candidate in candidates:
        if candidate is not None:
            seen.setdefault(candidate.resolve(), None)
    return tuple(seen)


def _within(path: Path, directory: Path) -> bool:
    resolved = directory.resolve()
    return path == resolved or resolved in path.parents
