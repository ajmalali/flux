"""The opaque test runner (design.md §2, ADR 0005).

flux runs the suite itself and keeps a verdict, not a transcript: counts, failing test
ids, and the first assertion line. Never test source. Two different jobs need exactly
that shape and so share this module:

* the **gate** the implement stage faces, where the session may learn *what* broke but
  must not read the test that broke — pre-written tests plus "make these pass" is the
  canonical reward-hacking target, and a session that can read the assertion can write
  code shaped to that one assertion instead of to the requirement;
* the **red step** the tests stage is held to, where flux runs the newly written tests
  and requires them to fail for a reason it recognises.

Nothing here raises. A suite that could not run is a report that says so, because
"we could not check" must never reach the runner looking like "there was nothing to
find" (the same rule the gate layer follows).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from flux.proc import DEFAULT_TIMEOUT_S, CommandRun, clean_env, run_command, tail

MAX_NAMED_FAILURES = 10
"""Failing tests listed by name before the rest are counted. Ten names locate a break;
a hundred names are a wall of text that hides the same fact."""

_OUTCOME = re.compile(r"\b\d+ (?:passed|failed|errors?|skipped|xfailed|xpassed|deselected)\b")
_FAILED = re.compile(r"^(?:FAILED|ERROR) (\S+)", re.MULTILINE)
_ASSERTION = re.compile(r"^E\s{2,}(\S.*)$", re.MULTILINE)
_COUNT = re.compile(r"(\d+) (passed|failed|errors?|skipped|xfailed|xpassed|deselected)\b")
_COLLECTION_ERROR = re.compile(
    r"errors? during collection|Interrupted:\s*\d+\s*error", re.IGNORECASE
)

_NO_COUNTS: Mapping[str, int] = MappingProxyType({})


@dataclass(frozen=True, slots=True)
class TestReport:
    """What one test run did, in the only terms flux is allowed to keep."""

    command: tuple[str, ...] = ()
    ran: bool = False
    """False when the command never produced an exit status (missing binary, timeout)."""

    returncode: int = 0
    duration_ms: int = 0
    fault: str = ""
    """Why it never ran, when it did not."""

    summary: str = ""
    """pytest's own totals line, e.g. ``1 failed, 4 passed in 0.31s``."""

    counts: Mapping[str, int] = _NO_COUNTS
    failing: tuple[str, ...] = ()
    """Failing test ids, deduplicated and in the order the runner reported them."""

    first_assertion: str = ""
    collection_error: bool = False
    raw_tail: str = ""
    """Last few lines of output, kept only for runs this parser did not recognise."""

    @property
    def passed(self) -> int:
        return self.counts.get("passed", 0)

    @property
    def failed(self) -> int:
        return self.counts.get("failed", 0)

    @property
    def errors(self) -> int:
        return self.counts.get("error", 0)

    @property
    def green(self) -> bool:
        return self.ran and self.returncode == 0

    @property
    def all_red(self) -> bool:
        """Every test ran and every test failed on an assertion.

        Deliberately strict on both sides. A suite with a passing test in it is not a
        red step — it is a test that was already satisfied before the work started. A
        suite that *errored* is not a red step either: an import error or a broken
        fixture fails for a reason the implementation cannot fix, so it would go green
        the moment the file merely imports, whatever the assertion says.
        """
        return (
            self.ran
            and not self.collection_error
            and self.errors == 0
            and self.passed == 0
            and self.failed >= 1
        )

    def detail(self) -> str:
        """The opaque summary: counts, failing ids, first assertion. No test source."""
        if not self.ran:
            return self.fault
        lines = [self.summary] if self.summary else []
        if self.returncode == 0:
            return "\n".join(lines)
        shown = self.failing[:MAX_NAMED_FAILURES]
        lines.extend(shown)
        if len(self.failing) > len(shown):
            lines.append(f"… and {len(self.failing) - len(shown)} more")
        if self.first_assertion:
            lines.append(f"first assertion: {self.first_assertion}")
        return "\n".join(lines).strip() or self.raw_tail

    def to_json(self) -> dict[str, object]:
        """The structured half of the red-step evidence stored in ``tests.json``."""
        return {
            "command": list(self.command),
            "ran": self.ran,
            "returncode": self.returncode,
            "duration_ms": self.duration_ms,
            "summary": self.summary,
            "passed": self.passed,
            "failed": self.failed,
            "errors": self.errors,
            "collection_error": self.collection_error,
            "failing": list(self.failing[:MAX_NAMED_FAILURES]),
            "first_assertion": self.first_assertion,
            "fault": self.fault,
        }


def parse(run: CommandRun) -> TestReport:
    """Read a test runner's output into a :class:`TestReport`.

    Written against pytest's reporting, which is what ``kind = "pytest"`` declares.
    An unrecognised runner degrades to exit status plus the tail of its output —
    still a usable verdict, just a coarser one.
    """
    if not run.completed:
        return TestReport(
            command=run.argv,
            ran=False,
            returncode=run.returncode,
            duration_ms=run.duration_ms,
            fault=run.fault,
            raw_tail=tail(run.output),
        )
    output = run.output
    summary = _totals(output)
    return TestReport(
        command=run.argv,
        ran=True,
        returncode=run.returncode,
        duration_ms=run.duration_ms,
        summary=summary,
        counts=_counts(summary),
        failing=tuple(_dedupe(_FAILED.findall(output))),
        first_assertion=_first_assertion(output),
        collection_error=bool(_COLLECTION_ERROR.search(output)),
        raw_tail=tail(output),
    )


def run_tests(
    command: Sequence[str],
    *,
    cwd: Path,
    paths: Sequence[str] = (),
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> TestReport:
    """Run ``command`` (optionally narrowed to ``paths``) in ``cwd`` and report opaquely.

    The environment is cleaned for the same reason the gates' is: flux is itself a
    Python program launched from its own virtualenv, and an inherited ``VIRTUAL_ENV``
    would have the target repo's suite measured against *flux's* site-packages.
    """
    if not command:
        return TestReport(ran=False, fault="no test command is configured")
    argv = (*command, *paths)
    return parse(run_command(argv, cwd=cwd, timeout_s=timeout_s, env=clean_env()))


def _totals(output: str) -> str:
    """pytest's own totals line, decorated with ``=`` or not.

    Read from the bottom up and stripped of decoration because ``-q`` — which is in
    flux's own default gate command — prints the line bare, and a parser that only
    recognised the decorated form would report zero of everything for the exact
    command ``flux init`` writes.
    """
    for line in reversed(output.splitlines()):
        stripped = line.strip().strip("=").strip()
        if stripped and (_OUTCOME.search(stripped) or stripped.startswith("no tests ran")):
            return stripped
    return ""


def _counts(summary: str) -> Mapping[str, int]:
    """Per-outcome counts from pytest's totals line. ``errors`` is normalised to ``error``."""
    found = {
        name.rstrip("s") if name.startswith("error") else name: int(number)
        for number, name in _COUNT.findall(summary)
    }
    return MappingProxyType(found)


def _first_assertion(output: str) -> str:
    match = _ASSERTION.search(output)
    return match.group(1).strip() if match else ""


def _dedupe(values: list[str]) -> list[str]:
    """Order-preserving unique — pytest names a failure in more than one section."""
    return list(dict.fromkeys(values))
