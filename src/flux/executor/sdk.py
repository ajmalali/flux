"""The Claude Agent SDK executor — the only module in flux that imports the SDK (ADR 0007).

Every ``run()`` is a fresh, one-shot session (ADR 0003) that rides the logged-in
subscription (ADR 0010). Preflight runs before the first session of the process and
its verdict is cached: the auth state does not change mid-run, and re-probing before
every stage would add a subprocess spawn to each one.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import AsyncIterator, Mapping
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKError,
    Message,
    RateLimitEvent,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    query,
)

from flux.executor.billing import AuthStatus, preflight
from flux.executor.types import (
    ExecConfig,
    ExecResult,
    PromptPack,
    Usage,
    WindowPressure,
)

# Set by the SDK-spawned CLI's User-Agent so runs are attributable in usage logs.
_CLIENT_APP = "flux/0.1.0"


class ClaudeAgentSDKExecutor:
    """Runs a :class:`~flux.executor.types.PromptPack` through the Claude Agent SDK.

    Args:
        cli_path: Explicit path to the ``claude`` binary. Defaults to PATH lookup.
        verify_billing: Run the ADR 0010 preflight before the first session. Only
            tests that never spawn a CLI should turn this off.
    """

    def __init__(self, *, cli_path: str | None = None, verify_billing: bool = True) -> None:
        self._cli_path = cli_path
        self._verify_billing = verify_billing
        self._auth: AuthStatus | None = None

    @property
    def auth(self) -> AuthStatus | None:
        """The cached preflight verdict, or ``None`` before the first run."""
        return self._auth

    def ensure_preflight(self) -> AuthStatus | None:
        """Run (and cache) the billing preflight. Idempotent.

        Raises:
            BillingPolicyError: the environment would not bill to the subscription.
        """
        if not self._verify_billing:
            return None
        if self._auth is None:
            self._auth = preflight(cli_path=self._cli_path)
        return self._auth

    def run(self, pack: PromptPack, cfg: ExecConfig) -> ExecResult:
        """Execute one fresh session. See :class:`~flux.executor.protocol.Executor`."""
        self.ensure_preflight()
        return asyncio.run(self._run_async(pack, cfg))

    async def _run_async(self, pack: PromptPack, cfg: ExecConfig) -> ExecResult:
        options = build_options(pack, cfg)
        collector = Collector(pack=pack, cfg=cfg)
        stream: AsyncIterator[Message] = query(prompt=pack.prompt, options=options)
        iterator = stream.__aiter__()
        while True:
            try:
                message = await iterator.__anext__()
            except StopAsyncIteration:
                break
            except ClaudeSDKError:
                # Environment fault (CLI missing, process died, unparseable output).
                # The runner cannot retry its way out of these, so let them surface.
                raise
            except Exception as exc:
                # The SDK reports terminal CLI error results (turn cap, budget cap,
                # API error) by raising a bare Exception from the stream. Those are
                # session outcomes, not faults: the runner decides whether to retry
                # or park, so they come back as a failed ExecResult. Only the stream
                # advance is wrapped, so a bug in absorb() still raises.
                return collector.failed(str(exc))
            collector.absorb(message)
        return collector.finish()


def build_options(pack: PromptPack, cfg: ExecConfig) -> ClaudeAgentOptions:
    """Translate flux config into SDK options. Pure — no I/O, so it is directly testable.

    Note what is *not* here: ``env`` carries no credential overrides. The SDK merges
    ``env`` over the inherited process environment, so an override cannot unset an
    inherited ``ANTHROPIC_API_KEY``; the removal happens in
    :func:`flux.executor.billing.sanitize_process_env` before the process spawns.
    """
    # SDK hook types are re-exported as implicit aliases; keeping this Any avoids
    # dragging them across the ADR 0007 seam just to satisfy a cast.
    hooks: Any = dict(cfg.hooks) or None
    task_budget: Any = {"total": cfg.max_tokens} if cfg.advertise_token_budget else None
    return ClaudeAgentOptions(
        model=cfg.model,
        effort=cfg.effort,
        permission_mode=cfg.permission_mode,
        allowed_tools=list(cfg.allowed_tools),
        disallowed_tools=list(cfg.disallowed_tools),
        max_turns=cfg.max_turns,
        max_budget_usd=cfg.max_budget_usd,
        task_budget=task_budget,
        setting_sources=list(cfg.setting_sources),
        # Empty means "the CLI's own default preset", which is what the A/B baseline
        # arm needs: a vanilla session must not be handed a harness system prompt, and
        # an empty string here would give it a blank one instead of the real default.
        system_prompt=pack.system_prompt or None,
        cwd=cfg.cwd,
        add_dirs=[str(path) for path in cfg.add_dirs],
        hooks=hooks,
        env={"CLAUDE_AGENT_SDK_CLIENT_APP": _CLIENT_APP},
    )


class Collector:
    """Folds the SDK message stream into a single :class:`ExecResult`."""

    def __init__(self, *, pack: PromptPack, cfg: ExecConfig) -> None:
        self._pack = pack
        self._cfg = cfg
        self._texts: list[str] = []
        self._tool_uses: Counter[str] = Counter()
        self._window: WindowPressure | None = None
        self._result: ResultMessage | None = None
        self._session_id = ""

    def absorb(self, message: Message) -> None:
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    self._texts.append(block.text)
                elif isinstance(block, ToolUseBlock):
                    self._tool_uses[block.name] += 1
            if message.session_id:
                self._session_id = message.session_id
        elif isinstance(message, RateLimitEvent):
            info = message.rate_limit_info
            self._window = WindowPressure(
                status=info.status,
                window=info.rate_limit_type,
                utilization=info.utilization,
                resets_at=info.resets_at,
            )
        elif isinstance(message, ResultMessage):
            self._result = message
            self._session_id = message.session_id or self._session_id

    def failed(self, error: str, *, subtype: str = "stream_error") -> ExecResult:
        """A session that ended in a CLI-reported error, with whatever was collected."""
        return self._partial(subtype=subtype, error=error)

    def _partial(self, *, subtype: str, error: str) -> ExecResult:
        return ExecResult(
            ok=False,
            text="\n".join(self._texts),
            session_id=self._session_id,
            model=self._cfg.model,
            effort=self._cfg.effort,
            billing_mode=self._cfg.billing_mode,
            tool_uses=dict(self._tool_uses),
            window=self._window,
            pack_chars=self._pack.size_chars,
            subtype=subtype,
            error=error,
        )

    def finish(self) -> ExecResult:
        result = self._result
        if result is None:
            # The CLI ended without a result message: treat as a failed session so the
            # runner retries or parks, rather than surfacing a stack trace mid-pipeline.
            return self._partial(
                subtype="no_result", error="session ended without a result message"
            )
        return ExecResult(
            ok=not result.is_error,
            text=result.result if result.result is not None else "\n".join(self._texts),
            session_id=self._session_id,
            model=self._cfg.model,
            effort=self._cfg.effort,
            billing_mode=self._cfg.billing_mode,
            usage=extract_usage(result),
            total_cost_usd=result.total_cost_usd,
            num_turns=result.num_turns,
            duration_ms=result.duration_ms,
            duration_api_ms=result.duration_api_ms,
            subtype=result.subtype,
            stop_reason=result.stop_reason,
            provider=extract_provider(result),
            tool_uses=dict(self._tool_uses),
            window=self._window,
            pack_chars=self._pack.size_chars,
            error="; ".join(result.errors) if result.errors else None,
        )


def extract_usage(result: ResultMessage) -> Usage:
    """Pull token counts out of a ``ResultMessage``.

    ``model_usage`` is preferred: it is the CLI's per-model breakdown and always
    carries the cache fields. ``usage`` is the flat fallback for older CLI builds,
    where the cache keys are snake_case.
    """
    if result.model_usage:
        total = Usage()
        for entry in result.model_usage.values():
            total = total + Usage(
                input_tokens=_int(entry.get("inputTokens")),
                output_tokens=_int(entry.get("outputTokens")),
                cache_read_tokens=_int(entry.get("cacheReadInputTokens")),
                cache_creation_tokens=_int(entry.get("cacheCreationInputTokens")),
            )
        return total
    usage: Mapping[str, Any] = result.usage or {}
    return Usage(
        input_tokens=_int(usage.get("input_tokens")),
        output_tokens=_int(usage.get("output_tokens")),
        cache_read_tokens=_int(usage.get("cache_read_input_tokens")),
        cache_creation_tokens=_int(usage.get("cache_creation_input_tokens")),
    )


def extract_provider(result: ResultMessage) -> str | None:
    """The billing provider the CLI reported, if it reported one consistently."""
    if not result.model_usage:
        return None
    providers = {
        entry.get("provider") for entry in result.model_usage.values() if entry.get("provider")
    }
    if len(providers) != 1:
        return None
    (provider,) = providers
    return provider if isinstance(provider, str) else None


def _int(value: object) -> int:
    return value if isinstance(value, int) else 0
