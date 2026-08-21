"""Drive every arm through every task and write the evidence down.

The run loop is deliberately boring; the interesting decisions are the ones
that keep the comparison honest:

* **Every arm starts from a byte-identical tree.** The project's seed directory
  is copied fresh per arm and committed, so no arm inherits another's work.
* **The brief is committed before the arm starts.** The diff that gets attributed
  to an arm is therefore exactly what it changed, with the task statement itself
  excluded.
* **A fresh session per step.** Nothing is resumed with ``--continue``. Carrying
  knowledge from one session to the next is the arm's job, done through whatever
  mechanism the arm believes in -- that is the thing under test, and handing every
  arm a warm conversation would erase it.
* **Records are appended as they happen.** A run that dies at task 4 still leaves
  three tasks of usable evidence.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import metrics as M
from .driver import run_session
from .grade import grade
from .spec import FRAMEWORKS_DIR, REPO_ROOT, Arm, Project, Task, render

DEFAULT_RUNS_DIR = Path(os.path.expanduser("~/.flux-bench/runs"))


@dataclass
class RunConfig:
    project: str
    arms: List[str]
    model: str = "sonnet"
    effort: Optional[str] = None
    max_usd: float = 40.0
    max_usd_per_session: float = 4.0
    timeout_s: int = 1800
    tasks: Optional[List[str]] = None
    runs_dir: Path = DEFAULT_RUNS_DIR
    run_id: str = ""
    dry_run: bool = False

    def to_json(self) -> Dict[str, Any]:
        payload = dict(self.__dict__)
        payload["runs_dir"] = str(self.runs_dir)
        return payload


@dataclass
class TaskRecord:
    arm: str
    task: str
    title: str = ""
    delivered: bool = False
    grade: Dict[str, Any] = field(default_factory=dict)
    sessions: List[Dict[str, Any]] = field(default_factory=list)
    wall_ms: int = 0
    cost_usd: float = 0.0
    aborted: str = ""

    def to_json(self) -> Dict[str, Any]:
        return {"type": "task", **self.__dict__}


def _git(args: List[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git"] + args, cwd=str(cwd), capture_output=True, text=True)


def _head(repo: Path) -> str:
    return _git(["rev-parse", "HEAD"], repo).stdout.strip()


def _commit_all(repo: Path, message: str) -> None:
    _git(["add", "-A"], repo)
    _git(["-c", "user.email=bench@flux.local", "-c", "user.name=fluxbench",
          "commit", "--allow-empty", "-q", "-m", message], repo)


def materialize(project: Project, arm: Arm, dest: Path) -> Path:
    """Fresh clone-equivalent for one arm: project seed, then the arm's own files."""
    repo = dest / "repo"
    if repo.exists():
        shutil.rmtree(repo)
    shutil.copytree(project.seed_dir, repo)
    _git(["init", "-q", "-b", "main"], repo)
    _commit_all(repo, "seed: %s" % project.name)

    seed_dir = arm.seed_dir
    if seed_dir and seed_dir.is_dir():
        for item in seed_dir.iterdir():
            target = repo / item.name
            if item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)
            else:
                shutil.copy2(item, target)
        _commit_all(repo, "arm seed: %s" % arm.name)
    return repo


