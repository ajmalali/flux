"""One real session against the live subscription — the T2 acceptance test.

Skipped unless ``FLUX_LIVE_TESTS=1``, because it spends real usage-window budget and
needs a logged-in CLI. Run it with::

    FLUX_LIVE_TESTS=1 uv run pytest -m live

What it proves, end to end: preflight confirms subscription auth, a fresh session
runs with an explicit model and effort, usage comes back populated, and the metrics
line that lands on disk carries the billing mode.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from flux.executor import ClaudeAgentSDKExecutor, ExecConfig, PromptPack
from flux.metrics import MetricRecord, MetricsStore

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.environ.get("FLUX_LIVE_TESTS") != "1",
        reason="live subscription test; set FLUX_LIVE_TESTS=1 to run",
    ),
]


def test_one_round_trip_on_subscription_auth_writes_a_metrics_line(tmp_path: Path) -> None:
    executor = ClaudeAgentSDKExecutor()
    auth = executor.ensure_preflight()
    assert auth is not None and auth.is_subscription

    pack = PromptPack(
        system_prompt="You are a terse test harness probe. Answer in one word.",
        stage_tail="Reply with exactly: pong",
    )
    cfg = ExecConfig(
        model="claude-haiku-4-5-20251001",
        effort="low",
        permission_mode="plan",
        allowed_tools=(),
        max_turns=1,
        max_tokens=2_000,
    )

    result = executor.run(pack, cfg)

    assert result.ok, f"session failed: {result.subtype} {result.error}"
    assert "pong" in result.text.lower()
    assert result.billing_mode == "subscription"
    assert result.provider == "firstParty", f"billed to {result.provider}, not the subscription"
    assert result.model == cfg.model
    assert result.effort == cfg.effort
    assert result.usage.output_tokens > 0
    assert result.session_id

    store = MetricsStore(tmp_path / "metrics.jsonl")
    written = store.record(
        MetricRecord.from_exec_result(ticket="live-probe", stage="smoke", result=result)
    )
    (read_back,) = store.read()
    assert read_back == written
    assert read_back.billing_mode == "subscription"
    assert read_back.provider == "firstParty"
    assert read_back.output_tokens == result.usage.output_tokens
    assert read_back.total_tokens > 0
