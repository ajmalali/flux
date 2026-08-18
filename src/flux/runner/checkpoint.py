"""Stage checkpoints and per-ticket run state, under ``.flux/state/<ticket>/`` (design.md §1).

This is the whole of the runner's memory. Nothing is held in the process: kill the
runner anywhere and re-invoking it reconstructs the identical position from these
files. Two kinds of file live here:

* ``<stage>.done.json`` — one per stage that finished successfully. Its *existence*
  is what makes a stage skip on rerun.
* ``run.json`` — the state the transition function needs that is not per-stage: the
  review-loop counter, whether findings are open, and the park record.

Writes go through :func:`~flux.fsio.write_atomic`, so a checkpoint is either absent
or complete — never half-written.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any

from flux.fsio import read_json_mapping, write_json_atomic
from flux.jsonio import as_json_mapping

SCHEMA_VERSION = 1
CHECKPOINT_SUFFIX = ".done.json"
RUN_STATE_FILENAME = "run.json"

_NO_DETAIL: Mapping[str, Any] = MappingProxyType({})


@dataclass(frozen=True, slots=True)
class Checkpoint:
    """The record that one stage finished. Written after ``commit()`` returns."""

    stage: str
    ok: bool = True
    """Only ``ok`` checkpoints make a stage skip. A stage that ran but did not stand
    (gate failure, park) leaves a record for triage and reruns once unparked."""

    ts: str = ""
    attempts: int = 1
    """Executor calls this stage consumed, including the artifact retry."""

    note: str = ""
    artifact_path: str = ""
    artifact_digest: str = ""
    """SHA-256 of the artifact as validated, so a later stage can detect a swap."""

    detail: Mapping[str, Any] = _NO_DETAIL
    schema_version: int = SCHEMA_VERSION

    def to_json(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "stage": self.stage,
            "ok": self.ok,
            "ts": self.ts or _now_iso(),
            "attempts": self.attempts,
            "note": self.note,
            "artifact_path": self.artifact_path,
            "artifact_digest": self.artifact_digest,
            "detail": dict(self.detail),
        }

    @classmethod
    def from_json(cls, payload: Mapping[str, Any]) -> Checkpoint:
        detail = as_json_mapping(payload.get("detail")) or {}
        return cls(
            stage=str(payload.get("stage", "")),
            ok=bool(payload.get("ok", True)),
            ts=str(payload.get("ts", "")),
            attempts=_int(payload.get("attempts"), default=1),
            note=str(payload.get("note", "")),
            artifact_path=str(payload.get("artifact_path", "")),
            artifact_digest=str(payload.get("artifact_digest", "")),
            detail=MappingProxyType(dict(detail)),
            schema_version=_int(payload.get("schema_version"), default=SCHEMA_VERSION),
        )


@dataclass(frozen=True, slots=True)
class ParkRecord:
    """Why a ticket stopped and where. The human triage surface until bd is wired (M4)."""

    stage: str
    reason: str
    note: str
    ts: str = ""
    """When the ticket parked. Stamped at construction, so a record and its persisted
    form are the same value — the runner compares them to tell a fresh park from a
    park it is merely re-reporting."""

    def __post_init__(self) -> None:
        if not self.ts:
            object.__setattr__(self, "ts", _now_iso())

    def to_json(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "reason": self.reason,
            "note": self.note,
            "ts": self.ts,
        }

    @classmethod
    def from_json(cls, payload: Mapping[str, Any]) -> ParkRecord:
        return cls(
            stage=str(payload.get("stage", "")),
            reason=str(payload.get("reason", "unspecified")),
            note=str(payload.get("note", "")),
            ts=str(payload.get("ts", "")),
        )


@dataclass(frozen=True, slots=True)
class RunState:
    """Per-ticket state that is not per-stage. Read by the transition function."""

    ticket: str = ""
    review_iterations: int = 0
    """Completed review passes. The review↔fix loop is bounded by this."""

    open_findings: bool = False
    """Set from the review stage's outcome, which derives it from ``review.json``."""

    human_accepted: bool = False
    """A human signed off on the remaining findings; the loop stops fighting them."""

    stage_runs: int = 0
    """Stage invocations so far, across resumes. Backstop against a non-writing stage."""

    parked: ParkRecord | None = None
    updated: str = ""
    schema_version: int = SCHEMA_VERSION

    def to_json(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "ticket": self.ticket,
            "review_iterations": self.review_iterations,
            "open_findings": self.open_findings,
            "human_accepted": self.human_accepted,
            "stage_runs": self.stage_runs,
            "parked": self.parked.to_json() if self.parked else None,
            "updated": self.updated or _now_iso(),
        }

    @classmethod
    def from_json(cls, payload: Mapping[str, Any]) -> RunState:
        parked = as_json_mapping(payload.get("parked"))
        return cls(
            ticket=str(payload.get("ticket", "")),
            review_iterations=_int(payload.get("review_iterations")),
            open_findings=bool(payload.get("open_findings", False)),
            human_accepted=bool(payload.get("human_accepted", False)),
            stage_runs=_int(payload.get("stage_runs")),
            parked=ParkRecord.from_json(parked) if parked else None,
            updated=str(payload.get("updated", "")),
            schema_version=_int(payload.get("schema_version"), default=SCHEMA_VERSION),
        )


