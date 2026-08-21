"""Arm and project specs -- the two things a benchmark run is made of.

An **arm** is a Claude Code setup. It may differ from another arm in exactly
three ways: files seeded into the repo, plugin directories loaded, and the
sequence of prompts each task is driven with. Everything else -- model, effort,
permission mode, tool allow-list, starting tree, grading -- is fixed by the
runner so that no arm can win on a handicap.

A **project** is a seed repo plus an ordered list of tasks. The order matters:
tasks build on each other, so an arm's ability to carry knowledge from task N to
task N+1 across a fresh session is part of what is being measured. A benchmark
made of independent one-shot tasks would measure nothing about session
machinery, which is most of what flux is.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .toml_compat import load_toml

BENCH_ROOT = Path(__file__).resolve().parents[1]
ARMS_DIR = BENCH_ROOT / "arms"
PROJECTS_DIR = BENCH_ROOT / "projects"
REPO_ROOT = BENCH_ROOT.parent


@dataclass
class Step:
    """One unit of an arm's procedure: a model session, or a shell command."""

    label: str
    kind: str = "session"           # "session" | "shell"
    prompt: str = ""
    command: str = ""
    max_usd: Optional[float] = None
    optional: bool = False          # a failure here does not abort the task

    @classmethod
    def from_dict(cls, payload: Dict[str, Any], index: int) -> "Step":
        kind = str(payload.get("kind", "session"))
        label = str(payload.get("label") or payload.get("kind") or "step%d" % index)
        step = cls(
            label=label,
            kind=kind,
            prompt=str(payload.get("prompt", "")),
            command=str(payload.get("command", "")),
            max_usd=payload.get("max_usd"),
            optional=bool(payload.get("optional", False)),
        )
        if kind == "session" and not step.prompt:
            raise ValueError("session step %r has no prompt" % label)
        if kind == "shell" and not step.command:
            raise ValueError("shell step %r has no command" % label)
        if kind not in ("session", "shell"):
            raise ValueError("step %r has unknown kind %r" % (label, kind))
        return step


@dataclass
class Arm:
    name: str
    title: str = ""
    notes: str = ""
    plugin_dirs: List[str] = field(default_factory=list)
    seed: str = ""                                  # dir under arms/<name>/ copied into the repo
    setting_sources: str = "project"
    bootstrap: List[Step] = field(default_factory=list)
    steps: List[Step] = field(default_factory=list)
    spec_path: Optional[Path] = None

    @property
    def seed_dir(self) -> Optional[Path]:
        if not self.seed or self.spec_path is None:
            return None
        return (self.spec_path.parent / self.seed).resolve()

    def resolved_plugin_dirs(self) -> List[str]:
        out = []
        for raw in self.plugin_dirs:
            out.append(str(Path(raw.replace("${FLUX_REPO}", str(REPO_ROOT))).expanduser().resolve()))
        return out

    @classmethod
    def load(cls, name: str) -> "Arm":
        path = ARMS_DIR / (name + ".toml")
        if not path.exists():
            raise FileNotFoundError("no arm spec at %s" % path)
        data = load_toml(path)
        arm = cls(
            name=str(data.get("name", name)),
            title=str(data.get("title", name)),
            notes=str(data.get("notes", "")),
            plugin_dirs=list(data.get("plugin_dirs", []) or []),
            seed=str(data.get("seed", "")),
            setting_sources=str(data.get("setting_sources", "project")),
            spec_path=path,
        )
        arm.bootstrap = [Step.from_dict(s, i) for i, s in enumerate(data.get("bootstrap", []) or [])]
        arm.steps = [Step.from_dict(s, i) for i, s in enumerate(data.get("step", []) or [])]
        if not arm.steps:
            raise ValueError("arm %r defines no [[step]] -- it would do nothing" % arm.name)
        return arm


@dataclass
class Task:
    id: str
    title: str
    brief: str
    accept_dir: Optional[Path] = None
    reference_dir: Optional[Path] = None
    accept_command: str = ""

    @property
    def has_acceptance(self) -> bool:
        return self.accept_dir is not None and self.accept_dir.is_dir()

    @property
    def has_reference(self) -> bool:
        return self.reference_dir is not None and self.reference_dir.is_dir()


@dataclass
class Project:
    name: str
    title: str = ""
    root: Optional[Path] = None
    seed: str = "seed"
    gate: str = ""
    accept_command: str = "python3 -m unittest discover -s _accept -t . -v"
    brief_filename: str = "TASK.md"
    tasks: List[Task] = field(default_factory=list)

    @property
    def seed_dir(self) -> Path:
        assert self.root is not None
        return self.root / self.seed

    @classmethod
    def load(cls, name: str) -> "Project":
        root = PROJECTS_DIR / name
        path = root / "project.toml"
        if not path.exists():
            raise FileNotFoundError("no project spec at %s" % path)
        data = load_toml(path)
        project = cls(
            name=str(data.get("name", name)),
            title=str(data.get("title", name)),
            root=root,
            seed=str(data.get("seed", "seed")),
            gate=str(data.get("gate", "")),
            accept_command=str(data.get("accept_command", cls.accept_command)),
            brief_filename=str(data.get("brief_filename", cls.brief_filename)),
        )
        for entry in data.get("task", []) or []:
            tid = str(entry["id"])
            brief_path = root / "tasks" / tid / "BRIEF.md"
            if not brief_path.exists():
                raise FileNotFoundError("task %s has no BRIEF.md at %s" % (tid, brief_path))
            accept = root / "tasks" / tid / "accept"
            reference = root / "tasks" / tid / "reference"
            project.tasks.append(
                Task(
                    id=tid,
                    title=str(entry.get("title", tid)),
                    brief=brief_path.read_text(encoding="utf-8"),
                    accept_dir=accept if accept.is_dir() else None,
                    reference_dir=reference if reference.is_dir() else None,
                    accept_command=str(entry.get("accept_command", "")),
                )
            )
        if not project.tasks:
            raise ValueError("project %r defines no [[task]]" % project.name)
        return project


FRAMEWORKS_DIR = Path(os.path.expanduser(
    os.environ.get("FLUXBENCH_FRAMEWORKS", "~/.flux-bench/frameworks")))


def render(template: str, task: Optional[Task], project: Project, repo: Path) -> str:
    """Fill a prompt or command template.

    Every arm gets the same substitutions, so a difference between arms is
    always a difference in procedure, never in what the arm was told about the
    task. ``${FLUX_REPO}`` and ``${FRAMEWORKS}`` are available to bootstrap
    commands so that no arm has to hardcode a machine-specific path -- and so
    that third-party framework payloads can live outside this repo entirely.
    """
    out = (
        template.replace("{brief_path}", project.brief_filename)
        .replace("{gate}", project.gate)
        .replace("{repo}", str(repo))
        .replace("${FLUX_REPO}", str(REPO_ROOT))
        .replace("${FRAMEWORKS}", str(FRAMEWORKS_DIR))
    )
    if task is not None:
        out = (out.replace("{brief}", task.brief)
                  .replace("{task_id}", task.id)
                  .replace("{task_title}", task.title))
    return out


def available_arms() -> List[str]:
    return sorted(p.stem for p in ARMS_DIR.glob("*.toml"))


def available_projects() -> List[str]:
    return sorted(p.name for p in PROJECTS_DIR.iterdir() if (p / "project.toml").exists())