class Runner:
    def __init__(self, config: RunConfig, project: Project, arms: List[Arm]):
        self.config = config
        self.project = project
        self.arms = arms
        self.run_id = config.run_id or time.strftime("%Y%m%d-%H%M%S")
        self.out = Path(config.runs_dir) / self.run_id
        self.records_path = self.out / "records.jsonl"
        self.spent = 0.0

    # -- plumbing -----------------------------------------------------------

    def _append(self, payload: Dict[str, Any]) -> None:
        self.out.mkdir(parents=True, exist_ok=True)
        with self.records_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload) + "\n")

    def _budget_left(self) -> float:
        return max(0.0, self.config.max_usd - self.spent)

    def _log(self, message: str) -> None:
        print(message, flush=True)

    # -- steps --------------------------------------------------------------

    def _run_step(self, arm: Arm, step, repo: Path, task: Optional[Task], index: int) -> Optional[M.SessionMetrics]:
        label = "%s/%s/%s" % (arm.name, task.id if task else "bootstrap", step.label)
        if step.kind == "shell":
            command = render(step.command, task, self.project, repo)
            env = dict(os.environ)
            env["FLUX_REPO"] = str(REPO_ROOT)
            env["FRAMEWORKS"] = str(FRAMEWORKS_DIR)
            proc = subprocess.run(command, cwd=str(repo), shell=True, capture_output=True, text=True,
                                  timeout=self.config.timeout_s, env=env)
            ok = proc.returncode == 0
            self._log("  shell %-28s %s" % (label, "ok" if ok else "FAILED (%d)" % proc.returncode))
            if not ok:
                self._log("    ! %s" % (proc.stdout + proc.stderr).strip()[-500:])
            if not ok and not step.optional:
                self._append({"type": "shell", "arm": arm.name, "task": task.id if task else "",
                              "label": step.label, "ok": False,
                              "output": (proc.stdout + proc.stderr)[-2000:]})
            return None

        prompt = render(step.prompt, task, self.project, repo) if task else step.prompt
        cap = min(step.max_usd or self.config.max_usd_per_session, self._budget_left())
        if cap <= 0:
            raise BudgetExhausted("run budget of $%.2f exhausted" % self.config.max_usd)

        outcome = run_session(
            prompt,
            repo,
            model=self.config.model,
            effort=self.config.effort,
            plugin_dirs=arm.resolved_plugin_dirs(),
            setting_sources=arm.setting_sources,
            max_usd=cap,
            timeout_s=self.config.timeout_s,
        )
        sm = M.collect(
            outcome.payload,
            cwd=str(repo),
            arm=arm.name,
            task=task.id if task else "bootstrap",
            step=index,
            label=step.label,
            prompt_chars=len(prompt),
        )
        if not outcome.ok and not sm.error:
            sm.ok, sm.error = False, outcome.error
        if not sm.wall_ms:
            sm.wall_ms = outcome.wall_ms
        self.spent += sm.cost_usd
        self._log(
            "  session %-26s %s  $%.3f  %5.1fs  turns=%-3d ctx50=%s"
            % (label, "ok " if sm.ok else "ERR", sm.cost_usd, sm.wall_ms / 1000.0,
               sm.num_turns, sm.context_percentile(50))
        )
        if not sm.ok:
            self._log("    ! %s" % (sm.error or outcome.error))
        self._append({"type": "session", **sm.to_json()})
        return sm

    # -- arms ---------------------------------------------------------------

    def run_arm(self, arm: Arm) -> List[TaskRecord]:
        self._log("\n=== arm: %s (%s) ===" % (arm.name, arm.title))
        repo = materialize(self.project, arm, self.out / arm.name)
        records: List[TaskRecord] = []

        for i, step in enumerate(arm.bootstrap):
            self._run_step(arm, step, repo, None, i)
        if arm.bootstrap:
            _commit_all(repo, "bootstrap: %s" % arm.name)

        tasks = [t for t in self.project.tasks
                 if not self.config.tasks or t.id in self.config.tasks]
        for task in tasks:
            record = TaskRecord(arm=arm.name, task=task.id, title=task.title)
            (repo / self.project.brief_filename).write_text(task.brief, encoding="utf-8")
            _commit_all(repo, "brief: %s" % task.id)
            base = _head(repo)
            started = time.monotonic()
            self._log("-- task %s: %s" % (task.id, task.title))
            try:
                for i, step in enumerate(arm.steps):
                    sm = self._run_step(arm, step, repo, task, i)
                    if sm is not None:
                        record.sessions.append({"label": step.label, "ok": sm.ok,
                                                "cost_usd": sm.cost_usd, "wall_ms": sm.wall_ms})
                        record.cost_usd += sm.cost_usd
            except BudgetExhausted as exc:
                record.aborted = str(exc)
                self._log("  ! %s" % exc)

            record.wall_ms = int((time.monotonic() - started) * 1000)
            result = grade(
                repo,
                task.accept_dir,
                task.accept_command or self.project.accept_command,
                self.project.gate,
                since=base,
            )
            record.grade = result.to_json()
            record.delivered = result.delivered
            self._log("  grade: %s  accept %d/%d  gate %s  diff %d files +%d-%d"
                      % ("DELIVERED" if result.delivered else "not delivered",
                         result.accept_passed, result.accept_total,
                         "ok" if result.gate_ok else ("fail" if result.gate_ran else "n/a"),
                         result.files_changed, result.lines_added, result.lines_removed))
            _commit_all(repo, "after: %s (%s)" % (task.id, arm.name))
            self._append(record.to_json())
            records.append(record)
            if record.aborted:
                break
        return records

    def run(self) -> Dict[str, Any]:
        self.out.mkdir(parents=True, exist_ok=True)
        manifest = {
            "type": "manifest",
            "run_id": self.run_id,
            "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "config": self.config.to_json(),
            "project": {"name": self.project.name, "title": self.project.title,
                        "gate": self.project.gate,
                        "tasks": [{"id": t.id, "title": t.title,
                                   "acceptance": t.has_acceptance} for t in self.project.tasks]},
            "arms": [{"name": a.name, "title": a.title, "notes": a.notes,
                      "plugin_dirs": a.resolved_plugin_dirs(),
                      "steps": [s.label for s in a.steps],
                      "bootstrap": [s.label for s in a.bootstrap]} for a in self.arms],
        }
        (self.out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        self._append(manifest)

        for arm in self.arms:
            try:
                self.run_arm(arm)
            except BudgetExhausted as exc:
                self._log("! %s -- stopping before remaining arms" % exc)
                break
        self._log("\nspent $%.2f of $%.2f budget; records: %s"
                  % (self.spent, self.config.max_usd, self.records_path))
        return manifest


class BudgetExhausted(RuntimeError):
    pass
