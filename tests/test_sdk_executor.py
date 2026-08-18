"""SDK translation and message folding — no CLI is spawned.

These cover the parts of ``sdk.py`` that are pure: config → SDK options, and the
message stream → :class:`~flux.executor.types.ExecResult` fold.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, cast

import pytest
from claude_agent_sdk import (
    AssistantMessage,
    CLINotFoundError,
    Message,
    ModelUsage,
    RateLimitEvent,
    RateLimitInfo,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)

from flux.executor import ExecConfig, ExecResult, PromptPack, build_options
from flux.executor.sdk import (
    ClaudeAgentSDKExecutor,
    Collector,
    extract_provider,
    extract_usage,
)

PACK = PromptPack(
    system_prompt="You are the review stage.",
    plan_summary="PLAN",
    context_pack="FILES",
    stage_tail="TAIL",
)


def make_result(
    *,
    is_error: bool = False,
    subtype: str = "success",
    usage: dict[str, Any] | None = None,
    model_usage: dict[str, ModelUsage] | None = None,
    errors: list[str] | None = None,
) -> ResultMessage:
    return ResultMessage(
        subtype=subtype,
        duration_ms=1200,
        duration_api_ms=900,
        is_error=is_error,
        num_turns=3,
        session_id="sess-1",
        result="done",
        total_cost_usd=0.0123,
        usage=usage,
        model_usage=model_usage,
        errors=errors,
    )


def model_usage(**fields: int | str) -> ModelUsage:
    """A ModelUsage with only the fields a test cares about."""
    return cast(ModelUsage, fields)


def test_build_options_carries_explicit_model_and_effort() -> None:
    cfg = ExecConfig(model="claude-opus-5", effort="xhigh", permission_mode="plan")
    options = build_options(PACK, cfg)
    assert options.model == "claude-opus-5"
    assert options.effort == "xhigh"
    assert options.permission_mode == "plan"


def test_build_options_maps_the_turn_cap_and_never_a_dollar_cap() -> None:
    """ADR 0010: subscription caps are turns + tokens, never dollars."""
    cfg = ExecConfig(model="claude-sonnet-5", effort="high", max_turns=7, max_tokens=1234)
    options = build_options(PACK, cfg)
    assert options.max_turns == 7
    assert options.max_budget_usd is None


def test_token_budget_is_not_advertised_to_the_api_by_default() -> None:
    """Models without task-budget support reject the request with a 400."""
    cfg = ExecConfig(model="claude-haiku-4-5-20251001", effort="low", max_tokens=1234)
    assert build_options(PACK, cfg).task_budget is None


def test_token_budget_is_advertised_when_explicitly_enabled() -> None:
    cfg = ExecConfig(
        model="claude-sonnet-5", effort="high", max_tokens=1234, advertise_token_budget=True
    )
    assert build_options(PACK, cfg).task_budget == {"total": 1234}


def test_build_options_passes_usd_cap_only_under_api_fallback() -> None:
    cfg = ExecConfig(
        model="claude-sonnet-5", effort="high", billing_mode="api-fallback", max_budget_usd=2.5
    )
    assert build_options(PACK, cfg).max_budget_usd == 2.5


def test_build_options_sends_system_prompt_separately_from_the_user_prompt() -> None:
    """Keeping the role prompt out of the user turn is what makes the prefix cacheable."""
    options = build_options(PACK, ExecConfig(model="m", effort="high"))
    assert options.system_prompt == PACK.system_prompt
    assert PACK.system_prompt not in PACK.prompt


def test_build_options_forwards_tools_sources_and_cwd(tmp_path: Path) -> None:
    cfg = ExecConfig(
        model="m",
        effort="low",
        allowed_tools=("Read", "Grep"),
        disallowed_tools=("Bash",),
        setting_sources=("project", "local"),
        cwd=tmp_path,
    )
    options = build_options(PACK, cfg)
    assert options.allowed_tools == ["Read", "Grep"]
    assert options.disallowed_tools == ["Bash"]
    assert options.setting_sources == ["project", "local"]
    assert options.cwd == tmp_path


def test_build_options_omits_hooks_when_none_configured() -> None:
    assert build_options(PACK, ExecConfig(model="m", effort="high")).hooks is None


def test_provider_is_read_from_the_per_model_breakdown() -> None:
    """A silent billing-surface change should be visible in the metrics history."""
    result = make_result(model_usage={"m": model_usage(provider="firstParty")})
    assert extract_provider(result) == "firstParty"


def test_provider_is_none_when_unreported_or_inconsistent() -> None:
    assert extract_provider(make_result()) is None
    mixed = make_result(
        model_usage={
            "a": model_usage(provider="firstParty"),
            "b": model_usage(provider="bedrock"),
        }
    )
    assert extract_provider(mixed) is None


def test_extract_usage_prefers_the_per_model_breakdown() -> None:
    result = make_result(
        model_usage={
            "claude-sonnet-5": model_usage(
                inputTokens=10,
                outputTokens=20,
                cacheReadInputTokens=30,
                cacheCreationInputTokens=40,
            )
        },
        usage={"input_tokens": 999},
    )
    usage = extract_usage(result)
    assert (usage.input_tokens, usage.output_tokens) == (10, 20)
    assert usage.cache_read_tokens == 30
    assert usage.billable_input_tokens == 50
    assert usage.budget_tokens == 70  # cache reads excluded: they recur every turn
    assert usage.total_tokens == 100


def test_extract_usage_sums_across_models() -> None:
    result = make_result(
        model_usage={
            "a": model_usage(inputTokens=1, outputTokens=2),
            "b": model_usage(inputTokens=3, outputTokens=4),
        }
    )
    usage = extract_usage(result)
    assert (usage.input_tokens, usage.output_tokens) == (4, 6)


def test_extract_usage_falls_back_to_the_flat_usage_dict() -> None:
    result = make_result(
        usage={
            "input_tokens": 5,
            "output_tokens": 6,
            "cache_read_input_tokens": 7,
            "cache_creation_input_tokens": 8,
        }
    )
    usage = extract_usage(result)
    assert usage.total_tokens == 26


def test_extract_usage_tolerates_missing_fields() -> None:
    assert extract_usage(make_result()).total_tokens == 0


def fold(*messages: Message) -> ExecResult:
    collector = Collector(pack=PACK, cfg=ExecConfig(model="claude-sonnet-5", effort="high"))
    for message in messages:
        collector.absorb(message)
    return collector.finish()


def test_collector_counts_tool_uses_and_flags_exploration() -> None:
    assistant = AssistantMessage(
        content=[
            TextBlock(text="looking"),
            ToolUseBlock(id="1", name="Read", input={}),
            ToolUseBlock(id="2", name="Read", input={}),
            ToolUseBlock(id="3", name="Edit", input={}),
        ],
        model="claude-sonnet-5",
        session_id="sess-1",
    )
    result = fold(assistant, make_result())
    assert result.tool_uses == {"Read": 2, "Edit": 1}
    assert result.exploratory_calls == 2


def test_collector_records_the_result_fields() -> None:
    result = fold(make_result())
    assert result.ok is True
    assert result.text == "done"
    assert result.num_turns == 3
    assert result.duration_ms == 1200
    assert result.total_cost_usd == pytest.approx(0.0123)
    assert result.pack_chars == PACK.size_chars


def test_collector_captures_usage_window_pressure() -> None:
    """ADR 0010: window pressure is what the scheduler parks on, so it must survive."""
    event = RateLimitEvent(
        rate_limit_info=RateLimitInfo(
            status="allowed_warning",
            rate_limit_type="five_hour",
            utilization=0.82,
            resets_at=1_800_000_000,
        ),
        uuid="u",
        session_id="sess-1",
    )
    result = fold(event, make_result())
    window = result.window
    assert window is not None
    assert window.status == "allowed_warning"
    assert window.window == "five_hour"
    assert window.utilization == pytest.approx(0.82)
    assert window.limit_hit is False


def test_collector_marks_a_rejected_window_as_a_limit_hit() -> None:
    event = RateLimitEvent(
        rate_limit_info=RateLimitInfo(status="rejected", resets_at=1),
        uuid="u",
        session_id="s",
    )
    result = fold(event, make_result())
    assert result.window is not None
    assert result.window.limit_hit is True


def test_collector_reports_an_error_result_without_raising() -> None:
    """A failed session is data for the runner, not an exception."""
    result = fold(make_result(is_error=True, subtype="error_max_turns", errors=["capped"]))
    assert result.ok is False
    assert result.subtype == "error_max_turns"
    assert result.error == "capped"


def test_collector_failed_reports_a_cli_error_as_a_session_outcome() -> None:
    """The SDK raises a bare Exception on terminal CLI errors; the runner needs data."""
    collector = Collector(pack=PACK, cfg=ExecConfig(model="m", effort="high"))
    collector.absorb(
        AssistantMessage(content=[TextBlock(text="partial")], model="m", session_id="s")
    )
    result = collector.failed("Reached maximum number of turns (1)")
    assert result.ok is False
    assert result.subtype == "stream_error"
    assert result.error is not None and "maximum number of turns" in result.error
    assert result.text == "partial", "whatever the session produced is still reported"


def test_run_converts_a_stream_error_into_a_failed_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def exploding_query(**_kwargs: object) -> AsyncIterator[Message]:
        raise RuntimeError("Claude Code returned an error result: max turns")
        yield  # pragma: no cover - makes this an async generator

    monkeypatch.setattr("flux.executor.sdk.query", exploding_query)
    executor = ClaudeAgentSDKExecutor(verify_billing=False)
    result = executor.run(PACK, ExecConfig(model="m", effort="high"))
    assert result.ok is False
    assert result.error is not None and "max turns" in result.error


def test_run_lets_environment_faults_surface(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing CLI is not something the runner can retry its way out of."""

    async def exploding_query(**_kwargs: object) -> AsyncIterator[Message]:
        raise CLINotFoundError("claude not installed")
        yield  # pragma: no cover - makes this an async generator

    monkeypatch.setattr("flux.executor.sdk.query", exploding_query)
    executor = ClaudeAgentSDKExecutor(verify_billing=False)
    with pytest.raises(CLINotFoundError):
        executor.run(PACK, ExecConfig(model="m", effort="high"))


