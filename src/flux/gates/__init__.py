"""Deterministic gates: the checks flux runs itself (ADR 0005).

The gate suite is the merge authority. Nothing here consults a model — a gate is a
subprocess, an exit status, and a short honest summary of what came back.
"""

from __future__ import annotations

from flux.gates.command import CommandGate, Summarizer, default_summary
from flux.gates.coverage import CoverageGate
from flux.gates.spec import GATE_KINDS, GateKind, GateSpec, bash_permissions, build_gates
from flux.gates.summaries import coverage_percent, pyright_summary, pytest_summary, ruff_summary
from flux.proc import (
    DEFAULT_TIMEOUT_S,
    ENVIRONMENT_TRAPS,
    MAX_DETAIL_CHARS,
    CommandRun,
    clean_env,
    run_command,
    tail,
)

__all__ = [
    "DEFAULT_TIMEOUT_S",
    "ENVIRONMENT_TRAPS",
    "GATE_KINDS",
    "MAX_DETAIL_CHARS",
    "CommandGate",
    "CommandRun",
    "CoverageGate",
    "GateKind",
    "GateSpec",
    "Summarizer",
    "bash_permissions",
    "build_gates",
    "clean_env",
    "coverage_percent",
    "default_summary",
    "pyright_summary",
    "pytest_summary",
    "ruff_summary",
    "run_command",
    "tail",
]
