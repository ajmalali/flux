"""A scripted :class:`~gus.executor.protocol.Executor` for tests.

The runner spine (T3) is specified to be provable without an LLM, so the stub is
library code rather than a test fixture: tests, and later ``gus run --dry-run``,
drive the real state machine through it.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from gus.executor.types import ExecConfig, ExecResult, PromptPack, Usage

ResponseFn = Callable[[PromptPack, ExecConfig], ExecResult]
CallLog = list[tuple[PromptPack, ExecConfig]]


def _new_call_log() -> CallLog:
    return []


@dataclass
class StubExecutor:
    """Returns canned results and records every call.

    Args:
        responses: Results (or callables producing them) yielded in order. When
            exhausted, the last entry repeats — so a single-element script serves
            an arbitrary number of calls.
    """

    responses: Sequence[ExecResult | ResponseFn] = ()
    calls: CallLog = field(default_factory=_new_call_log)

    def run(self, pack: PromptPack, cfg: ExecConfig) -> ExecResult:
        index = min(len(self.calls), len(self.responses) - 1) if self.responses else -1
        self.calls.append((pack, cfg))
        if index < 0:
            return ok_result(cfg, pack)
        entry = self.responses[index]
        return entry(pack, cfg) if callable(entry) else entry

    @property
    def call_count(self) -> int:
        return len(self.calls)


def ok_result(cfg: ExecConfig, pack: PromptPack | None = None, text: str = "") -> ExecResult:
    """A minimal successful result consistent with ``cfg``."""
    return ExecResult(
        ok=True,
        text=text,
        session_id="stub-session",
        model=cfg.model,
        effort=cfg.effort,
        billing_mode=cfg.billing_mode,
        usage=Usage(input_tokens=1, output_tokens=1),
        num_turns=1,
        subtype="success",
        pack_chars=pack.size_chars if pack else 0,
    )
