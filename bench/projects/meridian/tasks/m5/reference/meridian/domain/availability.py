"""When a space is free.

Pure: it is handed the bookings it should consider and returns intervals. It
does not know where bookings come from and never reads a clock.

A confirmed booking occupies its own interval *and* the space's changeover
buffer that follows it. That single definition -- :func:`occupied_interval` --
is what every other rule here is built from, so the buffer cannot be applied in
one place and forgotten in another.
"""

from datetime import timedelta

from .intervals import Interval, overlaps, subtract
from .models import CONFIRMED, HOLD


def occupied_interval(space, booking):
    """What ``booking`` takes out of ``space``: its interval plus the buffer."""
    return Interval(booking.start, booking.end + timedelta(minutes=space.buffer_minutes))


def claimed_interval(space, booking, now=None):
    """What ``booking`` takes out of ``space`` as of ``now``, or ``None``.

    Two kinds of record claim a slot, and they claim different things: a
    confirmed booking takes its interval plus the changeover buffer, a live hold
    takes exactly its own interval and no buffer -- nobody is changing over from
    a room that was never occupied. ``now`` decides whether a hold is still live;
    without one every hold counts as live, which is the safe reading for a caller
    that has no clock.
    """
    if booking.status == CONFIRMED:
        return occupied_interval(space, booking)
    if booking.status == HOLD and (now is None or booking.is_live_hold(now)):
        return Interval(booking.start, booking.end)
    return None


def busy_intervals(space, bookings, now=None):
    """The intervals actually claimed -- cancelled records claim nothing."""
    claimed = (claimed_interval(space, b, now) for b in bookings)
    return [i for i in claimed if i is not None]


def free_slots(space, bookings, day, now=None):
    """Open windows in ``space`` on ``day`` once ``bookings`` are removed."""
    window = space.opening_window(day)
    busy = [i for i in (b.clamp(window) for b in busy_intervals(space, bookings, now)) if i]
    return subtract(window, busy)


def is_free(space, bookings, interval, now=None):
    """True when ``interval`` fits entirely inside a single free slot."""
    for slot in free_slots(space, bookings, interval.start, now):
        if slot.start <= interval.start and interval.end <= slot.end:
            return True
    return False


def collides(space, interval, booking, now=None):
    """True when ``interval`` cannot coexist with ``booking`` in ``space``.

    Both sides carry the buffer, which is what makes the rule order-independent:
    a new booking placed *before* an existing one is rejected by the new
    booking's own changeover time, exactly as it would be the other way round.
    """
    if booking.status == HOLD:
        # A hold claims its own slot only; the buffer belongs to real occupancy.
        if now is not None and not booking.is_live_hold(now):
            return False
        return overlaps(interval.start, interval.end, booking.start, booking.end)
    if booking.status != CONFIRMED:
        return False
    buffer_ = timedelta(minutes=space.buffer_minutes)
    return overlaps(interval.start, interval.end + buffer_,
                    booking.start, booking.end + buffer_)


def find_conflict(space, bookings, interval, ignore_id=None, now=None):
    """The first booking ``interval`` collides with, or ``None``."""
    for booking in bookings:
        if ignore_id is not None and booking.id == ignore_id:
            continue
        if collides(space, interval, booking, now):
            return booking
    return None


def within_opening_hours(space, interval):
    window = space.opening_window(interval.start)
    return window.start <= interval.start and interval.end <= window.end


__all__ = ["occupied_interval", "claimed_interval", "busy_intervals", "free_slots", "is_free",
           "collides", "find_conflict", "within_opening_hours", "Interval"]
