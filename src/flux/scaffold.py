"""``flux init`` — lay down ``.flux/`` in a target repo (ADR 0006).

Two properties matter more than what gets written. First, **idempotence**: running
init twice is a no-op, and an existing ``flux.toml`` is never silently rewritten —
it is a repo's tuned gate suite, not scaffolding. Second, **honesty about gaps**: if
flux cannot tell what the repo is built with, it writes a config with no gates and
says so, rather than pretending a green pipeline means something.
"""

from __future__ import annotations

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
    _write(gitignore, FLUX_GITIGNORE.format(entries=entries), resolved, created, skipped)

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


def _config_warnings(config: FluxConfig) -> Sequence[str]:
    if config.gates:
        return ()
    return (
        f"no gates are configured for target {config.target!r} — flux cannot tell a good "
        f"change from a bad one until you add at least a test gate to {config.path}",
    )


def _write(path: Path, content: str, root: Path, created: list[str], skipped: list[str]) -> None:
    """Write ``content``, recording whether the file was new. Existing content that
    already matches is left untouched so init does not churn mtimes."""
    relative = _rel(path, root)
    if path.exists():
        try:
            if path.read_text(encoding="utf-8") == content:
                skipped.append(relative)
                return
        except (OSError, UnicodeDecodeError):
            pass
    write_atomic(path, content)
    created.append(relative)


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
