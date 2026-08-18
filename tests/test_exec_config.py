"""ExecConfig validation — model and effort are always explicit (ADR 0007, 0010)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from flux.errors import ConfigError
from flux.executor import ExecConfig


def make(**overrides: Any) -> ExecConfig:
    base: dict[str, Any] = {"model": "claude-sonnet-5", "effort": "high"}
    base.update(overrides)
    return ExecConfig(**base)


def test_minimal_config_is_valid() -> None:
    cfg = make()
    assert cfg.model == "claude-sonnet-5"
    assert cfg.effort == "high"
    assert cfg.billing_mode == "subscription"
    assert cfg.setting_sources == ("project",)


def test_config_is_frozen() -> None:
    cfg = make()
    with pytest.raises(AttributeError):
        cfg.model = "other"  # type: ignore[misc]


@pytest.mark.parametrize("model", ["", "   "])
def test_blank_model_rejected(model: str) -> None:
    with pytest.raises(ConfigError, match="non-empty model id"):
        make(model=model)


def test_unknown_effort_rejected() -> None:
    with pytest.raises(ConfigError, match="effort"):
        make(effort="ludicrous")


def test_unknown_permission_mode_rejected() -> None:
    with pytest.raises(ConfigError, match="permission_mode"):
        make(permission_mode="yolo")


def test_unknown_setting_source_rejected() -> None:
    with pytest.raises(ConfigError, match="setting_sources"):
        make(setting_sources=("project", "enterprise"))


@pytest.mark.parametrize("field_name", ["max_turns", "max_tokens"])
def test_non_positive_caps_rejected(field_name: str) -> None:
    with pytest.raises(ConfigError, match=field_name):
        make(**{field_name: 0})


def test_usd_cap_rejected_on_subscription() -> None:
    """ADR 0010: dollar caps are meaningless on a subscription; caps are turns + tokens."""
    with pytest.raises(ConfigError, match="api-fallback"):
        make(max_budget_usd=5.0)


def test_usd_cap_allowed_under_api_fallback() -> None:
    cfg = make(billing_mode="api-fallback", max_budget_usd=5.0)
    assert cfg.max_budget_usd == 5.0


def test_non_positive_usd_cap_rejected() -> None:
    with pytest.raises(ConfigError, match="max_budget_usd"):
        make(billing_mode="api-fallback", max_budget_usd=0.0)


def test_relative_cwd_rejected() -> None:
    with pytest.raises(ConfigError, match="absolute path"):
        make(cwd=Path("relative/dir"))


def test_absolute_cwd_accepted(tmp_path: Path) -> None:
    assert make(cwd=tmp_path).cwd == tmp_path
