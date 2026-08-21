import unittest
from datetime import timedelta

from meridian.clock import utc
from meridian.errors import NotFound, OutsideOpeningHours, ValidationError
from tests.fixtures import temp_service


class BookingServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = temp_service(self)

    def book(self, hour=10, hours=2, space="s-focus", member="m-ada"):
        start = utc(2026, 9, 1, hour)
        return self.service.create_booking(space, member, start, start + timedelta(hours=hours))

    def test_creates_a_priced_booking(self):
        booking = self.book()
        self.assertEqual(booking.price_cents, 2400)
        self.assertEqual(booking.status, "confirmed")
        self.assertEqual(booking.created_at, utc(2026, 9, 1, 7))

    def test_unknown_space_is_not_found(self):
        with self.assertRaises(NotFound):
            self.book(space="s-nope")

    def test_outside_opening_hours_is_rejected(self):
        with self.assertRaises(OutsideOpeningHours):
            self.book(hour=19, hours=3)

    def test_backwards_interval_is_a_validation_error(self):
        start = utc(2026, 9, 1, 12)
        with self.assertRaises(ValidationError):
            self.service.create_booking("s-focus", "m-ada", start, start - timedelta(hours=1))

    def test_cancel_marks_the_booking(self):
        booking = self.book()
        self.assertEqual(self.service.cancel_booking(booking.id).status, "cancelled")

    def test_cancelling_twice_is_rejected(self):
        booking = self.book()
        self.service.cancel_booking(booking.id)
        with self.assertRaises(ValidationError):
            self.service.cancel_booking(booking.id)

    def test_reschedule_reprices(self):
        booking = self.book(hours=2)
        moved = self.service.reschedule_booking(
            booking.id, utc(2026, 9, 1, 14), utc(2026, 9, 1, 15))
        self.assertEqual(moved.price_cents, 1200)
        self.assertEqual(moved.id, booking.id)

    def test_bookings_persist(self):
        booking = self.book()
        self.assertEqual(self.service.bookings_for_space("s-focus")[0].id, booking.id)
