"""Exception hierarchy shared across gus.

Two families matter to the runner:

* :class:`GusError` — a bug or a misuse of gus itself (bad config, bad call order).
  These should surface as a stack trace during development.
* :class:`ParkSignal` — the ticket cannot proceed and a human must look at it.
  The runner catches these, writes a park note, and stops. Never a stack trace.
"""

from __future__ import annotations


class GusError(Exception):
    """Base class for all gus errors."""


class ConfigError(GusError):
    """An :class:`~gus.executor.types.ExecConfig` or gus.toml value is invalid."""


class ParkSignal(GusError):
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

    ADR 0010: gus never silently switches to API billing. Detect and park.
    """
