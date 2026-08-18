"""The transition function: which stage runs next (design.md §1).

Pure, by construction. It takes the set of completed stages and the run state — both
read from disk by the caller — and returns a decision. No IO, no hidden memory, no
model. Every bound that keeps the pipeline terminating is visible in this one file.
"""

from __future__ import annotations

from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from typing import Literal

from flux.errors import ConfigError
from flux.runner.checkpoint import RunState
from flux.runner.context import RunnerConfig
from flux.runner.stage import Stage

REVIEW_STAGE = "review"
FIX_STAGE = "fix"

DecisionKind = Literal["run", "finished", "park"]


@dataclass(frozen=True, slots=True)
class Decision:
    """What the runner should do next."""

    kind: DecisionKind
    stage: Stage | None = None
    note: str = ""
    reason: str = "unspecified"

    @classmethod
    def run(cls, stage: Stage) -> Decision:
        return cls(kind="run", stage=stage)

    @classmethod
    def finished(cls) -> Decision:
        return cls(kind="finished")

    @classmethod
    def park(cls, note: str, *, reason: str) -> Decision:
        return cls(kind="park", note=note, reason=reason)


@dataclass(frozen=True, slots=True)
class Pipeline:
    """An ordered list of stages, plus which two of them form the review loop.

    The loop is named rather than hard-coded so the transition function can be
    exercised with fake stages, and so a target repo can drop the review loop
    entirely by simply not including those stages.
    """

    stages: tuple[Stage, ...]
    review_stage: str = REVIEW_STAGE
    fix_stage: str = FIX_STAGE

    def __post_init__(self) -> None:
        if not self.stages:
            raise ConfigError("Pipeline needs at least one stage")
        names = [s.name for s in self.stages]
        if any(not name for name in names):
            raise ConfigError("every Pipeline stage needs a non-empty name")
        duplicates = sorted({n for n in names if names.count(n) > 1})
        if duplicates:
            raise ConfigError(f"Pipeline stage names must be unique; repeated: {duplicates}")
        if self.review_stage in names and self.fix_stage not in names:
            raise ConfigError(
                f"Pipeline has a {self.review_stage!r} stage but no {self.fix_stage!r} stage "
                "to resolve its findings"
            )

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(s.name for s in self.stages)

    def by_name(self, name: str) -> Stage:
        for stage in self.stages:
            if stage.name == name:
                return stage
        raise ConfigError(f"Pipeline has no stage named {name!r}")


def next_stage(
    pipeline: Pipeline,
    *,
    completed: AbstractSet[str],
    state: RunState,
    config: RunnerConfig,
) -> Decision:
    """Decide the next move from persisted state alone.

    The linear walk covers the ordinary path. The one non-linear rule is the review
    loop: once ``review`` has completed with findings still open, the fix stage runs
    instead of the pipeline moving on, and the runner then clears the review
    checkpoint so the reviewer re-verifies. That can only happen
    ``config.max_review_iters`` times before the ticket parks.
    """
    if state.parked is not None:
        return Decision.park(state.parked.note, reason=state.parked.reason)

    for stage in pipeline.stages:
        # The fix stage is never entered by the linear walk — only by the loop rule below.
        if stage.name == pipeline.fix_stage:
            continue
        if stage.name not in completed:
            return Decision.run(stage)
        if stage.name == pipeline.review_stage and state.open_findings:
            if state.human_accepted:
                continue  # a human owns the remaining findings; carry on to the next stage
            if state.review_iterations >= config.max_review_iters:
                return Decision.park(
                    f"review loop exhausted after {state.review_iterations} review pass(es) "
                    "with findings still open",
                    reason="review-loop-exhausted",
                )
            return Decision.run(pipeline.by_name(pipeline.fix_stage))

    return Decision.finished()
