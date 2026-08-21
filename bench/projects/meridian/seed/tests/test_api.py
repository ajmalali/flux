import unittest
from datetime import timedelta

from meridian.api.handlers import build_router
from meridian.clock import utc
from tests.fixtures import temp_service


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.service = temp_service(self)
        self.router = build_router(self.service)

    def book(self, hour=10, hours=2):
        start = utc(2026, 9, 1, hour)
        return self.service.create_booking("s-focus", "m-ada", start, start + timedelta(hours=hours))

    def test_lists_spaces(self):
        response = self.router.dispatch("GET", "/spaces")
        self.assertEqual(response.status, 200)
        self.assertEqual(len(response.body["spaces"]), 2)

    def test_unknown_path_is_404(self):
        self.assertEqual(self.router.dispatch("GET", "/nope").status, 404)

    def test_known_path_wrong_method_is_405(self):
        self.assertEqual(self.router.dispatch("POST", "/spaces").status, 405)

    def test_gets_a_booking(self):
        booking = self.book()
        response = self.router.dispatch("GET", "/bookings/%s" % booking.id)
        self.assertEqual(response.status, 200)
        self.assertEqual(response.body["price_cents"], 2400)

    def test_missing_booking_is_404(self):
        self.assertEqual(self.router.dispatch("GET", "/bookings/b-999").status, 404)

    def test_cancel_endpoint(self):
        booking = self.book()
        response = self.router.dispatch("POST", "/bookings/%s/cancel" % booking.id)
        self.assertEqual(response.status, 200)
        self.assertEqual(response.body["status"], "cancelled")

    def test_cancelling_twice_is_409(self):
        booking = self.book()
        self.router.dispatch("POST", "/bookings/%s/cancel" % booking.id)
        self.assertEqual(self.router.dispatch("POST", "/bookings/%s/cancel" % booking.id).status, 409)
