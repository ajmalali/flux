"""``flux.toml``: complete defaults, strict parsing, and a lossless round trip.

Two properties matter. Nothing is silently disabled by an absent file — a repo with no
config still gets working defaults. And nothing is silently *mis*read: a wrong type or
an unknown schema version is a ``ConfigError`` naming the key, not a quiet fallback that
changes what "green" means.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from flux.config import (
    SCHEMA_VERSION,
    AbConfig,
    FluxConfig,
    StageProfile,
    config_path,
    default_gates,
    detect_target,
)
from flux.errors import ConfigError
from flux.gates.spec import GateSpec


def write_config(root: Path, body: str) -> Path:
    path = config_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def test_an_absent_config_still_yields_a_working_default(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    config = FluxConfig.load(tmp_path)
    assert config.target == "python"
    assert [g.name for g in config.gates] == ["lint", "typecheck", "test"]
    assert config.profile("implement").model
    assert config.runner.max_review_iters == 3


def test_target_detection_reads_the_repo_manifests(tmp_path: Path) -> None:
    assert detect_target(tmp_path) == "generic"
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    assert detect_target(tmp_path) == "typescript"
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    assert detect_target(tmp_path) == "python"


def test_a_uv_managed_repo_gets_uv_run_gate_commands(tmp_path: Path) -> None:
    """A gate that only works when flux runs it is a gate nobody trusts."""
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    (tmp_path / "uv.lock").write_text("", encoding="utf-8")
    assert default_gates(tmp_path)[0].command[:2] == ("uv", "run")


def test_a_plain_python_repo_gets_bare_gate_commands(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    assert default_gates(tmp_path)[0].command[0] == "ruff"


def test_a_pnpm_repo_gets_pnpm_gate_commands(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "pnpm-lock.yaml").write_text("", encoding="utf-8")
    commands = {g.name: g.command for g in default_gates(tmp_path)}
    assert commands["test"] == ("pnpm", "test")
    assert commands["typecheck"] == ("pnpm", "exec", "tsc", "--noEmit")


def test_an_unrecognised_repo_gets_no_gates_rather_than_a_guess(tmp_path: Path) -> None:
    assert default_gates(tmp_path) == ()


def test_a_config_round_trips_through_toml(tmp_path: Path) -> None:
    """``flux init`` writes what ``FluxConfig`` reads — proven, not assumed."""
    original = FluxConfig(
        root=tmp_path,
        target="python",
        gates=(
            GateSpec(name="test", kind="pytest", command=("pytest", "-q"), timeout_s=90),
            GateSpec(name="cov", kind="coverage", command=("coverage", "report"), min_percent=75.0),
        ),
        stage_commits=False,
        ab=AbConfig(vanilla_every=5, kill_criterion='vanilla wins twice: stop and "think"'),
    )
    write_config(tmp_path, original.to_toml())
    loaded = FluxConfig.load(tmp_path)

    assert loaded.target == original.target
    assert loaded.gates == original.gates
    assert loaded.stage_commits is False
    assert loaded.ab == original.ab
    assert loaded.stages["implement"] == original.stages["implement"]
    assert loaded.review == original.review


def test_the_rendered_config_is_valid_toml(tmp_path: Path) -> None:
    payload = tomllib.loads(FluxConfig(root=tmp_path, gates=default_gates(tmp_path)).to_toml())
    assert payload["schema_version"] == SCHEMA_VERSION


def test_stage_profiles_override_only_what_they_state(tmp_path: Path) -> None:
    write_config(tmp_path, '[stages.implement]\nmodel = "claude-opus-5"\nmax_turns = 12\n')
    profile = FluxConfig.load(tmp_path).profile("implement")
    assert profile.model == "claude-opus-5"
    assert profile.max_turns == 12
    assert profile.effort == "high"  # kept from the default profile


def test_a_stage_flux_ships_no_default_for_must_state_model_and_effort(tmp_path: Path) -> None:
    write_config(tmp_path, "[stages.bespoke]\nmax_turns = 4\n")
    with pytest.raises(ConfigError, match="needs both 'model' and 'effort'"):
        FluxConfig.load(tmp_path)


def test_an_unknown_stage_is_a_named_error(tmp_path: Path) -> None:
    config = FluxConfig.load(tmp_path)
    with pytest.raises(ConfigError, match=r"\[stages.nope\]"):
        config.profile("nope")


def test_a_future_schema_version_refuses_to_guess(tmp_path: Path) -> None:
    write_config(tmp_path, f"schema_version = {SCHEMA_VERSION + 1}\n")
    with pytest.raises(ConfigError, match="upgrade flux"):
        FluxConfig.load(tmp_path)


def test_broken_toml_is_reported_with_its_path(tmp_path: Path) -> None:
    write_config(tmp_path, "this is not = = toml\n")
    with pytest.raises(ConfigError, match="not valid TOML"):
        FluxConfig.load(tmp_path)


@pytest.mark.parametrize(
    "body",
    [
        '[runner]\nmax_review_iters = "three"\n',
        "[runner]\nstage_commits = 1\n",
        "target = 7\n",
        'stages = "implement"\n',
        'gates = "test"\n',
        '[[gates]]\nname = "test"\n',
        "[stages.implement]\nmodel = 5\n",
        '[stages.implement]\neffort = "enormous"\n',
        '[stages.implement]\npermission_mode = "yolo"\n',
    ],
)
def test_a_wrong_type_or_value_is_rejected(tmp_path: Path, body: str) -> None:
    write_config(tmp_path, body)
    with pytest.raises(ConfigError):
        FluxConfig.load(tmp_path)


def test_loop_bounds_come_from_the_runner_table(tmp_path: Path) -> None:
    write_config(tmp_path, "[runner]\nmax_review_iters = 2\nmax_stage_runs = 9\n")
    runner = FluxConfig.load(tmp_path).runner
    assert (runner.max_review_iters, runner.max_stage_runs) == (2, 9)


def test_an_invalid_loop_bound_is_rejected_by_the_runner_config(tmp_path: Path) -> None:
    write_config(tmp_path, "[runner]\nmax_review_iters = 0\n")
    with pytest.raises(ConfigError, match="max_review_iters"):
        FluxConfig.load(tmp_path)


def test_duplicate_gate_names_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="unique"):
        FluxConfig(
            root=tmp_path,
            gates=(
                GateSpec(name="test", command=("a",)),
                GateSpec(name="test", command=("b",)),
            ),
        )


def test_a_profile_becomes_an_exec_config_with_everything_explicit(tmp_path: Path) -> None:
    profile = StageProfile(model="claude-sonnet-5", effort="high", max_turns=7)
    cfg = profile.exec_config(cwd=tmp_path)
    assert (cfg.model, cfg.effort, cfg.max_turns) == ("claude-sonnet-5", "high", 7)
    assert cfg.permission_mode == "acceptEdits"
    assert cfg.billing_mode == "subscription"
    assert cfg.cwd == tmp_path


def test_a_profile_needs_a_real_model_and_effort() -> None:
    with pytest.raises(ConfigError):
        StageProfile(model="  ", effort="high")
    with pytest.raises(ConfigError):
        StageProfile(model="m", effort="enormous")  # pyright: ignore[reportArgumentType]


def test_the_kill_criterion_is_part_of_the_committed_config(tmp_path: Path) -> None:
    """ADR 0008: it only binds if it is written down where a run can read it."""
    rendered = FluxConfig(root=tmp_path).to_toml()
    assert "kill_criterion" in rendered
    assert "vanilla" in rendered.lower()


def test_a_profile_without_hooks_yields_a_config_the_executor_can_translate(
    tmp_path: Path,
) -> None:
    """Regression: the default had been read off the class, where it is a slot descriptor."""
    from flux.executor.sdk import build_options
    from flux.executor.types import PromptPack

    cfg = StageProfile(model="claude-sonnet-5", effort="high").exec_config(cwd=tmp_path)
    assert dict(cfg.hooks) == {}
    assert build_options(PromptPack(system_prompt="role"), cfg).hooks is None


def test_hooks_are_carried_through_when_a_stage_supplies_them(tmp_path: Path) -> None:
    profile = StageProfile(model="claude-sonnet-5", effort="high")
    cfg = profile.exec_config(cwd=tmp_path, hooks={"PreToolUse": []})
    assert "PreToolUse" in cfg.hooks


def test_tool_allow_and_deny_lists_reach_the_exec_config(tmp_path: Path) -> None:
    cfg = StageProfile(model="m", effort="high").exec_config(
        cwd=tmp_path, allowed_tools=["Read"], disallowed_tools=["Bash"]
    )
    assert cfg.allowed_tools == ("Read",)
    assert cfg.disallowed_tools == ("Bash",)
