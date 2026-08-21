"""Half-open time intervals: ``[start, end)``.

Half-open is the whole point. A booking that ends at 10:00 and one that starts
at 10:00 do not overlap, and every rule in Meridian depends on that being true
in exactly one place.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Interval(object):
    start: datetime
    end: datetime

    def __post_init__(self):
        if self.end <= self.start:
            raise ValueError("interval must end after it starts")

    @property
    def minutes(self):
        return int((self.end - self.start).total_seconds() // 60)

    def contains(self, moment):
        return self.start <= moment < self.end

    def overlaps(self, other):
        return overlaps(self.start, self.end, other.start, other.end)

    def clamp(self, window):
        """This interval restricted to ``window``, or ``None`` if they miss."""
        start = max(self.start, window.start)
        end = min(self.end, window.end)
        return Interval(start, end) if start < end else None


def overlaps(a_start, a_end, b_start, b_end):
    """True when ``[a_start, a_end)`` and ``[b_start, b_end)`` share any instant."""
    return a_start < b_end and b_start < a_end


def merge(intervals):
    """Sorted, non-overlapping cover of ``intervals``. Touching intervals join."""
    ordered = sorted(intervals, key=lambda i: i.start)
    merged = []
    for interval in ordered:
        if merged and interval.start <= merged[-1].end:
            last = merged.pop()
            merged.append(Interval(last.start, max(last.end, interval.end)))
        else:
            merged.append(interval)
    return merged


def subtract(window, busy):
    """``window`` minus every interval in ``busy``, as a sorted list."""
    free = [window]
    for taken in merge(busy):
        remaining = []
        for slot in free:
            if not slot.overlaps(taken):
                remaining.append(slot)
                continue
            if slot.start < taken.start:
                remaining.append(Interval(slot.start, taken.start))
            if taken.end < slot.end:
                remaining.append(Interval(taken.end, slot.end))
        free = remaining
    return free
