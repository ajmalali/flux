"""Summarisers: what the runner keeps from a gate's output.

Two jobs. The first is brevity — a gate's detail is stored on every metrics line, so
it must be a verdict, not a transcript. The second is *opacity* (design.md §2): the
implement session is not allowed to read test bodies, so the test gate reports which
tests failed and the first assertion line, never the source that produced them.
"""

from __future__ import annotations

import re

from flux.proc import CommandRun, tail

_RUFF_COUNT = re.compile(r"^Found \d+ errors?\b.*$", re.MULTILINE)
_RUFF_DIAGNOSTIC = re.compile(r"^\S+:\d+:\d+: ")
_PYRIGHT_COUNT = re.compile(r"^\s*\d+ errors?, \d+ warnings?, \d+ (?:informations?|notes?)", re.M)
_PYTEST_TOTALS = re.compile(r"^=+ (.*(?:passed|failed|error|no tests ran).*?) =+$", re.MULTILINE)
_PYTEST_FAILED = re.compile(r"^(?:FAILED|ERROR) (\S+)", re.MULTILINE)
_PYTEST_ASSERTION = re.compile(r"^E\s{2,}(\S.*)$", re.MULTILINE)
_COVERAGE_TOTAL = re.compile(r"^TOTAL\b.*?(\d+(?:\.\d+)?)%\s*$", re.MULTILINE)

MAX_NAMED_FAILURES = 10
"""Failing tests listed by name before the rest are counted. Ten names locate a break;
a hundred names are a wall of text that hides the same fact."""


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

    This is the opaque test runner of design.md §2 in its gate form: enough for the
    implement session's *next* attempt to know what broke, not enough for it to read
    the test and write code shaped to that one assertion.
    """
    output = run.output
    totals = _PYTEST_TOTALS.search(output)
    lines = [totals.group(1).strip()] if totals else []
    if run.returncode == 0:
        return "\n".join(lines)

    failures = _dedupe(_PYTEST_FAILED.findall(output))
    if failures:
        shown = failures[:MAX_NAMED_FAILURES]
        lines.extend(shown)
        if len(failures) > len(shown):
            lines.append(f"… and {len(failures) - len(shown)} more")
    assertion = _PYTEST_ASSERTION.search(output)
    if assertion:
        lines.append(f"first assertion: {assertion.group(1).strip()}")
    return "\n".join(lines).strip() or tail(output)


def coverage_percent(run: CommandRun) -> float | None:
    """Total line coverage from a ``coverage report`` table, or ``None`` if absent."""
    match = _COVERAGE_TOTAL.search(run.output)
    return float(match.group(1)) if match else None


def _dedupe(values: list[str]) -> list[str]:
    """Order-preserving unique — pytest names a failure in more than one section."""
    return list(dict.fromkeys(values))
