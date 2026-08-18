"""Adapters over bought knowledge tools (ADR 0009).

Nothing here extracts anything itself. flux owns the caching, the staleness signal and
the slicing; the extraction is a configured command.
"""

from __future__ import annotations

from flux.knowledge.repomap import (
    DEFAULT_MAP_COMMAND,
    IndexReport,
    RepoMap,
    RepoMapConfig,
    RepoMapEntry,
    cache_path,
    generate,
    load,
)

__all__ = [
    "DEFAULT_MAP_COMMAND",
    "IndexReport",
    "RepoMap",
    "RepoMapConfig",
    "RepoMapEntry",
    "cache_path",
    "generate",
    "load",
]
