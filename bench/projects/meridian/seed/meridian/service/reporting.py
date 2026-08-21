"""How well a space is used.

Utilisation is booked minutes over open minutes for a single day, as a
percentage rounded to one decimal place.
"""

from ..domain.intervals import Interval


def utilization(repos, space_id, day):
    """Percentage of ``space_id``'s opening hours booked on ``day``."""
    space = repos.spaces.get(space_id)
    window = space.opening_window(day)
    booked = 0
    for booking in repos.bookings.for_space(space_id):
        clamped = Interval(booking.start, booking.end).clamp(window)
        if clamped is not None:
            booked += clamped.minutes
    if window.minutes == 0:
        return 0.0
    return round(100.0 * booked / window.minutes, 1)
