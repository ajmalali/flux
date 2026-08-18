"""The checkpoint store: atomic writes, tolerant reads (design.md §1)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from flux.fsio import read_json_mapping, write_atomic, write_json_atomic
from flux.runner.checkpoint import (
    CHECKPOINT_SUFFIX,
    Checkpoint,
    CheckpointStore,
    ParkRecord,
    RunState,
)


@pytest.fixture
def store(tmp_path: Path) -> CheckpointStore:
    return CheckpointStore(tmp_path / "state" / "flux-1")


def test_checkpoint_round_trips(store: CheckpointStore) -> None:
    written = store.write(
        Checkpoint(
            stage="implement",
            attempts=2,
            note="landed",
            artifact_path="impl-notes.md",
            artifact_digest="abc123",
            detail={"files": 3},
        )
    )
    assert store.read("implement") == written


def test_checkpoint_stamps_a_timestamp(store: CheckpointStore) -> None:
    written = store.write(Checkpoint(stage="tests"))
    assert written.ts.endswith("Z")


def test_missing_checkpoint_reads_as_none(store: CheckpointStore) -> None:
    assert store.read("tests") is None


def test_corrupt_checkpoint_reads_as_absent(store: CheckpointStore) -> None:
    """A half-understood checkpoint must not wedge the ticket: rerunning is safe."""
    store.write(Checkpoint(stage="tests"))
    store.path_for("tests").write_text("{ this is not json", encoding="utf-8")
    assert store.read("tests") is None
    assert "tests" not in store.completed_stages()


def test_clear_removes_a_checkpoint(store: CheckpointStore) -> None:
    store.write(Checkpoint(stage="review"))
    assert store.clear("review") is True
    assert store.clear("review") is False
    assert store.read("review") is None


def test_completed_stages_excludes_stages_that_did_not_stand(store: CheckpointStore) -> None:
    """A stage that ran but failed its gates must run again, not be skipped."""
    store.write(Checkpoint(stage="tests", ok=True))
    store.write(Checkpoint(stage="implement", ok=False, note="typecheck failed"))
    assert store.completed_stages() == frozenset({"tests"})


def test_completed_stages_is_empty_before_the_directory_exists(store: CheckpointStore) -> None:
    assert store.completed_stages() == frozenset()
    assert list(store.iter_checkpoints()) == []


def test_run_state_round_trips(store: CheckpointStore) -> None:
    saved = store.save_state(
        RunState(
            ticket="flux-1",
            review_iterations=2,
            open_findings=True,
            stage_runs=5,
            parked=ParkRecord(stage="review", reason="review-loop-exhausted", note="3 passes"),
        )
    )
    loaded = store.load_state("flux-1")
    assert loaded == saved
    assert loaded.parked is not None
    assert loaded.parked.reason == "review-loop-exhausted"


def test_run_state_defaults_for_a_fresh_ticket(store: CheckpointStore) -> None:
    state = store.load_state("flux-9")
    assert state == RunState(ticket="flux-9")
    assert state.parked is None


def test_corrupt_run_state_falls_back_to_a_fresh_state(store: CheckpointStore) -> None:
    store.save_state(RunState(ticket="flux-1", review_iterations=2))
    store.state_path.write_text("not json at all", encoding="utf-8")
    assert store.load_state("flux-1") == RunState(ticket="flux-1")


def test_checkpoints_use_the_documented_filenames(store: CheckpointStore) -> None:
    store.write(Checkpoint(stage="pr"))
    assert store.path_for("pr").name == f"pr{CHECKPOINT_SUFFIX}"


# -- the atomicity the whole "resume is rerun" property rests on --


def test_write_atomic_leaves_no_temporary_files(tmp_path: Path) -> None:
    write_json_atomic(tmp_path / "deep" / "state.json", {"a": 1})
    assert read_json_mapping(tmp_path / "deep" / "state.json") == {"a": 1}
    assert [p.name for p in (tmp_path / "deep").iterdir()] == ["state.json"]


def test_failed_rename_leaves_neither_a_partial_file_nor_a_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the move fails, the reader must still see nothing rather than half a file."""
    target = tmp_path / "state.json"

    def boom(src: object, dst: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError, match="disk full"):
        write_atomic(target, "half a file")
    assert not target.exists()
    assert list(tmp_path.iterdir()) == []


def test_write_atomic_replaces_previous_content(tmp_path: Path) -> None:
    target = tmp_path / "state.json"
    write_atomic(target, "first")
    write_atomic(target, "second")
    assert target.read_text(encoding="utf-8") == "second"


def test_read_json_mapping_rejects_non_objects(tmp_path: Path) -> None:
    target = tmp_path / "list.json"
    target.write_text("[1, 2, 3]", encoding="utf-8")
    assert read_json_mapping(target) is None
    assert read_json_mapping(tmp_path / "absent.json") is None
