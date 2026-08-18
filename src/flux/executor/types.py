"""Value types on the executor seam (design.md §1, ADR 0007).

Nothing in this module imports ``claude_agent_sdk``: these types are the vocabulary
stage and runner code is allowed to depend on. ``sdk.py`` translates them.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, get_args

from flux.errors import ConfigError

EffortLevel = Literal["low", "medium", "high", "xhigh", "max"]
PermissionMode = Literal["default", "acceptEdits", "bypassPermissions", "plan", "dontAsk"]
SettingSource = Literal["user", "project", "local"]
BillingMode = Literal["subscription", "api-fallback"]

EFFORT_LEVELS: frozenset[str] = frozenset(get_args(EffortLevel))
PERMISSION_MODES: frozenset[str] = frozenset(get_args(PermissionMode))
SETTING_SOURCES: frozenset[str] = frozenset(get_args(SettingSource))
BILLING_MODES: frozenset[str] = frozenset(get_args(BillingMode))

# Rough char→token ratio, used only for the "pack size must not grow across stages"
# invariant (design.md §2). It is a comparison aid, never a billing figure.
_CHARS_PER_TOKEN = 4

# Shared immutable empties: frozen dataclasses need no factory for these. NO_HOOKS is
# public because callers building an ExecConfig need the default *value* — reading
# ``ExecConfig.hooks`` off the class gives a slot descriptor, not an empty mapping.
NO_HOOKS: Mapping[str, Sequence[Any]] = MappingProxyType({})
_NO_TOOL_USES: Mapping[str, int] = MappingProxyType({})


@dataclass(frozen=True, slots=True)
class PromptPack:
    """The complete input to one stage session (design.md §2).

    The split is deliberate and load-bearing for prompt caching: everything in the
    stable prefix is identical across the stages of a ticket, so consecutive stage
    sessions hit the cache on it. Only :attr:`stage_tail` varies per stage.

    ``appendix`` exists for exactly one purpose: the runner's single retry after a
    required artifact fails validation appends a nudge without rebuilding the pack.
    """

    system_prompt: str
    """Stage-role system prompt. Passed as the session system prompt, not as user text."""

    plan_summary: str = ""
    """Plan/ADR summary, re-injected every stage (the plan-reminder effect)."""

    context_pack: str = ""
    """Relevant-file list + repo-map slice + acceptance criteria."""

    stage_tail: str = ""
    """Resolved references to prior artifacts — slices, never whole documents."""

    appendix: str = ""
    """Runner-appended nudge text (missing-artifact retry)."""

    @property
    def stable_prefix(self) -> str:
        """The cache-stable portion of the user-visible prompt."""
        return _join_sections(self.plan_summary, self.context_pack)

    @property
    def prompt(self) -> str:
        """The full user prompt handed to the session."""
        return _join_sections(self.stable_prefix, self.stage_tail, self.appendix)

    @property
    def size_chars(self) -> int:
        """Characters in system prompt + full prompt. The measured size in tests."""
        return len(self.system_prompt) + len(self.prompt)

    @property
    def approx_tokens(self) -> int:
        """Coarse token estimate for budget assertions. Not a billing figure."""
        return self.size_chars // _CHARS_PER_TOKEN

    def with_appendix(self, text: str) -> PromptPack:
        """Return a copy with ``text`` appended to the appendix."""
        return replace(self, appendix=_join_sections(self.appendix, text))


def _join_sections(*parts: str) -> str:
    return "\n\n".join(p.strip() for p in parts if p.strip())


@dataclass(frozen=True, slots=True)
class ExecConfig:
    """Per-call execution policy. Model and effort are always explicit (ADR 0007).

    Caps are expressed in turns and tokens because flux runs on a subscription
    (ADR 0010); ``max_budget_usd`` is only meaningful once API fallback is active,
    and validation enforces that.
    """

    model: str
    effort: EffortLevel
    permission_mode: PermissionMode = "default"
    allowed_tools: tuple[str, ...] = ()
    disallowed_tools: tuple[str, ...] = ()
    max_turns: int = 40
    max_tokens: int = 200_000
    """flux's own token budget for the call, measured in *uncached* tokens
    (:attr:`Usage.budget_tokens`) — cache reads do not count against it. Enforced by
    the runner and recorded in metrics; see :attr:`advertise_token_budget` for the
    API-side variant."""

    advertise_token_budget: bool = False
    """Send :attr:`max_tokens` to the model as an API task budget.

    Off by default because it is model-gated: models without support reject the
    request with ``400 This model does not support user-configurable task budgets``
    (observed on Haiku 4.5, 2026-08-18). Turn it on per stage only for models known
    to accept it; ``max_turns`` is the cap that always applies.
    """

    max_budget_usd: float | None = None
    billing_mode: BillingMode = "subscription"
    setting_sources: tuple[SettingSource, ...] = ("project",)
    cwd: Path | None = None
    hooks: Mapping[str, Sequence[Any]] = NO_HOOKS
    """Opaque SDK hook config, forwarded verbatim by ``sdk.py``.

    Left untyped on purpose: the typed hook model (PreToolUse test-edit blocks and
    friends) lands with the stages that need it, and typing it here would drag SDK
    types across the seam that ADR 0007 exists to keep clean.
    """

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise ConfigError("ExecConfig.model must be a non-empty model id")
        if self.effort not in EFFORT_LEVELS:
            raise ConfigError(
                f"ExecConfig.effort {self.effort!r} not one of {sorted(EFFORT_LEVELS)}"
            )
        if self.permission_mode not in PERMISSION_MODES:
            raise ConfigError(
                f"ExecConfig.permission_mode {self.permission_mode!r} not one of "
                f"{sorted(PERMISSION_MODES)}"
            )
        if self.billing_mode not in BILLING_MODES:
            raise ConfigError(
                f"ExecConfig.billing_mode {self.billing_mode!r} not one of {sorted(BILLING_MODES)}"
            )
        unknown = set(self.setting_sources) - SETTING_SOURCES
        if unknown:
            raise ConfigError(f"ExecConfig.setting_sources has unknown entries: {sorted(unknown)}")
        if self.max_turns <= 0:
            raise ConfigError(f"ExecConfig.max_turns must be positive, got {self.max_turns}")
        if self.max_tokens <= 0:
            raise ConfigError(f"ExecConfig.max_tokens must be positive, got {self.max_tokens}")
        if self.max_budget_usd is not None:
            if self.billing_mode != "api-fallback":
                raise ConfigError(
                    "ExecConfig.max_budget_usd is only meaningful under api-fallback billing "
                    "(ADR 0010); on a subscription cap with max_turns/max_tokens instead"
                )
            if self.max_budget_usd <= 0:
                raise ConfigError(
                    f"ExecConfig.max_budget_usd must be positive, got {self.max_budget_usd}"
                )
        if self.cwd is not None and not self.cwd.is_absolute():
            raise ConfigError(f"ExecConfig.cwd must be an absolute path, got {self.cwd}")


@dataclass(frozen=True, slots=True)
class Usage:
    """Token accounting for one session. The primary economics on a subscription."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0

    @property
    def billable_input_tokens(self) -> int:
        """Uncached input: what actually consumed fresh window capacity."""
        return self.input_tokens + self.cache_creation_tokens

    @property
    def budget_tokens(self) -> int:
        """What a session actually consumed: uncached input, cache writes, and output.

        Cache *reads* are excluded on purpose. A cached prefix is re-read on every
        turn, so a 30-turn session over a 30k-token prefix reports ~900k cache reads
        while consuming almost nothing — budgeting on :attr:`total_tokens` would
        therefore cap how many *turns* a stage may take rather than how much work it
        may do, and would punish the prompt caching flux is structured to get.
        """
        return self.billable_input_tokens + self.output_tokens

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_tokens
            + self.cache_creation_tokens
        )

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens,
            cache_creation_tokens=self.cache_creation_tokens + other.cache_creation_tokens,
        )


