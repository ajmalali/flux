"""Time, injected rather than read.

Nothing in Meridian calls ``datetime.now()``. Every component that needs the
current time takes a clock, so tests pin it and behaviour is reproducible.
"""

from datetime import datetime, timezone


class Clock(object):
    """The real clock."""

    def now(self):
        return datetime.now(timezone.utc)


class FixedClock(Clock):
    """A clock that does not move. For tests."""

    def __init__(self, moment):
        self._moment = moment

    def now(self):
        return self._moment

    def advance(self, delta):
        self._moment = self._moment + delta
        return self._moment


def utc(year, month, day, hour=0, minute=0):
    """Build a timezone-aware UTC datetime without the ceremony."""
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
