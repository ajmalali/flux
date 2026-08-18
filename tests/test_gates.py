"""Gates as the runner sees them: an exit status, a duration, and a short verdict.

The load-bearing case is the one that is easy to get wrong — a gate that *could not
run*. Skipping it would let a missing typechecker read as a clean typecheck, which is
precisely the failure the gate suite exists to prevent (ADR 0005).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from flux.errors import ConfigError
from flux.gates import (
    CommandGate,
    CoverageGate,
    GateSpec,
    bash_permissions,
    build_gates,
    clean_env,
)
from flux.gates.command import _clip  # pyright: ignore[reportPrivateUsage]
from flux.proc import MAX_DETAIL_CHARS

PY = sys.executable


def script_gate(name: str, code: str, **kwargs: object) -> CommandGate:
    return CommandGate(name=name, argv=(PY, "-c", code), **kwargs)  # pyright: ignore[reportArgumentType]


def test_a_zero_exit_passes_with_no_detail(tmp_path: Path) -> None:
    outcome = script_gate("lint", "print('clean')").run(tmp_path)
    assert outcome.passed
    assert outcome.name == "lint"
    assert outcome.detail == ""


def test_a_nonzero_exit_fails_and_keeps_the_tail(tmp_path: Path) -> None:
    outcome = script_gate("lint", "print('a.py:1:1: E501 too long'); raise SystemExit(1)").run(
        tmp_path
    )
    assert not outcome.passed
    assert "E501" in outcome.detail


def test_a_silent_failure_still_says_why(tmp_path: Path) -> None:
    outcome = script_gate("lint", "raise SystemExit(7)").run(tmp_path)
    assert not outcome.passed
    assert outcome.detail == "exit status 7"


def test_a_gate_that_cannot_run_fails_rather_than_being_skipped(tmp_path: Path) -> None:
    """The whole point: an absent tool must never read as a clean check."""
    outcome = CommandGate(name="typecheck", argv=("flux-no-such-binary",)).run(tmp_path)
    assert not outcome.passed
    assert "did not run" in outcome.detail


def test_a_hanging_gate_fails_on_its_timeout(tmp_path: Path) -> None:
    outcome = script_gate("test", "import time; time.sleep(30)", timeout_s=1).run(tmp_path)
    assert not outcome.passed
    assert "did not finish within 1s" in outcome.detail


def test_the_gate_runs_in_the_worktree_it_is_given(tmp_path: Path) -> None:
    (tmp_path / "marker.txt").write_text("here", encoding="utf-8")
    outcome = script_gate(
        "test", "import pathlib,sys; sys.exit(0 if pathlib.Path('marker.txt').exists() else 1)"
    ).run(tmp_path)
    assert outcome.passed


def test_detail_is_clipped_so_metrics_lines_stay_readable() -> None:
    assert len(_clip("x" * 10_000)) == MAX_DETAIL_CHARS
    assert _clip("short") == "short"


def test_an_alternative_success_code_can_be_declared(tmp_path: Path) -> None:
    gate = script_gate("test", "raise SystemExit(5)", ok_returncodes=(0, 5))
    assert gate.run(tmp_path).passed


# -- coverage ---------------------------------------------------------------------


def coverage_gate(report: str, minimum: float, **kwargs: object) -> CoverageGate:
    return CoverageGate(
        name="coverage",
        argv=(PY, "-c", f"print({report!r})"),
        min_percent=minimum,
        **kwargs,  # pyright: ignore[reportArgumentType]
    )


TABLE = (
    "Name      Stmts   Miss  Cover\nsrc/a.py     10      2    80%\nTOTAL        10      2    80%"
)


def test_coverage_passes_at_or_above_the_floor(tmp_path: Path) -> None:
    outcome = coverage_gate(TABLE, 80.0).run(tmp_path)
    assert outcome.passed
    assert "80.0% total coverage" in outcome.detail


def test_coverage_fails_below_the_floor(tmp_path: Path) -> None:
    outcome = coverage_gate(TABLE, 90.0).run(tmp_path)
    assert not outcome.passed
    assert "minimum 90.0%" in outcome.detail


def test_an_unreadable_coverage_report_fails(tmp_path: Path) -> None:
    """'We could not measure it' must never be recorded as 'it was fine'."""
    outcome = coverage_gate("no table here", 50.0).run(tmp_path)
    assert not outcome.passed
    assert "no TOTAL line" in outcome.detail


def test_a_coverage_tool_that_errors_fails(tmp_path: Path) -> None:
    gate = CoverageGate(name="coverage", argv=(PY, "-c", "raise SystemExit(2)"))
    assert not gate.run(tmp_path).passed


def test_a_missing_coverage_tool_fails(tmp_path: Path) -> None:
    outcome = CoverageGate(name="coverage", argv=("flux-no-such-binary",)).run(tmp_path)
    assert not outcome.passed
    assert "did not run" in outcome.detail


# -- specs ------------------------------------------------------------------------


def test_a_spec_command_may_be_a_string_and_is_split_without_a_shell() -> None:
    spec = GateSpec.parse({"name": "lint", "command": "uv run ruff check '.'"})
    assert spec.command == ("uv", "run", "ruff", "check", ".")


def test_a_spec_command_may_be_a_list() -> None:
    spec = GateSpec.parse({"name": "lint", "command": ["ruff", "check", "."]})
    assert spec.command == ("ruff", "check", ".")


def test_a_shell_metacharacter_is_an_argument_not_a_second_command() -> None:
    """Gate commands come from flux.toml, so they must not be an injection surface."""
    spec = GateSpec.parse({"name": "lint", "command": "ruff check .; rm -rf /"})
    assert spec.command == ("ruff", "check", ".;", "rm", "-rf", "/")


@pytest.mark.parametrize(
    "payload",
    [
        {"command": "ruff"},
        {"name": "lint"},
        {"name": "lint", "command": ""},
        {"name": "lint", "command": "ruff", "kind": "telepathy"},
        {"name": "lint", "command": "ruff", "timeout_s": 0},
        {"name": "lint", "command": "ruff", "timeout_s": "soon"},
        {"name": "cov", "command": "coverage", "kind": "coverage", "min_percent": 120},
        {"name": "lint", "command": ["ruff", 3]},
    ],
)
def test_a_malformed_spec_is_rejected_with_an_explanation(payload: dict[str, object]) -> None:
    with pytest.raises(ConfigError):
        GateSpec.parse(payload)


def test_kind_selects_the_gate_implementation() -> None:
    built = build_gates(
        (
            GateSpec(name="lint", kind="ruff", command=("ruff",)),
            GateSpec(name="cov", kind="coverage", command=("coverage",), min_percent=70.0),
        )
    )
    assert [g.name for g in built] == ["lint", "cov"]
    assert isinstance(built[1], CoverageGate)
    assert built[1].min_percent == 70.0


def test_gate_permissions_name_the_exact_configured_commands() -> None:
    specs = (
        GateSpec(name="lint", command=("uv", "run", "ruff", "check", ".")),
        GateSpec(name="test", command=("pytest", "-q", "-rf")),
    )
    assert bash_permissions(specs) == (
        "Bash(uv run ruff check .:*)",
        "Bash(pytest -q -rf:*)",
    )


def test_gate_permissions_quote_arguments_that_need_it() -> None:
    spec = GateSpec(name="test", command=("just", "run tests"))
    assert bash_permissions((spec,)) == ("Bash(just 'run tests':*)",)


# -- environment isolation ---------------------------------------------------------


def test_a_gate_does_not_inherit_fluxs_own_virtualenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """flux runs from a virtualenv; a gate that inherits it measures flux, not the repo."""
    fake = tmp_path / "flux-venv"
    (fake / "bin").mkdir(parents=True)
    monkeypatch.setenv("VIRTUAL_ENV", str(fake))
    monkeypatch.setenv("PYTHONPATH", str(tmp_path / "flux-src"))
    monkeypatch.setenv("PATH", f"{fake / 'bin'}:/usr/bin:/bin")

    outcome = script_gate(
        "test",
        "import os,sys;"
        "sys.exit(1 if os.environ.get('VIRTUAL_ENV') or os.environ.get('PYTHONPATH') else 0)",
    ).run(tmp_path)
    assert outcome.passed


def test_the_shadowing_bin_directory_is_dropped_from_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unsetting VIRTUAL_ENV is not enough: its bin dir is still first on PATH."""
    fake = tmp_path / "flux-venv"
    (fake / "bin").mkdir(parents=True)
    monkeypatch.setenv("VIRTUAL_ENV", str(fake))
    monkeypatch.setenv("PATH", f"{fake / 'bin'}:/usr/bin:/bin")

    env = clean_env()
    assert str(fake / "bin") not in env["PATH"].split(":")
    assert "/usr/bin" in env["PATH"].split(":")


def test_clean_env_keeps_everything_else(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", "/home/dev")
    monkeypatch.setenv("CI", "true")
    env = clean_env()
    assert env["HOME"] == "/home/dev"
    assert env["CI"] == "true"


def test_a_gate_may_still_add_its_own_variables(tmp_path: Path) -> None:
    gate = CommandGate(
        name="test",
        argv=(PY, "-c", "import os,sys; sys.exit(0 if os.environ.get('FLUX_X')=='1' else 1)"),
        env={"FLUX_X": "1"},
    )
    assert gate.run(tmp_path).passed


def test_the_coverage_gate_is_isolated_too(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIRTUAL_ENV", str(tmp_path / "flux-venv"))
    leaked = "import os; print('TOTAL 10 0 %d%%' % (0 if os.environ.get('VIRTUAL_ENV') else 90))"
    gate = CoverageGate(name="coverage", argv=(PY, "-c", leaked), min_percent=80.0)
    assert gate.run(tmp_path).passed
