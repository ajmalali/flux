"""Shared fixtures.

Every test in this suite runs without touching the network. The one exception is
``tests/test_live_roundtrip.py``, which is marked ``live`` and skipped unless
``GUS_LIVE_TESTS=1``.
"""

from __future__ import annotations

import pytest

from gus.executor.billing import API_CREDENTIAL_VARS, BILLING_REDIRECT_VARS


@pytest.fixture(autouse=True)
def clean_billing_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start every test from an environment with no credentials or billing redirects.

    Without this, a developer's real ``ANTHROPIC_API_KEY`` would make the strip tests
    pass for the wrong reason (or the redirect tests fail for an unrelated one).
    """
    for name in (*API_CREDENTIAL_VARS, *BILLING_REDIRECT_VARS):
        monkeypatch.delenv(name, raising=False)
