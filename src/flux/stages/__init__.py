"""Pipeline stages (design.md stage I/O table).

Four of the five are built: ``tests``, ``implement``, ``review`` and ``fix``. Their
order in :func:`build_pipeline` is the mechanism rather than a preference — one stage
writes the specification and the two that write code are structurally prevented from
touching it (ADR 0005), and the reviewer that judges them can edit nothing at all. The
last stage, ``pr``, lands against the same :class:`~flux.runner.stage.Stage` protocol,
and the runner does not change to accept it.
"""

from __future__ import annotations

from flux.config import FluxConfig
from flux.runner.transition import Pipeline
from flux.stages.fix import FixStage
from flux.stages.implement import NOTES_SPEC, STAGE_NAME, ImplementStage
from flux.stages.review import ARTIFACT_SPEC as REVIEW_SPEC
from flux.stages.review import ReviewStage
from flux.stages.tests import ARTIFACT_SPEC as TESTS_SPEC
from flux.stages.tests import TestsStage

__all__ = [
    "NOTES_SPEC",
    "REVIEW_SPEC",
    "STAGE_NAME",
    "TESTS_SPEC",
    "FixStage",
    "ImplementStage",
    "ReviewStage",
    "TestsStage",
    "build_pipeline",
]


def build_pipeline(settings: FluxConfig) -> Pipeline:
    """The pipeline flux runs today: tests, implement, then the review↔fix loop.

    Kept as a function rather than a constant so that adding a stage is a change here
    and nowhere else — the runner is handed a ``Pipeline`` and asks no questions. The
    loop between the last two is not expressed here either: ``Pipeline`` is told which
    stage names form it, and the transition function does the turning (design.md §1).
    """
    return Pipeline(
        stages=(
            TestsStage(settings=settings),
            ImplementStage(settings=settings),
            ReviewStage(settings=settings),
            FixStage(settings=settings),
        )
    )
