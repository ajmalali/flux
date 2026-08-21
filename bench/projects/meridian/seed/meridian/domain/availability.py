"""When a space is free.

Pure: it is handed the bookings it should consider and returns intervals. It
does not know where bookings come from and never reads a clock.
"""

from .intervals import Interval, subtract
from .models import CONFIRMED


def busy_intervals(bookings):
    """The intervals actually occupied — cancelled bookings occupy nothing."""
    return [b.interval for b in bookings if b.status == CONFIRMED]


def free_slots(space, bookings, day):
    """Open windows in ``space`` on ``day`` once ``bookings`` are removed."""
    window = space.opening_window(day)
    busy = [i for i in (b.clamp(window) for b in busy_intervals(bookings)) if i]
    return subtract(window, busy)


def is_free(space, bookings, interval):
    """True when ``interval`` fits entirely inside a single free slot."""
    for slot in free_slots(space, bookings, interval.start):
        if slot.start <= interval.start and interval.end <= slot.end:
            return True
    return False


def within_opening_hours(space, interval):
    window = space.opening_window(interval.start)
    return window.start <= interval.start and interval.end <= window.end


__all__ = ["busy_intervals", "free_slots", "is_free", "within_opening_hours", "Interval"]
