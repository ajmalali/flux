"""Summarisers: what the runner keeps from a gate's output.

Two jobs. The first is brevity — a gate's detail is stored on every metrics line, so
it must be a verdict, not a transcript. The second is *opacity* (design.md §2): the
implement session is not allowed to read test bodies, so the test gate reports which
tests failed and the first assertion line, never the source that produced them.
"""

from __future__ import annotations

import re

from flux.proc import CommandRun, tail
from flux.testrun import MAX_NAMED_FAILURES
from flux.testrun import parse as parse_test_run

_RUFF_COUNT = re.compile(r"^Found \d+ errors?\b.*$", re.MULTILINE)
_RUFF_DIAGNOSTIC = re.compile(r"^\S+:\d+:\d+: ")
_PYRIGHT_COUNT = re.compile(r"^\s*\d+ errors?, \d+ warnings?, \d+ (?:informations?|notes?)", re.M)
_COVERAGE_TOTAL = re.compile(r"^TOTAL\b.*?(\d+(?:\.\d+)?)%\s*$", re.MULTILINE)

__all__ = [
    "MAX_NAMED_FAILURES",
    "coverage_percent",
    "pyright_summary",
    "pytest_summary",
    "ruff_summary",
]


def ruff_summary(run: CommandRun) -> str:
    """The first few diagnostics, plus ruff's own count line."""
    if run.returncode == 0:
        return ""
    output = run.output
    diagnostics = [line for line in output.splitlines() if _RUFF_DIAGNOSTIC.match(line)][:5]
    match = _RUFF_COUNT.search(output)
    parts = diagnostics + ([match.group(0)] if match else [])
    return "\n".join(parts).strip() or tail(output)


def pyright_summary(run: CommandRun) -> str:
    """Pyright's error/warning tally, plus the first few diagnostics."""
    if run.returncode == 0:
        return ""
    output = run.output
    match = _PYRIGHT_COUNT.search(output)
    diagnostics = [line.strip() for line in output.splitlines() if " - error: " in line][:5]
    parts = diagnostics + ([match.group(0).strip()] if match else [])
    return "\n".join(parts).strip() or tail(output)


def pytest_summary(run: CommandRun) -> str:
    """Counts, failing test ids, and the first assertion line — never test source.

    The gate form of the opaque runner in :mod:`flux.testrun`: same parser, so what a
    session may learn from a gate verdict and what the tests stage's red step records
    cannot drift apart.
    """
    return parse_test_run(run).detail() or tail(run.output)


def coverage_percent(run: CommandRun) -> float | None:
    """Total line coverage from a ``coverage report`` table, or ``None`` if absent."""
    match = _COVERAGE_TOTAL.search(run.output)
    return float(match.group(1)) if match else None
