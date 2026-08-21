"""Validate the corpus before it is allowed to judge anybody.

A benchmark is only as trustworthy as its acceptance tests, and acceptance tests
have two failure modes that are invisible until you look for them:

* **Vacuous** -- they pass on the untouched seed, so every arm "delivers" without
  doing anything;
* **Unfair** -- no correct implementation of the brief can pass them, usually
  because the brief is ambiguous at a boundary, so every arm loses a point for
  the task author's writing rather than its own work.

The second one is not hypothetical: the first smoke run of this harness had both
arms fail the same acceptance test on an off-by-one the brief never pinned down.
So every task ships a reference implementation, and ``verify`` asserts both
properties per task:

    red  -- acceptance tests FAIL on the tree as the arm receives it
    green -- acceptance tests PASS once the reference is applied

Tasks are checked cumulatively, in order: task N's reference is applied on top of
tasks 1..N-1, which also proves the task sequence itself is coherent.
"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List

from .grade import grade
from .spec import Project, Task


@dataclass
class TaskVerdict:
    task: str
    red_ok: bool = False           # acceptance fails before the reference
    green_ok: bool = False         # acceptance passes after it
    gate_ok: bool = False          # repo gate green after the reference
    has_acceptance: bool = False
    has_reference: bool = False
    before_passed: int = 0
    before_total: int = 0
    after_passed: int = 0
    after_total: int = 0
    detail: str = ""

    @property
    def ok(self) -> bool:
        return (self.has_acceptance and self.has_reference
                and self.red_ok and self.green_ok and self.gate_ok)


def _apply(reference: Path, repo: Path) -> None:
    for item in reference.iterdir():
        target = repo / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)


def verify_project(project: Project) -> List[TaskVerdict]:
    verdicts: List[TaskVerdict] = []
    workdir = Path(tempfile.mkdtemp(prefix="fluxbench-verify-"))
    repo = workdir / "repo"
    shutil.copytree(project.seed_dir, repo)
    try:
        for task in project.tasks:
            v = TaskVerdict(task=task.id,
                            has_acceptance=task.has_acceptance,
                            has_reference=task.has_reference)
            if not v.has_acceptance:
                v.detail = "no acceptance tests"
                verdicts.append(v)
                continue

            before = grade(repo, task.accept_dir,
                           task.accept_command or project.accept_command, "")
            v.before_passed, v.before_total = before.accept_passed, before.accept_total
            v.red_ok = not before.accept_ok
            if not v.red_ok:
                v.detail = "acceptance tests already pass before the work is done"

            if not v.has_reference:
                v.detail = (v.detail + "; " if v.detail else "") + "no reference implementation"
                verdicts.append(v)
                continue

            _apply(task.reference_dir, repo)
            after = grade(repo, task.accept_dir,
                          task.accept_command or project.accept_command, project.gate)
            v.after_passed, v.after_total = after.accept_passed, after.accept_total
            v.green_ok = after.accept_ok
            v.gate_ok = after.gate_ok or not after.gate_ran
            if not v.green_ok:
                v.detail = ((v.detail + "; ") if v.detail else "") + \
                    "reference does not satisfy the acceptance tests -- the brief is ambiguous " \
                    "or the tests are wrong:\n" + after.detail.get("accept", "")[-1500:]
            elif not v.gate_ok:
                v.detail = ((v.detail + "; ") if v.detail else "") + \
                    "reference breaks the repo gate:\n" + after.detail.get("gate", "")[-1000:]
            verdicts.append(v)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    return verdicts
