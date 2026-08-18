"""Pipeline stages (design.md stage I/O table).

M0 ships the implement stage alone: it is the one that proves the spine end to end.
The other four land at M1 against the same :class:`~flux.runner.stage.Stage` protocol,
and the runner does not change to accept them.
"""

from __future__ import annotations

from flux.config import FluxConfig
from flux.runner.transition import Pipeline
from flux.stages.implement import NOTES_SPEC, STAGE_NAME, ImplementStage

__all__ = ["NOTES_SPEC", "STAGE_NAME", "ImplementStage", "build_pipeline"]


def build_pipeline(settings: FluxConfig) -> Pipeline:
    """The pipeline flux runs today: implement, gated.

    Kept as a function rather than a constant so that adding a stage at M1 is a change
    here and nowhere else — the runner is handed a ``Pipeline`` and asks no questions.
    """
    return Pipeline(stages=(ImplementStage(settings=settings),))
