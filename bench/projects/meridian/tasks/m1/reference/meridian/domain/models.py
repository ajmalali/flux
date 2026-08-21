"""The entities. Data and the rules that need nothing but that data."""

from dataclasses import dataclass, field, replace
from datetime import datetime

CONFIRMED = "confirmed"
CANCELLED = "cancelled"
STATUSES = (CONFIRMED, CANCELLED)

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

    @property
    def interval(self):
        from .intervals import Interval

        return Interval(self.start, self.end)

    @property
    def is_active(self):
        return self.status == CONFIRMED

    def cancelled(self):
        return replace(self, status=CANCELLED)
