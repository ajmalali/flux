"""Preflight parks rather than switching billing (ADR 0010)."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Sequence
from typing import Any

import pytest

from flux.errors import BillingPolicyError
from flux.executor import AuthStatus, preflight
from flux.executor import billing as billing_mod

SUBSCRIPTION_PAYLOAD: dict[str, Any] = {
    "loggedIn": True,
    "authMethod": "claude.ai",
    "apiProvider": "firstParty",
    "email": "dev@example.com",
    "subscriptionType": "max",
}

API_KEY_PAYLOAD: dict[str, Any] = {
    "loggedIn": True,
    "authMethod": "claude.ai",
    "apiProvider": "firstParty",
    "apiKeySource": "ANTHROPIC_API_KEY",
    "email": None,
    "subscriptionType": None,
}


RunFn = Callable[..., "subprocess.CompletedProcess[str]"]


def fake_run(stdout: str, returncode: int = 0) -> RunFn:
    def run(argv: Sequence[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(list(argv), returncode, stdout, "")

    return run


def which_claude(_name: str) -> str:
    return "/usr/local/bin/claude"


def which_nothing(_name: str) -> str | None:
    return None


@pytest.fixture
def claude_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(billing_mod.shutil, "which", which_claude)


def test_subscription_status_is_accepted() -> None:
    status = AuthStatus.from_json(SUBSCRIPTION_PAYLOAD)
    assert status.is_subscription
    assert status.subscription_type == "max"


def test_api_key_source_disqualifies_subscription_auth() -> None:
    """An ambient key wins over the login, so the run would bill to the API."""
    assert not AuthStatus.from_json(API_KEY_PAYLOAD).is_subscription


@pytest.mark.parametrize(
    "payload",
    [
        {**SUBSCRIPTION_PAYLOAD, "loggedIn": False},
        {**SUBSCRIPTION_PAYLOAD, "authMethod": "apiKey"},
        {**SUBSCRIPTION_PAYLOAD, "apiProvider": "bedrock"},
    ],
)
def test_non_subscription_payloads_rejected(payload: dict[str, Any]) -> None:
    assert not AuthStatus.from_json(payload).is_subscription


def test_preflight_passes_on_subscription(
    claude_on_path: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(billing_mod.subprocess, "run", fake_run(json.dumps(SUBSCRIPTION_PAYLOAD)))
    assert preflight().email == "dev@example.com"


def test_preflight_strips_credentials_before_probing(
    claude_on_path: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ordering matters: the probe must see the environment the child will get."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-leaked")
    seen: dict[str, bool] = {}

    def run(argv: Sequence[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        seen["key_present"] = "ANTHROPIC_API_KEY" in billing_mod.os.environ
        return subprocess.CompletedProcess(list(argv), 0, json.dumps(SUBSCRIPTION_PAYLOAD), "")

    monkeypatch.setattr(billing_mod.subprocess, "run", run)
    preflight()
    assert seen["key_present"] is False


def test_preflight_parks_when_api_key_wins(
    claude_on_path: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(billing_mod.subprocess, "run", fake_run(json.dumps(API_KEY_PAYLOAD)))
    with pytest.raises(BillingPolicyError) as excinfo:
        preflight()
    assert excinfo.value.reason == "not-subscription"


def test_preflight_parks_when_logged_out(
    claude_on_path: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = {**SUBSCRIPTION_PAYLOAD, "loggedIn": False}
    monkeypatch.setattr(billing_mod.subprocess, "run", fake_run(json.dumps(payload)))
    with pytest.raises(BillingPolicyError) as excinfo:
        preflight()
    assert excinfo.value.reason == "not-logged-in"


def test_preflight_parks_on_billing_redirect(
    claude_on_path: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDE_CODE_USE_BEDROCK", "1")
    with pytest.raises(BillingPolicyError) as excinfo:
        preflight()
    assert excinfo.value.reason == "billing-redirect"
    assert "CLAUDE_CODE_USE_BEDROCK" in excinfo.value.note


def test_preflight_parks_when_cli_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(billing_mod.shutil, "which", which_nothing)
    with pytest.raises(BillingPolicyError) as excinfo:
        preflight()
    assert excinfo.value.reason == "cli-missing"


def test_preflight_parks_on_probe_failure(
    claude_on_path: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(billing_mod.subprocess, "run", fake_run("boom", returncode=1))
    with pytest.raises(BillingPolicyError) as excinfo:
        preflight()
    assert excinfo.value.reason == "auth-probe-failed"


def test_preflight_parks_on_unparseable_probe_output(
    claude_on_path: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(billing_mod.subprocess, "run", fake_run("not json at all"))
    with pytest.raises(BillingPolicyError) as excinfo:
        preflight()
    assert excinfo.value.reason == "auth-probe-unparseable"


def test_preflight_parks_on_probe_timeout(
    claude_on_path: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    def run(_argv: Sequence[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd="claude", timeout=30)

    monkeypatch.setattr(billing_mod.subprocess, "run", run)
    with pytest.raises(BillingPolicyError) as excinfo:
        preflight()
    assert excinfo.value.reason == "auth-probe-timeout"
