"""Scriptable stages, gates and an executor that stand in for the real pipeline.

The runner spine is specified to be provable without a model (plan.md M0), so these
fakes play the part a model would: :class:`FakeExecutor` writes the artifact a stage
asked for, fails a session, or dies mid-stage, exactly as scripted.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from flux.executor.types import (
    EffortLevel,
    ExecConfig,
    ExecResult,
    PromptPack,
    Usage,
    WindowPressure,
)
from flux.metrics.record import GateOutcome
from flux.runner.artifact import ArtifactSpec
from flux.runner.context import TicketContext
from flux.runner.stage import Gate, Outcome

STAGE_MARKER = "flux-fake-stage:"


class StageCrash(RuntimeError):
    """Stands in for the process being killed mid-stage."""


@dataclass
class FakeGate:
    """A gate whose verdict is decided by the test, not by a subprocess."""

    name: str = "fake-gate"
    passed: bool = True
    detail: str = ""
    runs: list[Path] = field(default_factory=list[Path])

    def run(self, worktree: Path) -> GateOutcome:
        self.runs.append(worktree)
        return GateOutcome(name=self.name, passed=self.passed, detail=self.detail)


@dataclass
class FakeStage:
    """One scripted pipeline step.

    The per-attempt tuples (``writes``, ``outcomes``) repeat their last entry once
    exhausted, so a one-element script serves any number of attempts.
    """

    name: str
    spec: ArtifactSpec | None = None
    model: str = "claude-sonnet-5"
    effort: EffortLevel = "high"
    max_tokens: int = 200_000
    gate_list: tuple[Gate, ...] = ()

    writes: tuple[str | None, ...] = ()
    """File content per attempt; ``None`` writes nothing. Empty means "always valid"."""

    outcomes: tuple[Outcome, ...] = ()
    """What ``commit()`` returns per commit. Empty means a plain successful outcome."""

    fail_attempts: frozenset[int] = frozenset()
    """Attempt indexes where the session itself returns ``ok=False``."""

    crash_attempts: frozenset[int] = frozenset()
    """Attempt indexes where the process dies before the stage can finish."""

    usage_tokens: int = 2
    window: WindowPressure | None = None
    """Usage-window pressure the session reports back (ADR 0010)."""

    hydrations: list[PromptPack] = field(default_factory=list[PromptPack])
    commits: list[tuple[ExecResult, tuple[GateOutcome, ...]]] = field(
        default_factory=list[tuple[ExecResult, tuple[GateOutcome, ...]]]
    )

    def hydrate(self, ticket: TicketContext) -> PromptPack:
        pack = PromptPack(
            system_prompt=f"{STAGE_MARKER}{self.name}",
            plan_summary="the plan, re-injected every stage",
            context_pack=f"ticket {ticket.ticket_id}",
            stage_tail=f"do the {self.name} work",
        )
        self.hydrations.append(pack)
        return pack

    def config(self, ticket: TicketContext) -> ExecConfig:
        return ExecConfig(
            model=self.model,
            effort=self.effort,
            permission_mode="acceptEdits",
            max_turns=8,
            max_tokens=self.max_tokens,
            cwd=ticket.worktree,
        )

    def required_artifact(self) -> ArtifactSpec | None:
        return self.spec

    def gates(self, ticket: TicketContext) -> Sequence[Gate]:
        return self.gate_list

    def commit(
        self,
        ticket: TicketContext,
        result: ExecResult,
        gate_results: Sequence[GateOutcome],
    ) -> Outcome:
        outcome = _at(self.outcomes, len(self.commits), Outcome())
        self.commits.append((result, tuple(gate_results)))
        return outcome

    # -- the part FakeExecutor drives, standing in for the session's side effects --

    def perform(self, ticket: TicketContext, attempt: int) -> None:
        if attempt in self.crash_attempts:
            raise StageCrash(f"{self.name} killed on attempt {attempt}")
        if self.spec is None:
            return
        content = _at(self.writes, attempt, default_content(self.spec))
        if content is None:
            return
        path = self.spec.resolve(ticket)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


@dataclass
class FakeExecutor:
    """Routes each call to the stage that hydrated the pack and performs its script."""

    ticket: TicketContext
    stages: Mapping[str, FakeStage]
    calls: list[tuple[str, PromptPack, ExecConfig]] = field(
        default_factory=list[tuple[str, PromptPack, ExecConfig]]
    )
    attempts: Counter[str] = field(default_factory=Counter[str])

    def run(self, pack: PromptPack, cfg: ExecConfig) -> ExecResult:
        name = stage_name_of(pack)
        stage = self.stages[name]
        attempt = self.attempts[name]
        self.attempts[name] += 1
        self.calls.append((name, pack, cfg))
        stage.perform(self.ticket, attempt)
        ok = attempt not in stage.fail_attempts
        return ExecResult(
            ok=ok,
            text=f"{name} attempt {attempt}",
            session_id=f"{name}-{attempt}",
            model=cfg.model,
            effort=cfg.effort,
            billing_mode=cfg.billing_mode,
            usage=Usage(input_tokens=stage.usage_tokens, output_tokens=1),
            num_turns=1,
            subtype="success" if ok else "error_during_execution",
            error=None if ok else "the model gave up",
            window=stage.window,
            pack_chars=pack.size_chars,
        )

    def calls_for(self, stage: str) -> list[tuple[str, PromptPack, ExecConfig]]:
        return [call for call in self.calls if call[0] == stage]


def stage_name_of(pack: PromptPack) -> str:
    return pack.system_prompt.removeprefix(STAGE_MARKER)


def default_content(spec: ArtifactSpec) -> str:
    """Artifact content that satisfies ``spec`` — what an obedient model would write."""
    if spec.kind == "json":
        payload = {key: f"{key}-value" for key in spec.required_keys} or {"done": True}
        return json.dumps(payload, indent=2)
    body = "\n\n".join(f"## {section}\n\nnotes" for section in spec.required_sections)
    return body or "notes"


def make_executor(ticket: TicketContext, *stages: FakeStage) -> FakeExecutor:
    return FakeExecutor(ticket=ticket, stages={stage.name: stage for stage in stages})


def _at[T](values: Sequence[T], index: int, default: T) -> T:
    """``values[index]`` with the last entry repeating, or ``default`` when empty."""
    if not values:
        return default
    return values[min(index, len(values) - 1)]
