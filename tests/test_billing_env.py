"""API credentials must never reach the child process (ADR 0010).

The SDK spawns the Claude Code CLI with ``{**os.environ, **options.env}``. That merge
is why these tests exist twice over: once to prove ``options.env`` *cannot* remove an
inherited credential, and once to prove flux's actual mechanism — deleting it from
``os.environ`` before the spawn — does.
"""

from __future__ import annotations

import os

import pytest

from flux.executor import (
    API_CREDENTIAL_VARS,
    ExecConfig,
    PromptPack,
    build_options,
    child_env_from,
    detect_billing_redirects,
    sanitize_process_env,
)
from flux.executor.billing import BILLING_REDIRECT_VARS

CFG = ExecConfig(model="claude-sonnet-5", effort="high")
PACK = PromptPack(system_prompt="sys", stage_tail="do the thing")


def test_options_env_cannot_unset_an_inherited_credential() -> None:
    """Documents the constraint that forces the os.environ strip.

    If this ever fails, the SDK changed its merge and flux could stop mutating the
    parent environment.
    """
    inherited = {"ANTHROPIC_API_KEY": "sk-real"}
    child = child_env_from(inherited, {"ANTHROPIC_API_KEY": ""})
    assert "ANTHROPIC_API_KEY" in child, "override sets an empty value, it does not remove"


@pytest.mark.parametrize("name", API_CREDENTIAL_VARS)
def test_sanitize_removes_credential_from_process_env(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(name, "sk-should-not-survive")
    removed = sanitize_process_env()
    assert removed[name] == "sk-should-not-survive"
    assert name not in os.environ


def test_sanitize_is_idempotent_and_reports_only_what_it_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-1")
    assert set(sanitize_process_env()) == {"ANTHROPIC_API_KEY"}
    assert sanitize_process_env() == {}


def test_child_env_has_no_credentials_after_sanitize(monkeypatch: pytest.MonkeyPatch) -> None:
    """The end-to-end guarantee, asserted on the exact env the SDK would build."""
    for name in API_CREDENTIAL_VARS:
        monkeypatch.setenv(name, "sk-leaked")

    sanitize_process_env()
    options = build_options(PACK, CFG)
    child_env = child_env_from(os.environ, options.env)

    leaked = [name for name in API_CREDENTIAL_VARS if name in child_env]
    assert leaked == [], f"credentials reached the child environment: {leaked}"


def test_build_options_does_not_inject_credentials() -> None:
    """flux never *adds* an API credential either, whatever the ambient env holds."""
    options = build_options(PACK, CFG)
    assert not set(options.env) & set(API_CREDENTIAL_VARS)


@pytest.mark.parametrize("name", BILLING_REDIRECT_VARS)
def test_billing_redirects_are_detected_not_stripped(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A deliberate Bedrock/Vertex setup is surfaced, never silently undone."""
    monkeypatch.setenv(name, "1")
    sanitize_process_env()
    assert detect_billing_redirects() == [name]
    assert os.environ[name] == "1"


def test_no_redirects_detected_in_a_clean_environment() -> None:
    assert detect_billing_redirects() == []
