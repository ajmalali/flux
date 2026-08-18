"""The executor seam: the only place flux talks to a model (ADR 0007)."""

from flux.executor.billing import (
    API_CREDENTIAL_VARS,
    BILLING_REDIRECT_VARS,
    AuthStatus,
    child_env_from,
    detect_billing_redirects,
    preflight,
    sanitize_process_env,
)
from flux.executor.protocol import Executor
from flux.executor.sdk import ClaudeAgentSDKExecutor, build_options
from flux.executor.stub import StubExecutor, ok_result
from flux.executor.types import (
    BillingMode,
    EffortLevel,
    ExecConfig,
    ExecResult,
    PermissionMode,
    PromptPack,
    SettingSource,
    Usage,
    WindowPressure,
)

__all__ = [
    "API_CREDENTIAL_VARS",
    "BILLING_REDIRECT_VARS",
    "AuthStatus",
    "BillingMode",
    "ClaudeAgentSDKExecutor",
    "EffortLevel",
    "ExecConfig",
    "ExecResult",
    "Executor",
    "PermissionMode",
    "PromptPack",
    "SettingSource",
    "StubExecutor",
    "Usage",
    "WindowPressure",
    "build_options",
    "child_env_from",
    "detect_billing_redirects",
    "ok_result",
    "preflight",
    "sanitize_process_env",
]
