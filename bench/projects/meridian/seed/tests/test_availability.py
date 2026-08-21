import unittest
from datetime import timedelta

from meridian.clock import utc
from meridian.domain.availability import free_slots, is_free, within_opening_hours
from meridian.domain.intervals import Interval
from meridian.domain.models import Booking
from tests.fixtures import FOCUS


def booking(start_hour, hours, status="confirmed"):
    start = utc(2026, 9, 1, start_hour)
    return Booking(id="b", space_id="s-focus", member_id="m", start=start,
                   end=start + timedelta(hours=hours), price_cents=0,
                   created_at=utc(2026, 9, 1, 7), status=status)


class AvailabilityTests(unittest.TestCase):
    def test_empty_day_is_one_slot(self):
        slots = free_slots(FOCUS, [], utc(2026, 9, 1))
        self.assertEqual(len(slots), 1)
        self.assertEqual((slots[0].start.hour, slots[0].end.hour), (8, 20))

    def test_a_booking_splits_the_day(self):
        slots = free_slots(FOCUS, [booking(10, 2)], utc(2026, 9, 1))
        self.assertEqual([(s.start.hour, s.end.hour) for s in slots], [(8, 10), (12, 20)])

    def test_cancelled_bookings_free_the_room(self):
        slots = free_slots(FOCUS, [booking(10, 2, status="cancelled")], utc(2026, 9, 1))
        self.assertEqual(len(slots), 1)

    def test_is_free_respects_existing_bookings(self):
        taken = [booking(10, 2)]
        self.assertFalse(is_free(FOCUS, taken, Interval(utc(2026, 9, 1, 11), utc(2026, 9, 1, 12))))
        self.assertTrue(is_free(FOCUS, taken, Interval(utc(2026, 9, 1, 12), utc(2026, 9, 1, 13))))

    def test_opening_hours(self):
        self.assertTrue(within_opening_hours(FOCUS, Interval(utc(2026, 9, 1, 8), utc(2026, 9, 1, 20))))
        self.assertFalse(within_opening_hours(FOCUS, Interval(utc(2026, 9, 1, 7), utc(2026, 9, 1, 9))))
