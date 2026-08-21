import unittest
from datetime import timedelta

from meridian.clock import utc
from meridian.service.reporting import utilization
from tests.fixtures import temp_service


class ReportingTests(unittest.TestCase):
    def setUp(self):
        self.service = temp_service(self)

    def book(self, hour, hours):
        start = utc(2026, 9, 1, hour)
        return self.service.create_booking("s-focus", "m-ada", start, start + timedelta(hours=hours))

    def test_empty_day_is_zero(self):
        self.assertEqual(utilization(self.service.repos, "s-focus", utc(2026, 9, 1)), 0.0)

    def test_half_the_day(self):
        self.book(8, 6)
        self.assertEqual(utilization(self.service.repos, "s-focus", utc(2026, 9, 1)), 50.0)

    def test_two_bookings_add_up(self):
        self.book(8, 3)
        self.book(14, 3)
        self.assertEqual(utilization(self.service.repos, "s-focus", utc(2026, 9, 1)), 50.0)

    def test_other_days_are_excluded(self):
        start = utc(2026, 9, 2, 8)
        self.service.create_booking("s-focus", "m-ada", start, start + timedelta(hours=6))
        self.assertEqual(utilization(self.service.repos, "s-focus", utc(2026, 9, 1)), 0.0)
