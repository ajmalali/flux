"""``flux init`` — lay down ``.flux/`` in a target repo (ADR 0006).

Two properties matter more than what gets written. First, **idempotence**: running
init twice is a no-op, and an existing ``flux.toml`` is never silently rewritten —
it is a repo's tuned gate suite, not scaffolding. Second, **honesty about gaps**: if
flux cannot tell what the repo is built with, it writes a config with no gates and
says so, rather than pretending a green pipeline means something.
"""

from __future__ import annotations

import shlex
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from flux.config import CONFIG_FILENAME, FluxConfig, default_gates, detect_target
from flux.errors import ConfigError
from flux.fsio import write_atomic
from flux.runner.context import FLUX_DIRNAME

GITIGNORE_FILENAME = ".gitignore"

COMMITTED_DIRS: tuple[str, ...] = ("research", "plans", "adr", "context")
"""Durable artifacts: the research, the plans, the ADRs, and the per-ticket handoffs.
These are the parts of a run a human reads six months later, so they go in git."""

IGNORED_DIRS: tuple[str, ...] = ("state", "transcripts", "usage", "cache")
"""Machine state: rebuildable by rerunning, and noisy in a diff."""

FLUX_GITIGNORE = """\
# Written by `flux init` (ADR 0006). Runtime state is rebuildable; artifacts are not.
{entries}
"""

GITKEEP = (
    "# Keeps this directory in git while it is empty. flux writes here; delete freely\n"
    "# once the directory has real content.\n"
)

POST_MERGE_HOOK = """\
#!/bin/sh
# Installed by `flux index --install-hook`: keep the repo map current after a merge
# (ADR 0009). Never fails the merge — a stale map is already detected and labelled at
# hydration time, so a ranker problem must not become a git problem.
{python} -m flux.cli index --root "$(git rev-parse --show-toplevel)" >/dev/null 2>&1 || true
"""

HOOK_MARKER = "flux index --install-hook"


@dataclass(frozen=True, slots=True)
class InitReport:
    """What ``flux init`` did, so the CLI can print it and tests can assert on it."""

    root: Path
    target: str
    created: tuple[str, ...] = ()
    """Paths created, relative to ``root``."""

    skipped: tuple[str, ...] = ()
    """Paths that already existed and were left alone."""

    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def config_path(self) -> Path:
        return self.root / FLUX_DIRNAME / CONFIG_FILENAME


def init_repo(root: Path, *, force: bool = False) -> InitReport:
    """Create ``<root>/.flux/`` with a config, a gitignore and the standard directories.

    Args:
        force: Rewrite ``flux.toml`` even if one exists. Everything else is written
            unconditionally, because the other files have no user-owned content.
    """
    resolved = root.resolve()
    if not resolved.is_dir():
        raise ConfigError(f"cannot initialise {resolved}: it is not a directory")

    created: list[str] = []
    skipped: list[str] = []
    warnings: list[str] = []
    flux_dir = resolved / FLUX_DIRNAME

    for name in (*COMMITTED_DIRS, *IGNORED_DIRS):
        directory = flux_dir / name
        if directory.is_dir():
            skipped.append(_rel(directory, resolved))
        else:
            directory.mkdir(parents=True, exist_ok=True)
            created.append(_rel(directory, resolved))
        # Git tracks files, not directories: a committed-but-empty directory would
        # simply vanish for the next clone. One that already has content does not
        # need the placeholder, and adding it to a live directory is just litter.
        if name in COMMITTED_DIRS and not any(directory.iterdir()):
            write_atomic(directory / ".gitkeep", GITKEEP)

    gitignore = flux_dir / GITIGNORE_FILENAME
    entries = "\n".join(f"{name}/" for name in IGNORED_DIRS)
    default = FLUX_GITIGNORE.format(entries=entries)
    # An existing .gitignore is never rewritten, not even under --force (which is
    # scoped to flux.toml). What a repo chooses to track is that repo's decision, and
    # silently restoring the default would revert it on the next init with no trace —
    # the same reason `flux index --install-hook` refuses to clobber a live hook.
    if gitignore.exists():
        skipped.append(_rel(gitignore, resolved))
        warnings.extend(_gitignore_warnings(gitignore, default))
    else:
        write_atomic(gitignore, default)
        created.append(_rel(gitignore, resolved))

    target = detect_target(resolved)
    config = FluxConfig(root=resolved, target=target, gates=default_gates(resolved))
    config_file = flux_dir / CONFIG_FILENAME
    if config_file.exists() and not force:
        skipped.append(_rel(config_file, resolved))
        warnings.extend(_config_warnings(FluxConfig.load(resolved)))
    else:
        write_atomic(config_file, config.to_toml())
        created.append(_rel(config_file, resolved))
        warnings.extend(_config_warnings(config))

    return InitReport(
        root=resolved,
        target=target,
        created=tuple(created),
        skipped=tuple(skipped),
        warnings=tuple(warnings),
    )


def install_post_merge_hook(root: Path, *, force: bool = False) -> tuple[Path, str]:
    """Write a ``post-merge`` hook that regenerates the repo map. Returns (path, note).

    Opt-in rather than part of ``flux init``: a git hook runs on every merge in a repo
    flux does not own, so installing one silently would be a surprise. An existing hook
    is never clobbered — the note says so and the user can merge the two lines by hand.
    """
    hooks = root / ".git" / "hooks"
    if not (root / ".git").exists():
        raise ConfigError(f"{root} is not a git repository, so it has no hooks directory")
    path = hooks / "post-merge"
    if path.exists() and not force:
        existing = _read(path)
        if HOOK_MARKER in existing:
            return path, "already installed"
        return path, "left alone: a post-merge hook already exists (pass --force to replace it)"
    hooks.mkdir(parents=True, exist_ok=True)
    write_atomic(path, POST_MERGE_HOOK.format(python=shlex.quote(sys.executable)))
    path.chmod(0o755)
    return path, "installed"


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _gitignore_warnings(path: Path, default: str) -> Sequence[str]:
    """Name the directories this repo tracks that the default would ignore.

    Not an error: tracking checkpoints or metrics is a legitimate choice (flux's own
    repo tracks `state/` so a run's checkpoints are part of the project record). It is
    said out loud because the consequence — `git add -A` in a stage commit sweeping
    those files up — is not visible from the .gitignore alone.
    """
    try:
        current = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ()
    if current == default:
        return ()
    # Patterns only: a comment explaining why `state/` is tracked mentions `state/`,
    # so a substring test over the whole file would read the explanation as the rule.
    patterns = {
        line.strip() for line in current.splitlines() if line.strip() and not line.startswith("#")
    }
    tracked = [name for name in IGNORED_DIRS if f"{name}/" not in patterns]
    if not tracked:
        return ()
    listed = ", ".join(f"{name}/" for name in tracked)
    return (
        f"{path.name} has been edited: this repo tracks {listed}, which flux would "
        "otherwise ignore. Left as it is.",
    )


def _config_warnings(config: FluxConfig) -> Sequence[str]:
    if config.gates:
        return ()
    return (
        f"no gates are configured for target {config.target!r} — flux cannot tell a good "
        f"change from a bad one until you add at least a test gate to {config.path}",
    )



def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
