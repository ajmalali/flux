"""The runner spine: checkpoints, transition function, and the ``run_ticket`` loop.

Nothing here imports the SDK (ADR 0007) and nothing here needs a model to be tested:
the loop drives any :class:`~flux.executor.protocol.Executor`, including
:class:`~flux.executor.stub.StubExecutor`.
"""

from flux.runner.artifact import (
    FAILED_SESSION_NUDGE,
    ArtifactCheck,
    ArtifactKind,
    ArtifactSpec,
    missing_artifact_nudge,
    validate_artifact,
)
from flux.runner.checkpoint import (
    CHECKPOINT_SUFFIX,
    RUN_STATE_FILENAME,
    Checkpoint,
    CheckpointStore,
    ParkRecord,
    RunState,
)
from flux.runner.context import DEFAULT_RUNNER_CONFIG, RunnerConfig, TicketContext
from flux.runner.loop import RunResult, RunStatus, run_ticket
from flux.runner.stage import Gate, Outcome, Stage
from flux.runner.transition import FIX_STAGE, REVIEW_STAGE, Decision, Pipeline, next_stage

__all__ = [
    "CHECKPOINT_SUFFIX",
    "DEFAULT_RUNNER_CONFIG",
    "FAILED_SESSION_NUDGE",
    "FIX_STAGE",
    "REVIEW_STAGE",
    "RUN_STATE_FILENAME",
    "ArtifactCheck",
    "ArtifactKind",
    "ArtifactSpec",
    "Checkpoint",
    "CheckpointStore",
    "Decision",
    "Gate",
    "Outcome",
    "ParkRecord",
    "Pipeline",
    "RunResult",
    "RunState",
    "RunStatus",
    "RunnerConfig",
    "Stage",
    "TicketContext",
    "missing_artifact_nudge",
    "next_stage",
    "run_ticket",
    "validate_artifact",
]