def test_collector_handles_a_stream_that_ends_without_a_result() -> None:
    assistant = AssistantMessage(
        content=[TextBlock(text="partial")], model="m", session_id="sess-9"
    )
    result = fold(assistant)
    assert result.ok is False
    assert result.subtype == "no_result"
    assert result.text == "partial"


def test_preflight_is_cached_after_the_first_call(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def fake_preflight(**_kwargs: object) -> object:
        calls["n"] += 1
        return object()

    monkeypatch.setattr("flux.executor.sdk.preflight", fake_preflight)
    executor = ClaudeAgentSDKExecutor()
    executor.ensure_preflight()
    executor.ensure_preflight()
    assert calls["n"] == 1


def test_preflight_can_be_disabled_for_tests() -> None:
    executor = ClaudeAgentSDKExecutor(verify_billing=False)
    assert executor.ensure_preflight() is None
    assert executor.auth is None


def test_build_options_grants_directories_outside_the_worktree(tmp_path: Path) -> None:
    """``add_dirs`` is how a stage reaches its artifact once worktree ≠ root.

    Observed live on 2026-08-18: with the context directory out of reach, the implement
    stage wrote `impl-notes.md` at the same relative path *inside the worktree*, where
    the runner does not look, and the ticket parked after two paid attempts.
    """
    context = tmp_path / "context"
    cfg = ExecConfig(model="m", effort="high", cwd=tmp_path, add_dirs=(context,))
    assert build_options(PACK, cfg).add_dirs == [str(context)]


def test_build_options_defaults_the_system_prompt_to_the_clis_own(tmp_path: Path) -> None:
    """An empty pack prompt means "the CLI default", which is what the A/B baseline is."""
    options = build_options(PromptPack(system_prompt="", context_pack="do it"), ExecConfig(
        model="m", effort="high"
    ))
    assert options.system_prompt is None
