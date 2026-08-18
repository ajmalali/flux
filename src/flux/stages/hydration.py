"""Shared pieces for building prompt packs out of disk (design.md §2, Rule 3).

Hydration is pure code: given the same files it produces the same pack, so "did the
handoff work?" is a pytest question. These helpers exist so every stage answers the
two recurring questions the same way — what to do when an optional input is absent,
and how to reference a prior artifact without pasting the whole of it.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from flux.fsio import read_json_mapping
from flux.jsonio import JsonMapping


def read_text(path: Path, *, limit: int = 20_000) -> str:
    """The file's contents, or ``""`` if it is absent or unreadable.

    Absence is normal: most context files are optional at M0, and a stage that
    refused to run without them would be unusable before the knowledge layer exists.
    """
    try:
        text = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return ""
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + f"\n\n[truncated at {limit} characters]"


def section(title: str, body: str) -> str:
    """A titled Markdown section, or ``""`` when there is no body to title."""
    stripped = body.strip()
    return f"## {title}\n\n{stripped}" if stripped else ""


def join(*parts: str) -> str:
    return "\n\n".join(part.strip() for part in parts if part.strip())


def bullets(items: Iterable[str]) -> str:
    return "\n".join(f"- {item}" for item in items if item)


def artifact_slice(path: Path, keys: Sequence[str]) -> JsonMapping:
    """Only the named keys of a JSON artifact.

    The handoff rule is reference-and-resolve, not concatenate (design.md §2): the
    next stage gets the fields it needs, so pack size does not grow with every stage
    that ran before it.
    """
    payload = read_json_mapping(path)
    if payload is None:
        return {}
    sliced: dict[str, Any] = {key: payload[key] for key in keys if key in payload}
    return sliced