_EMPTY_USAGE = Usage()


@dataclass(frozen=True, slots=True)
class WindowPressure:
    """Subscription usage-window state, from the CLI's rate-limit events (ADR 0010).

    ``utilization`` is the fraction of the window consumed (0.0–1.0). ``rejected``
    means the limit was hit — the runner parks and resumes at ``resets_at``.
    """

    status: str
    window: str | None = None
    utilization: float | None = None
    resets_at: int | None = None

    @property
    def limit_hit(self) -> bool:
        return self.status == "rejected"


# Tools whose use signals the session went looking for context it was not given.
# The M4 refinement narrows this to reads *outside* the context pack; until packs
# exist, the raw count is the honest proxy.
EXPLORATORY_TOOLS: frozenset[str] = frozenset({"Read", "Grep", "Glob"})


@dataclass(frozen=True, slots=True)
class ExecResult:
    """Everything the runner and metrics need from one session."""

    ok: bool
    text: str
    session_id: str
    model: str
    effort: EffortLevel
    billing_mode: BillingMode
    usage: Usage = _EMPTY_USAGE
    total_cost_usd: float | None = None
    num_turns: int = 0
    duration_ms: int = 0
    duration_api_ms: int = 0
    subtype: str = ""
    stop_reason: str | None = None
    provider: str | None = None
    """API provider the CLI actually billed, as reported per model (e.g. ``firstParty``).

    Observed, not configured: it is how a silent billing-surface change would show up
    in the metrics history rather than only in a preflight that ran hours earlier.
    """

    tool_uses: Mapping[str, int] = _NO_TOOL_USES
    window: WindowPressure | None = None
    pack_chars: int = 0
    error: str | None = None

    @property
    def exploratory_calls(self) -> int:
        """Read/Grep/Glob calls — the cold-exploration KPI (plan.md M4 exit)."""
        return sum(n for tool, n in self.tool_uses.items() if tool in EXPLORATORY_TOOLS)
