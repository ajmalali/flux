"""The repo map: which files matter, ranked, with no LLM in the loop (ADR 0009).

flux does not compute this itself — the extractor is bought, and which tool provides it
is configuration (``[repo_map] command``), the same seam the gate suite uses. What flux
owns is the part a tool cannot: caching the result under ``.flux/cache/``, knowing when
it went stale, and slicing it to a size a prompt pack can afford.

The default command runs the tool through ``uvx`` rather than depending on it. A
zero-LLM ranker that would drag an LLM SDK into flux's own dependency tree is a bad
trade, and keeping it a command means a repo can point at a different ranker without
touching flux.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from flux.errors import ConfigError, FluxError
from flux.fsio import read_json_mapping, write_json_atomic
from flux.jsonio import JsonMapping, as_json_list, as_json_mapping
from flux.proc import DEFAULT_TIMEOUT_S, clean_env, run_command, tail
from flux.runner.context import FLUX_DIRNAME

CACHE_DIRNAME = "cache"
REPO_MAP_FILENAME = "repo-map.json"
SCHEMA_VERSION = 1
OVERFETCH = 3
"""How many times ``top`` to request, so exclusions do not shrink the kept map."""

DEFAULT_MAP_COMMAND: tuple[str, ...] = ("uvx", "--from", "repowiki", "repowiki", "map")
"""``repowiki map`` — chosen over Aider's RepoMapper fork in the T4b bake-off; see
``.flux/plans/flux-harness/repo-map-memo.md``."""


@dataclass(frozen=True, slots=True)
class RepoMapConfig:
    """How to produce the map and how much of it a pack may carry."""

    command: tuple[str, ...] = DEFAULT_MAP_COMMAND
    top: int = 60
    """Entries to keep in the cache."""

    pack_entries: int = 25
    """Entries a stage's context pack may carry. Smaller than :attr:`top` on purpose:
    the cache is for humans and future slicing, the pack is on a token budget."""

    timeout_s: int = DEFAULT_TIMEOUT_S
    exclude_prefixes: tuple[str, ...] = (f"{FLUX_DIRNAME}/",)
    """Paths dropped from the map. flux's own artifacts are not the repo's code, and a
    ranker that sees them will happily rank them."""

    def __post_init__(self) -> None:
        if not self.command:
            raise ConfigError("[repo_map] command must not be empty")
        for name, value in (("top", self.top), ("pack_entries", self.pack_entries)):
            if value <= 0:
                raise ConfigError(f"[repo_map] {name} must be positive, got {value}")
        if self.timeout_s <= 0:
            raise ConfigError(f"[repo_map] timeout_s must be positive, got {self.timeout_s}")


@dataclass(frozen=True, slots=True)
class RepoMapEntry:
    """One ranked file."""

    path: str
    score: float = 0.0
    language: str = ""
    lines: int = 0

    def to_json(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "score": self.score,
            "language": self.language,
            "lines": self.lines,
        }

    @classmethod
    def from_json(cls, payload: JsonMapping) -> RepoMapEntry:
        return cls(
            path=str(payload.get("path", "")),
            score=_float(payload.get("score")),
            language=str(payload.get("language", "")),
            lines=_int(payload.get("lines")),
        )


@dataclass(frozen=True, slots=True)
class RepoMap:
    """A generated map plus the provenance needed to distrust it later."""

    entries: tuple[RepoMapEntry, ...] = ()
    file_count: int = 0
    generated_at: str = ""
    head: str = ""
    """Git HEAD when the map was generated. How staleness is detected — a map that
    silently describes an older tree is worse than no map (plan.md §7)."""

    command: tuple[str, ...] = ()
    schema_version: int = SCHEMA_VERSION

    def is_stale(self, head: str) -> bool:
        """True when the worktree has moved on from what was mapped."""
        return bool(self.head) and bool(head) and self.head != head

    def render(self, *, limit: int = 25) -> str:
        """A compact ranked list for a prompt pack."""
        shown = self.entries[:limit]
        if not shown:
            return ""
        width = max(len(e.path) for e in shown)
        rows = [f"{e.path.ljust(width)}  {e.score:.3f}  {e.lines:>5} lines" for e in shown]
        more = len(self.entries) - len(shown)
        if more > 0:
            rows.append(f"… and {more} further files, less central to the import graph")
        return "\n".join(rows)

    def to_json(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at or _now_iso(),
            "head": self.head,
            "command": list(self.command),
            "file_count": self.file_count,
            "entries": [e.to_json() for e in self.entries],
        }

    @classmethod
    def from_json(cls, payload: JsonMapping) -> RepoMap:
        entries = tuple(_map_entries(payload.get("entries")))
        command = as_json_list(payload.get("command")) or []
        return cls(
            entries=entries,
            file_count=_int(payload.get("file_count")),
            generated_at=str(payload.get("generated_at", "")),
            head=str(payload.get("head", "")),
            command=tuple(str(part) for part in command),
            schema_version=_int(payload.get("schema_version")) or SCHEMA_VERSION,
        )


@dataclass(frozen=True, slots=True)
class IndexReport:
    """What one ``flux index`` run did."""

    map: RepoMap
    path: Path
    duration_ms: int = 0
    warnings: tuple[str, ...] = field(default_factory=tuple)


def cache_path(root: Path) -> Path:
    return root / FLUX_DIRNAME / CACHE_DIRNAME / REPO_MAP_FILENAME


def load(root: Path) -> RepoMap | None:
    """The cached map, or ``None`` if it was never generated or is unreadable."""
    payload = read_json_mapping(cache_path(root))
    return RepoMap.from_json(payload) if payload else None


def generate(root: Path, config: RepoMapConfig, *, head: str = "") -> IndexReport:
    """Run the configured ranker over ``root`` and cache what it returns.

    Raises:
        FluxError: the command could not run or did not return usable JSON. This is a
            user-invoked command, so failing loudly beats caching an empty map that
            would later look like "this repo has no important files".
    """
    # Ask for more than we keep: excluded paths are filtered *after* the ranker has
    # chosen its top N, so requesting exactly `top` would silently shrink the map by
    # however many flux-owned files happened to rank.
    requested = config.top * OVERFETCH
    argv = [*config.command, str(root), "--format", "json", "-n", str(requested)]
    run = run_command(argv, cwd=root, timeout_s=config.timeout_s, env=clean_env())
    if not run.completed:
        raise FluxError(f"repo map command failed: {run.fault}")
    if run.returncode != 0:
        why = tail(run.output, lines=5) or "(no output)"
        raise FluxError(f"repo map command exited {run.returncode}: {why}")

    payload = _parse(run.stdout)
    entries, dropped = _entries(payload, config)
    generated = RepoMap(
        entries=entries,
        file_count=_int(payload.get("file_count")),
        generated_at=_now_iso(),
        head=head,
        command=tuple(config.command),
    )
    write_json_atomic(cache_path(root), generated.to_json())

    warnings: list[str] = []
    if not entries:
        warnings.append("the ranker returned no files — check the command and the repo path")
    if dropped:
        warnings.append(f"dropped {dropped} flux-owned path(s) from the map")
    return IndexReport(
        map=generated,
        path=cache_path(root),
        duration_ms=run.duration_ms,
        warnings=tuple(warnings),
    )


def _parse(stdout: str) -> JsonMapping:
    """Read the ranker's JSON, tolerating leading progress chatter on stdout."""
    text = stdout.strip()
    start = text.find("{")
    if start < 0:
        raise FluxError("repo map command produced no JSON object on stdout")
    try:
        parsed: Any = json.loads(text[start:])
    except json.JSONDecodeError as exc:
        raise FluxError(f"repo map output is not valid JSON: {exc.msg}") from exc
    payload = as_json_mapping(parsed)
    if payload is None:
        raise FluxError("repo map output is not a JSON object")
    return payload


def _entries(payload: JsonMapping, config: RepoMapConfig) -> tuple[tuple[RepoMapEntry, ...], int]:
    if as_json_list(payload.get("entries")) is None:
        raise FluxError("repo map output has no 'entries' array")
    parsed = list(_map_entries(payload.get("entries")))
    kept = [e for e in parsed if e.path and not _excluded(e.path, config.exclude_prefixes)]
    return tuple(kept[: config.top]), len(parsed) - len(kept)


def _map_entries(raw: object) -> Iterator[RepoMapEntry]:
    """Every well-formed entry in a JSON array, skipping anything that is not an object."""
    for item in as_json_list(raw) or ():
        mapping = as_json_mapping(item)
        if mapping is not None:
            yield RepoMapEntry.from_json(mapping)


def _excluded(path: str, prefixes: Sequence[str]) -> bool:
    return any(path.startswith(prefix) for prefix in prefixes)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _float(value: object) -> float:
    if isinstance(value, bool):
        return 0.0
    return float(value) if isinstance(value, int | float) else 0.0
