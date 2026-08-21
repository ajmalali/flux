"""How well a space is used.

Utilisation is the time a space was *occupied* over its opening hours for a
single day, as a percentage rounded to one decimal place.

Two things it deliberately is not:

* it does not count cancelled bookings -- a cancelled booking occupied nothing,
  and counting them was the bug operations reported;
* it does not count the changeover buffer -- that makes a space *unavailable*,
  which is a different question from whether it was *used*.
"""

from ..domain.intervals import Interval
from ..domain.models import CONFIRMED


def _occupied_minutes(bookings, window):
    minutes = 0
    for booking in bookings:
        if booking.status != CONFIRMED:
            continue
        clamped = Interval(booking.start, booking.end).clamp(window)
        if clamped is not None:
            minutes += clamped.minutes
    return minutes


def _percent(minutes, window):
    if window.minutes == 0:
        return 0.0
    return round(100.0 * minutes / window.minutes, 1)


def utilization(repos, space_id, day):
    """Percentage of ``space_id``'s opening hours occupied on ``day``."""
    space = repos.spaces.get(space_id)
    window = space.opening_window(day)
    return _percent(_occupied_minutes(repos.bookings.for_space(space_id), window), window)


def utilization_by_space(repos, day):
    """``{space_id: percent}`` for every space, including the unused ones."""
    report = {}
    for space in repos.spaces.all():
        window = space.opening_window(day)
        report[space.id] = _percent(
            _occupied_minutes(repos.bookings.for_space(space.id), window), window)
    return report
