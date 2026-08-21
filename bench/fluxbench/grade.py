"""The quality axis: did the arm actually deliver the task?

ADR 0011 in the v1 archive records why this file exists and why it is not just
"run the repo's test suite". The repo's own suite stays green when a session
changes nothing at all, so grading on it alone scores "did nothing" identically
to "shipped the feature" -- and a kill-criterion computed that way can fire
against the arm that delivered.

So every task ships **held-out acceptance tests**, written before any arm runs
and kept outside every arm's worktree. After an arm finishes a task the tests
are copied in, run, and removed. Two verdicts come out of it:

* ``accept`` -- the task's own acceptance tests pass, i.e. the feature exists;
* ``gate``   -- the repo's pre-existing suite still passes, i.e. nothing was
  broken to get there.

An arm needs both. Either alone is gameable.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

ACCEPT_DIRNAME = "_accept"
# Python >= 3.11 prints "test_x (pkg.Mod.Class.test_x)"; older prints "test_x (pkg.Mod.Class)".
_TEST_LINE = re.compile(r"^(?P<name>[\w.]+) \((?P<id>[\w.]+)\)[^)]*\.\.\. (?P<verdict>ok|FAIL|ERROR|skipped.*)$")


@dataclass
class GradeResult:
    accept_ran: bool = False
    accept_ok: bool = False
    accept_total: int = 0
    accept_passed: int = 0
    gate_ran: bool = False
    gate_ok: bool = False
    files_changed: int = 0
    lines_added: int = 0
    lines_removed: int = 0
    contaminated: bool = False
    detail: Dict[str, str] = field(default_factory=dict)
    failures: List[str] = field(default_factory=list)

    @property
    def delivered(self) -> bool:
        """The only definition of success the report is allowed to use."""
        return self.accept_ran and self.accept_ok and (not self.gate_ran or self.gate_ok)

    def to_json(self) -> Dict[str, object]:
        payload = dict(self.__dict__)
        payload["delivered"] = self.delivered
        return payload


def _run(command: str, cwd: Path, timeout_s: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=str(cwd),
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )


def _count_unittest(output: str) -> "tuple[int, int, List[str]]":
    total = passed = 0
    failures: List[str] = []
    for line in output.splitlines():
        m = _TEST_LINE.match(line.strip())
        if not m:
            continue
        total += 1
        verdict = m.group("verdict")
        if verdict == "ok" or verdict.startswith("skipped"):
            passed += 1
        else:
            ident = m.group("id")
            failures.append(ident if ident.endswith(m.group("name")) else "%s.%s" % (ident, m.group("name")))
    if total == 0:  # fall back to the summary line when -v output is unavailable
        m = re.search(r"^Ran (\d+) tests?", output, re.M)
        if m:
            total = int(m.group(1))
            passed = total if re.search(r"^OK", output, re.M) else 0
    return total, passed, failures


def diff_stats(repo: Path, since: str) -> "tuple[int, int, int]":
    proc = _run("git diff --numstat %s -- ." % since, repo)
    files = added = removed = 0
    for line in proc.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        files += 1
        if parts[0].isdigit():
            added += int(parts[0])
        if parts[1].isdigit():
            removed += int(parts[1])
    return files, added, removed


def grade(
    repo: Path,
    accept_dir: Optional[Path],
    accept_command: str,
    gate_command: str,
    since: Optional[str] = None,
) -> GradeResult:
    result = GradeResult()

    if gate_command:
        proc = _run(gate_command, repo)
        result.gate_ran = True
        result.gate_ok = proc.returncode == 0
        if not result.gate_ok:
            result.detail["gate"] = (proc.stdout + proc.stderr)[-2000:]

    if accept_dir is not None and accept_dir.is_dir():
        target = repo / ACCEPT_DIRNAME
        # An arm that created its own _accept/ would be graded against its own
        # tests. Refuse rather than record a number that means nothing.
        result.contaminated = target.exists()
        if result.contaminated:
            shutil.rmtree(target)
        shutil.copytree(accept_dir, target)
        # unittest discovery with `-t .` needs the accept directory to be an
        # importable package, otherwise the repo root never reaches sys.path and
        # every acceptance test fails on an ImportError that looks like the arm's
        # fault. Task authors should not have to remember this.
        init = target / "__init__.py"
        if not init.exists():
            init.write_text("", encoding="utf-8")
        try:
            proc = _run(accept_command, repo)
            result.accept_ran = True
            result.accept_ok = proc.returncode == 0
            output = proc.stdout + proc.stderr
            total, passed, failures = _count_unittest(output)
            result.accept_total, result.accept_passed = total, passed
            result.failures = failures
            if not result.accept_ok:
                result.detail["accept"] = output[-3000:]
        finally:
            shutil.rmtree(target, ignore_errors=True)

    if since:
        result.files_changed, result.lines_added, result.lines_removed = diff_stats(repo, since)
    return result
