"""Exception hierarchy shared across flux.

Two families matter to the runner:

* :class:`FluxError` — a bug or a misuse of flux itself (bad config, bad call order).
  These should surface as a stack trace during development.
* :class:`ParkSignal` — the ticket cannot proceed and a human must look at it.
  The runner catches these, writes a park note, and stops. Never a stack trace.
"""

from __future__ import annotations


class FluxError(Exception):
    """Base class for all flux errors."""


class ConfigError(FluxError):
    """An :class:`~flux.executor.types.ExecConfig` or flux.toml value is invalid."""


class ParkSignal(FluxError):
    """Raised when work must stop and wait for a human.

    Args:
        note: Human-readable reason, written verbatim into the park note.
        reason: Short machine-readable slug for metrics/triage grouping.
    """

    def __init__(self, note: str, *, reason: str = "unspecified") -> None:
        super().__init__(note)
        self.note = note
        self.reason = reason


class BillingPolicyError(ParkSignal):
    """Preflight found an execution environment that would not bill to the subscription.

    ADR 0010: flux never silently switches to API billing. Detect and park.
    """
