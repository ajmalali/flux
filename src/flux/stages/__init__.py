"""Pipeline stages (design.md stage I/O table).

Two of the five are built: ``tests`` and ``implement``. They are also the pair that
carries ADR 0005's hardening — one writes the specification, the other is structurally
prevented from touching it — so the order in :func:`build_pipeline` is the mechanism,
not a preference. The remaining three land against the same
:class:`~flux.runner.stage.Stage` protocol, and the runner does not change to accept
them.
"""

from __future__ import annotations

from flux.config import FluxConfig
from flux.runner.transition import Pipeline
from flux.stages.implement import NOTES_SPEC, STAGE_NAME, ImplementStage
from flux.stages.tests import ARTIFACT_SPEC as TESTS_SPEC
from flux.stages.tests import TestsStage

__all__ = [
    "NOTES_SPEC",
    "STAGE_NAME",
    "TESTS_SPEC",
    "ImplementStage",
    "TestsStage",
    "build_pipeline",
]


def build_pipeline(settings: FluxConfig) -> Pipeline:
    """The pipeline flux runs today: tests, then implement, both gated.

    Kept as a function rather than a constant so that adding a stage is a change here
    and nowhere else — the runner is handed a ``Pipeline`` and asks no questions.
    """
    return Pipeline(stages=(TestsStage(settings=settings), ImplementStage(settings=settings)))
