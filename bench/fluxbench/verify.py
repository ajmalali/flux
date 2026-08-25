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

import ast
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from .grade import grade
from .runner import apply_reference
from .spec import Project, Task

_SYMBOL_IMPORT = re.compile(r"^\s*from\s+meridian[\w.]*\s+import\s+(?P<names>[^\n#]+)", re.M)


def seed_symbols(project: Project) -> set:
    """Every top-level name the seed already exports.

    Acceptance tests are free to use these as scaffolding -- they exist before
    any arm touches the repo, so binding to them holds nobody to anything the
    brief failed to say."""
    names = set()
    for path in sorted(project.seed_dir.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - a broken seed fails elsewhere
            continue
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, ast.Assign):
                names.update(t.id for t in node.targets if isinstance(t, ast.Name))
    return names


def unbriefed_symbols(task: Task, seed: set) -> List[str]:
    """Names the acceptance tests import that are neither in the seed nor the brief.

    A test may only hold an arm to API that already exists or that the brief
    actually asks for. Binding to anything else measures whether the arm guessed
    the task author's imagination.

    This catches the coarse version of a failure red/green verification
    structurally cannot: the reference implementation is written by the same
    person as the tests, so it agrees with them by construction. m2 shipped
    binding to a *signature* the brief never stated -- `refund_cents(price, gap)`
    rather than `refund_cents(booking, at)` -- and cost the vanilla arm a task it
    had in fact delivered. A name check would not have caught that one; only the
    rule in bench/README.md ("state the signature in the brief") does. This guard
    stops the easier mistake of testing a helper nobody asked for.
    """
    if not task.has_acceptance:
        return []
    missing = []
    for path in sorted(task.accept_dir.rglob("*.py")):
        for match in _SYMBOL_IMPORT.finditer(path.read_text(encoding="utf-8")):
            for raw in match.group("names").split(","):
                name = raw.strip().split(" as ")[0].strip().strip("()")
                if name and name not in seed and name not in task.brief and name not in missing:
                    missing.append(name)
    return missing


@dataclass
class TaskVerdict:
    task: str
    red_ok: bool = False           # acceptance fails before the reference
    green_ok: bool = False         # acceptance passes after it
    gate_ok: bool = False          # repo gate green after the reference
    has_acceptance: bool = False
    has_reference: bool = False
    unbriefed: List[str] = field(default_factory=list)
    before_passed: int = 0
    before_total: int = 0
    after_passed: int = 0
    after_total: int = 0
    detail: str = ""

    @property
    def ok(self) -> bool:
        return (self.has_acceptance and self.has_reference and not self.unbriefed
                and self.red_ok and self.green_ok and self.gate_ok)


def verify_project(project: Project) -> List[TaskVerdict]:
    verdicts: List[TaskVerdict] = []
    seed = seed_symbols(project)
    workdir = Path(tempfile.mkdtemp(prefix="fluxbench-verify-"))
    repo = workdir / "repo"
    shutil.copytree(project.seed_dir, repo)
    try:
        for task in project.tasks:
            v = TaskVerdict(task=task.id,
                            has_acceptance=task.has_acceptance,
                            has_reference=task.has_reference,
                            unbriefed=unbriefed_symbols(task, seed))
            if v.unbriefed:
                v.detail = ("acceptance tests bind to names the brief never states: %s"
                            % ", ".join(v.unbriefed))
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

            apply_reference(task, repo)
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
