"""The entities. Data and the rules that need nothing but that data."""

from dataclasses import dataclass, field, replace
from datetime import datetime

CONFIRMED = "confirmed"
CANCELLED = "cancelled"
HOLD = "hold"
STATUSES = (CONFIRMED, CANCELLED, HOLD)

PLAN_BASIC = "basic"
PLAN_PRO = "pro"
PLANS = (PLAN_BASIC, PLAN_PRO)


@dataclass(frozen=True)
class Space(object):
    id: str
    name: str
    capacity: int
    hourly_cents: int
    open_hour: int = 8
    close_hour: int = 20
    buffer_minutes: int = 0
    """Changeover time a space needs after a booking before it can be reoccupied."""

    def opening_window(self, day):
        """The ``[open, close)`` window on the UTC date of ``day``."""
        from .intervals import Interval

        start = day.replace(hour=self.open_hour, minute=0, second=0, microsecond=0)
        end = day.replace(hour=self.close_hour, minute=0, second=0, microsecond=0)
        return Interval(start, end)


@dataclass(frozen=True)
class Member(object):
    id: str
    name: str
    email: str
    plan: str = PLAN_BASIC

    def __post_init__(self):
        if self.plan not in PLANS:
            raise ValueError("unknown plan: %r" % (self.plan,))


@dataclass(frozen=True)
class Booking(object):
    id: str
    space_id: str
    member_id: str
    start: datetime
    end: datetime
    price_cents: int
    created_at: datetime
    status: str = CONFIRMED
    refund_cents: int = 0
    """Refunded on cancellation; always 0 while the booking is confirmed."""
    series_id: str = ""
    """Shared by every occurrence of a recurring series; empty for one-offs."""
    expires_at: datetime = None
    """When a hold stops claiming its slot. ``None`` for anything that is not a hold."""

    @property
    def interval(self):
        from .intervals import Interval

        return Interval(self.start, self.end)

    @property
    def is_active(self):
        return self.status == CONFIRMED

    @property
    def is_hold(self):
        return self.status == HOLD

    def is_live_hold(self, now):
        """True while this hold still claims its slot.

        Half-open like every interval here: at exactly ``expires_at`` it is over.
        The moment is an argument because ``domain`` never reads a clock.
        """
        if not self.is_hold or self.expires_at is None:
            return False
        return now < self.expires_at

    def cancelled(self, refund_cents=0):
        return replace(self, status=CANCELLED, refund_cents=refund_cents)
