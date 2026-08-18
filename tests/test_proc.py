"""``run_command`` never raises — every failure mode comes back as a value.

That is the property the gate layer is built on: if the helper could raise, "we could
not check" would reach the runner as a stack trace instead of a failed gate.
"""

from __future__ import annotations

import sys
from pathlib import Path

from flux.proc import run_command, tail

PY = sys.executable


def test_a_successful_command_reports_its_output(tmp_path: Path) -> None:
    run = run_command([PY, "-c", "print('hello')"], cwd=tmp_path)
    assert run.completed
    assert run.returncode == 0
    assert run.stdout.strip() == "hello"
    assert run.output == "hello"


def test_stderr_joins_stdout_in_output(tmp_path: Path) -> None:
    run = run_command(
        [PY, "-c", "import sys; print('out'); print('err', file=sys.stderr)"], cwd=tmp_path
    )
    assert run.output.splitlines() == ["out", "err"]


def test_a_nonzero_exit_is_a_value_not_an_exception(tmp_path: Path) -> None:
    run = run_command([PY, "-c", "raise SystemExit(3)"], cwd=tmp_path)
    assert run.completed
    assert run.returncode == 3


def test_a_missing_executable_reports_the_name(tmp_path: Path) -> None:
    run = run_command(["flux-definitely-not-a-real-binary"], cwd=tmp_path)
    assert not run.completed
    assert not run.launched
    assert "not on PATH" in run.fault


def test_a_missing_working_directory_is_reported(tmp_path: Path) -> None:
    run = run_command([PY, "-c", "pass"], cwd=tmp_path / "absent")
    assert not run.launched
    assert "does not exist" in run.fault


def test_an_empty_command_is_reported_rather_than_run(tmp_path: Path) -> None:
    run = run_command([], cwd=tmp_path)
    assert not run.launched
    assert "no command" in run.fault


def test_a_hang_times_out_and_keeps_partial_output(tmp_path: Path) -> None:
    run = run_command(
        [PY, "-u", "-c", "import time; print('started'); time.sleep(30)"],
        cwd=tmp_path,
        timeout_s=1,
    )
    assert run.timed_out
    assert not run.completed
    assert "did not finish within 1s" in run.fault
    assert "started" in run.stdout


def test_the_environment_is_passed_through(tmp_path: Path) -> None:
    run = run_command(
        [PY, "-c", "import os; print(os.environ.get('FLUX_TEST_VAR', 'unset'))"],
        cwd=tmp_path,
        env={"FLUX_TEST_VAR": "set", "PATH": ""},
    )
    assert run.stdout.strip() == "set"


def test_tail_keeps_the_end_because_failures_summarise_at_the_bottom() -> None:
    text = "\n".join(f"line {n}" for n in range(50))
    assert tail(text, lines=3) == "line 47\nline 48\nline 49"


def test_tail_clips_to_the_character_limit() -> None:
    clipped = tail("x" * 5_000, limit=100)
    assert len(clipped) == 100
    assert clipped.startswith("…")
