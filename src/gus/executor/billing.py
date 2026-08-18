"""Subscription-auth preflight and child-environment sanitation (ADR 0010).

gus runs on the user's logged-in Claude subscription. Two things have to be true
before any session starts, and neither can be assumed:

1. **No API credential reaches the child process.** The Agent SDK spawns the Claude
   Code CLI with ``{**os.environ, **options.env}`` — ``options.env`` can override a
   variable but cannot *unset* one. So the only reliable strip is to remove the
   variables from this process's ``os.environ`` before spawning. That is what
   :func:`sanitize_process_env` does.
2. **The CLI is actually on subscription auth.** ``claude auth status --json`` reports
   it, including an ``apiKeySource`` field that appears precisely when a key is
   winning over the subscription login. Preflight runs that probe in the sanitized
   environment, so it sees what the child will see.

Any deviation parks (:class:`~gus.errors.BillingPolicyError`). There is no code path
here that switches to API billing — the fallback ladder needs user approval and lands
with the runner.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from gus.errors import BillingPolicyError
from gus.jsonio import as_json_mapping

# Credentials that would bill this run to an API account instead of the subscription.
API_CREDENTIAL_VARS: tuple[str, ...] = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
)

# Variables that redirect execution to a different billing surface entirely.
# These are detected and parked, never silently stripped: unsetting a deliberate
# Bedrock/Vertex setup behind the user's back would be its own kind of surprise.
BILLING_REDIRECT_VARS: tuple[str, ...] = (
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_BEDROCK_BASE_URL",
    "ANTHROPIC_VERTEX_BASE_URL",
    "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX",
)

_AUTH_PROBE_TIMEOUT_S = 30


@dataclass(frozen=True, slots=True)
class AuthStatus:
    """Parsed ``claude auth status --json`` output."""

    logged_in: bool
    auth_method: str | None
    api_provider: str | None
    api_key_source: str | None
    subscription_type: str | None
    email: str | None
    raw: Mapping[str, Any]

    @property
    def is_subscription(self) -> bool:
        """True only for a first-party claude.ai login with no API key overriding it."""
        return (
            self.logged_in
            and self.auth_method == "claude.ai"
            and self.api_provider == "firstParty"
            and self.api_key_source is None
        )

    @classmethod
    def from_json(cls, payload: Mapping[str, Any]) -> AuthStatus:
        return cls(
            logged_in=bool(payload.get("loggedIn")),
            auth_method=_opt_str(payload.get("authMethod")),
            api_provider=_opt_str(payload.get("apiProvider")),
            api_key_source=_opt_str(payload.get("apiKeySource")),
            subscription_type=_opt_str(payload.get("subscriptionType")),
            email=_opt_str(payload.get("email")),
            raw=dict(payload),
        )


def _opt_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def sanitize_process_env(
    env: dict[str, str] | None = None,
    *,
    names: Iterable[str] = API_CREDENTIAL_VARS,
) -> dict[str, str]:
    """Remove API credentials from ``env`` in place; return what was removed.

    Defaults to this process's ``os.environ``, which is the mapping the SDK copies
    into the child. Deleting here is the only way to make the variable absent from
    the child — ``ClaudeAgentOptions.env`` merges over the inherited environment and
    so can set a variable but never unset one.
    """
    target = os.environ if env is None else env
    removed: dict[str, str] = {}
    for name in names:
        value = target.pop(name, None)
        if value is not None:
            removed[name] = value
    return removed


def detect_billing_redirects(env: Mapping[str, str] | None = None) -> list[str]:
    """Return the names of set billing-redirect variables (Bedrock/Vertex/base URL)."""
    source = os.environ if env is None else env
    return [name for name in BILLING_REDIRECT_VARS if source.get(name)]


def child_env_from(process_env: Mapping[str, str], overrides: Mapping[str, str]) -> dict[str, str]:
    """Reproduce the SDK's child-environment merge, for assertions.

    Mirrors ``claude_agent_sdk/_internal/transport/subprocess_cli.py``: the child gets
    the inherited process environment with ``ClaudeAgentOptions.env`` merged on top.
    Tests use this to prove a credential is gone rather than merely overridden.
    """
    return {**process_env, **overrides}


def query_auth_status(
    *,
    cli_path: str | None = None,
    env: Mapping[str, str] | None = None,
    timeout: int = _AUTH_PROBE_TIMEOUT_S,
) -> AuthStatus:
    """Run ``claude auth status --json`` and parse it.

    Raises:
        BillingPolicyError: the CLI is missing, failed, or emitted unparseable output.
            Parking is the right response: gus cannot prove it is on subscription auth.
    """
    executable = cli_path or shutil.which("claude")
    if executable is None:
        raise BillingPolicyError(
            "claude CLI not found on PATH; cannot verify subscription auth (ADR 0010)",
            reason="cli-missing",
        )
    try:
        completed = subprocess.run(  # fixed argv, no shell
            [executable, "auth", "status", "--json"],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=dict(env) if env is not None else None,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise BillingPolicyError(
            f"`claude auth status` timed out after {timeout}s", reason="auth-probe-timeout"
        ) from exc
    except OSError as exc:
        raise BillingPolicyError(
            f"could not run `claude auth status`: {exc}", reason="auth-probe-failed"
        ) from exc

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise BillingPolicyError(
            f"`claude auth status` exited {completed.returncode}: {detail}",
            reason="auth-probe-failed",
        )
    try:
        payload: Any = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise BillingPolicyError(
            f"`claude auth status` emitted non-JSON output: {completed.stdout[:200]!r}",
            reason="auth-probe-unparseable",
        ) from exc
    mapping = as_json_mapping(payload)
    if mapping is None:
        raise BillingPolicyError(
            f"`claude auth status` returned {type(payload).__name__}, expected an object",
            reason="auth-probe-unparseable",
        )
    return AuthStatus.from_json(mapping)


def preflight(*, cli_path: str | None = None, strip_env: bool = True) -> AuthStatus:
    """Assert this process will bill to the subscription; strip credentials first.

    Order matters. Credentials are removed from ``os.environ`` *before* the auth
    probe runs, so the probe reports the environment the child will actually get —
    otherwise a stray ``ANTHROPIC_API_KEY`` would make preflight pass on a reading
    that no longer applies once we strip it.

    Returns:
        The verified :class:`AuthStatus`.

    Raises:
        BillingPolicyError: a billing redirect is configured, or the CLI is not on
            first-party subscription auth. Both park (ADR 0010): switching to API
            billing requires explicit user approval, which lives above this layer.
    """
    if strip_env:
        sanitize_process_env()

    redirects = detect_billing_redirects()
    if redirects:
        raise BillingPolicyError(
            "billing-redirect environment variables are set: "
            f"{', '.join(redirects)}. gus runs on subscription auth (ADR 0010); "
            "unset them or approve an API fallback explicitly.",
            reason="billing-redirect",
        )

    status = query_auth_status(cli_path=cli_path)
    if not status.logged_in:
        raise BillingPolicyError(
            "Claude CLI is not logged in; run `claude auth login` (ADR 0010 trigger a)",
            reason="not-logged-in",
        )
    if not status.is_subscription:
        raise BillingPolicyError(
            "Claude CLI is not on first-party subscription auth "
            f"(authMethod={status.auth_method!r}, apiProvider={status.api_provider!r}, "
            f"apiKeySource={status.api_key_source!r}). gus will not bill to an API "
            "account without explicit approval (ADR 0010).",
            reason="not-subscription",
        )
    return status
