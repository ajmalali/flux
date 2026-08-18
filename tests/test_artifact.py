"""Runner-side artifact validation — design.md §2 Rule 1."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from flux.errors import ConfigError
from flux.runner.artifact import (
    ArtifactSpec,
    missing_artifact_nudge,
    validate_artifact,
)
from flux.runner.context import TicketContext

TESTS_SPEC = ArtifactSpec(
    path="tests.json",
    required_keys=("test_files", "cases"),
    description="it maps each new test case to the acceptance criterion it covers.",
)
NOTES_SPEC = ArtifactSpec(
    path="impl-notes.md",
    kind="text",
    required_sections=("What changed", "Deviations"),
)


@pytest.fixture
def ticket(tmp_path: Path) -> TicketContext:
    return TicketContext(ticket_id="flux-1", root=tmp_path)


def write_artifact(ticket: TicketContext, spec: ArtifactSpec, content: str) -> Path:
    path = spec.resolve(ticket)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_no_spec_means_nothing_to_check(ticket: TicketContext) -> None:
    assert validate_artifact(ticket, None).ok


def test_missing_file_fails_with_a_readable_problem(ticket: TicketContext) -> None:
    check = validate_artifact(ticket, TESTS_SPEC)
    assert not check.ok
    assert "does not exist" in check.problem


def test_valid_json_artifact_passes_and_exposes_its_payload(ticket: TicketContext) -> None:
    write_artifact(ticket, TESTS_SPEC, json.dumps({"test_files": ["a.py"], "cases": []}))
    check = validate_artifact(ticket, TESTS_SPEC)
    assert check.ok
    assert check.payload is not None
    assert check.payload["test_files"] == ["a.py"]
    assert len(check.digest) == 64


def test_digest_tracks_content(ticket: TicketContext) -> None:
    write_artifact(ticket, TESTS_SPEC, json.dumps({"test_files": [], "cases": []}))
    first = validate_artifact(ticket, TESTS_SPEC).digest
    write_artifact(ticket, TESTS_SPEC, json.dumps({"test_files": ["b.py"], "cases": []}))
    assert validate_artifact(ticket, TESTS_SPEC).digest != first


def test_malformed_json_fails(ticket: TicketContext) -> None:
    write_artifact(ticket, TESTS_SPEC, "{ nope")
    check = validate_artifact(ticket, TESTS_SPEC)
    assert not check.ok
    assert "not valid JSON" in check.problem


def test_json_array_at_the_top_level_fails(ticket: TicketContext) -> None:
    write_artifact(ticket, TESTS_SPEC, "[1, 2]")
    assert "not a JSON object" in validate_artifact(ticket, TESTS_SPEC).problem


def test_missing_required_keys_are_named(ticket: TicketContext) -> None:
    write_artifact(ticket, TESTS_SPEC, json.dumps({"test_files": []}))
    check = validate_artifact(ticket, TESTS_SPEC)
    assert not check.ok
    assert "cases" in check.problem


def test_empty_artifact_fails_the_length_floor(ticket: TicketContext) -> None:
    write_artifact(ticket, TESTS_SPEC, "   \n  ")
    assert "shorter than" in validate_artifact(ticket, TESTS_SPEC).problem


def test_text_artifact_needs_its_headings(ticket: TicketContext) -> None:
    write_artifact(ticket, NOTES_SPEC, "## What changed\n\nadded a parser\n")
    check = validate_artifact(ticket, NOTES_SPEC)
    assert not check.ok
    assert "Deviations" in check.problem


def test_text_artifact_passes_with_all_headings(ticket: TicketContext) -> None:
    write_artifact(
        ticket,
        NOTES_SPEC,
        "# Notes\n\n### what changed\n\nadded a parser\n\n## Deviations\n\nnone\n",
    )
    check = validate_artifact(ticket, NOTES_SPEC)
    assert check.ok, check.problem


def test_heading_must_be_a_heading_not_a_mention(ticket: TicketContext) -> None:
    write_artifact(ticket, NOTES_SPEC, "I will describe What changed and Deviations later.\n")
    assert not validate_artifact(ticket, NOTES_SPEC).ok


def test_non_utf8_content_fails(ticket: TicketContext) -> None:
    path = TESTS_SPEC.resolve(ticket)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\xff\xfe\x00garbage")
    assert "not valid UTF-8" in validate_artifact(ticket, TESTS_SPEC).problem


@pytest.mark.parametrize("bad", ["", "/abs/tests.json", "../escape.json"])
def test_spec_path_must_stay_inside_the_context_dir(bad: str) -> None:
    with pytest.raises(ConfigError, match="relative path"):
        ArtifactSpec(path=bad)


def test_spec_rejects_mismatched_checks() -> None:
    with pytest.raises(ConfigError, match="required_keys"):
        ArtifactSpec(path="notes.md", kind="text", required_keys=("a",))
    with pytest.raises(ConfigError, match="required_sections"):
        ArtifactSpec(path="a.json", required_sections=("Summary",))


def test_nudge_names_the_file_the_problem_and_the_shape(ticket: TicketContext) -> None:
    check = validate_artifact(ticket, TESTS_SPEC)
    nudge = missing_artifact_nudge(check, context_dir=ticket.context_dir)
    assert "tests.json" in nudge
    assert "does not exist" in nudge
    assert "`test_files`" in nudge and "`cases`" in nudge
    assert TESTS_SPEC.description in nudge


def test_nudge_for_a_text_artifact_lists_headings(ticket: TicketContext) -> None:
    write_artifact(ticket, NOTES_SPEC, "## What changed\n\nx\n")
    nudge = missing_artifact_nudge(
        validate_artifact(ticket, NOTES_SPEC), context_dir=ticket.context_dir
    )
    assert "## Deviations" in nudge


def test_nudge_is_empty_when_no_artifact_was_required(ticket: TicketContext) -> None:
    check = validate_artifact(ticket, None)
    assert missing_artifact_nudge(check, context_dir=ticket.context_dir) == ""
