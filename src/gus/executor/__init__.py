"""The executor seam: the only place gus talks to a model (ADR 0007)."""

from gus.executor.billing import (
    API_CREDENTIAL_VARS,
    BILLING_REDIRECT_VARS,
    AuthStatus,
    child_env_from,
    detect_billing_redirects,
    preflight,
    sanitize_process_env,
)
from gus.executor.protocol import Executor
from gus.executor.sdk import ClaudeAgentSDKExecutor, build_options
from gus.executor.stub import StubExecutor, ok_result
from gus.executor.types import (
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
