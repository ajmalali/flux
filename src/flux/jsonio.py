"""Narrowing helpers for values that came out of :func:`json.loads`.

``json.loads`` returns ``Any``; ``isinstance(x, dict)`` narrows it to
``dict[Unknown, Unknown]``, which strict type checking rightly rejects. JSON object
keys are always strings, so one cast in one place beats a cast at every call site.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

JsonMapping = Mapping[str, Any]


def as_json_mapping(value: object) -> JsonMapping | None:
    """Return ``value`` as a string-keyed mapping, or ``None`` if it is not an object."""
    if isinstance(value, dict):
        return cast(JsonMapping, value)
    return None


def as_json_list(value: object) -> list[object] | None:
    """Return ``value`` as a list of unknowns, or ``None`` if it is not an array.

    Returning the narrowed value beats an ``isinstance`` guard at the call site: the
    guard narrows to ``list[Unknown]``, which strict type checking then rejects at
    every use.
    """
    if isinstance(value, list):
        return cast(list[object], value)
    return None