@dataclass(frozen=True, slots=True)
class CheckpointStore:
    """File-backed checkpoint and run-state access for one ticket."""

    directory: Path

    def path_for(self, stage: str) -> Path:
        return self.directory / f"{stage}{CHECKPOINT_SUFFIX}"

    def read(self, stage: str) -> Checkpoint | None:
        """The stage's checkpoint, or ``None`` if absent — or unreadable.

        Corruption reads as absence: the stage reruns, which is always safe, whereas
        trusting a half-understood checkpoint is not.
        """
        payload = read_json_mapping(self.path_for(stage))
        return Checkpoint.from_json(payload) if payload else None

    def write(self, checkpoint: Checkpoint) -> Checkpoint:
        """Persist ``checkpoint`` atomically, stamping ``ts`` if unset."""
        stamped = checkpoint if checkpoint.ts else replace(checkpoint, ts=_now_iso())
        write_json_atomic(self.path_for(stamped.stage), stamped.to_json())
        return stamped

    def clear(self, stage: str) -> bool:
        """Remove a stage's checkpoint so it runs again. Returns whether one existed."""
        path = self.path_for(stage)
        existed = path.exists()
        path.unlink(missing_ok=True)
        return existed

    def iter_checkpoints(self) -> Iterator[Checkpoint]:
        """Every readable checkpoint, in stage-name order."""
        if not self.directory.is_dir():
            return
        for path in sorted(self.directory.glob(f"*{CHECKPOINT_SUFFIX}")):
            payload = read_json_mapping(path)
            if payload:
                yield Checkpoint.from_json(payload)

    def completed_stages(self) -> frozenset[str]:
        """Stages that finished *and* stood — what ``done()`` means to the transition fn."""
        return frozenset(cp.stage for cp in self.iter_checkpoints() if cp.ok and cp.stage)

    @property
    def state_path(self) -> Path:
        return self.directory / RUN_STATE_FILENAME

    def load_state(self, ticket: str = "") -> RunState:
        """Read ``run.json``; a ticket with no history starts from a clean state."""
        payload = read_json_mapping(self.state_path)
        if not payload:
            return RunState(ticket=ticket)
        state = RunState.from_json(payload)
        return state if state.ticket or not ticket else replace(state, ticket=ticket)

    def save_state(self, state: RunState) -> RunState:
        stamped = replace(state, updated=_now_iso())
        write_json_atomic(self.state_path, stamped.to_json())
        return stamped


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _int(value: object, *, default: int = 0) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else default
