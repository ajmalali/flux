"""Crash-safe file writes.

The runner's guarantee is "resume is rerun" (design.md §1), and that only holds if a
checkpoint that *exists* is also *complete*. A reader must never see a half-written
state file, so every write goes to a temporary file in the same directory, is fsynced,
and is then moved into place with :func:`os.replace` — atomic on POSIX. The parent
directory is fsynced afterwards so the rename itself survives a power loss.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from flux.jsonio import JsonMapping, as_json_mapping


def write_atomic(path: Path, data: str, *, encoding: str = "utf-8") -> Path:
    """Write ``data`` to ``path`` atomically, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with tmp.open("w", encoding=encoding) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    _fsync_dir(path.parent)
    return path


def write_json_atomic(path: Path, payload: Mapping[str, Any]) -> Path:
    """Write ``payload`` as indented JSON. Indented because humans read these files."""
    return write_atomic(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def read_json_mapping(path: Path) -> JsonMapping | None:
    """Read a JSON object from ``path``, or ``None`` if it is absent or unreadable.

    Corruption is reported as absence on purpose: state files are rebuildable by
    rerunning the stage, so an unparseable one must not wedge the ticket.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    try:
        payload: Any = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return as_json_mapping(payload)


def _fsync_dir(directory: Path) -> None:
    """Best-effort directory fsync; not every platform permits opening a directory."""
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)
