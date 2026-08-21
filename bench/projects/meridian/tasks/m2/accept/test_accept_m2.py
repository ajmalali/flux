"""Held-out acceptance tests for m2."""

import shutil
import tempfile
import unittest
from datetime import timedelta

from meridian.clock import FixedClock, utc
from meridian.domain.models import Member, Space
from meridian.errors import ValidationError
from meridian.service.booking import BookingService
from meridian.store.jsonstore import JsonStore
from meridian.store.repositories import Repositories

START = utc(2026, 9, 10, 10)


def build(testcase, now):
    tmpdir = tempfile.mkdtemp(prefix="m2-accept-")
    testcase.addCleanup(shutil.rmtree, tmpdir, True)
    repos = Repositories(JsonStore(tmpdir + "/data.json"))
    repos.spaces.add(Space(id="s-focus", name="Focus", capacity=4, hourly_cents=1200))
    repos.members.add(Member(id="m-ada", name="Ada", email="ada@example.com"))
    repos.commit()
    return BookingService(repos, FixedClock(now)), tmpdir


class PolicyModuleTests(unittest.TestCase):
    def test_policy_module_exists_and_is_pure(self):
        import meridian.domain.policy as policy

        with open(policy.__file__, encoding="utf-8") as fh:
            source = fh.read()
        self.assertNotIn("datetime.now(", source, "domain code must not read a clock")
        self.assertNotIn("open(", source, "domain code must not do I/O")


class TierTests(unittest.TestCase):
    def cancel_with_gap(self, gap, price_hours=2):
        service, _ = build(self, START - gap)
        booking = service.create_booking("s-focus", "m-ada", START,
                                         START + timedelta(hours=price_hours))
        return service.cancel_booking(booking.id), booking

    def test_confirmed_bookings_carry_no_refund(self):
        service, _ = build(self, START - timedelta(days=7))
        booking = service.create_booking("s-focus", "m-ada", START, START + timedelta(hours=2))
        self.assertEqual(booking.refund_cents, 0)

    def test_full_refund_well_ahead(self):
        cancelled, booking = self.cancel_with_gap(timedelta(days=7))
        self.assertEqual(cancelled.refund_cents, booking.price_cents)

    def test_exactly_48_hours_is_a_full_refund(self):
        cancelled, booking = self.cancel_with_gap(timedelta(hours=48))
        self.assertEqual(cancelled.refund_cents, booking.price_cents)

    def test_just_under_48_hours_is_half(self):
        cancelled, booking = self.cancel_with_gap(timedelta(hours=47, minutes=59))
        self.assertEqual(cancelled.refund_cents, booking.price_cents // 2)

    def test_exactly_24_hours_is_half(self):
        cancelled, booking = self.cancel_with_gap(timedelta(hours=24))
        self.assertEqual(cancelled.refund_cents, booking.price_cents // 2)

    def test_just_under_24_hours_is_a_quarter(self):
        cancelled, booking = self.cancel_with_gap(timedelta(hours=23, minutes=59))
        self.assertEqual(cancelled.refund_cents, booking.price_cents // 4)

    def test_exactly_2_hours_is_a_quarter(self):
        cancelled, booking = self.cancel_with_gap(timedelta(hours=2))
        self.assertEqual(cancelled.refund_cents, booking.price_cents // 4)

    def test_just_under_2_hours_is_nothing(self):
        cancelled, _ = self.cancel_with_gap(timedelta(hours=1, minutes=59))
        self.assertEqual(cancelled.refund_cents, 0)

    def test_after_the_start_is_nothing(self):
        cancelled, _ = self.cancel_with_gap(timedelta(hours=-3))
        self.assertEqual(cancelled.refund_cents, 0)


class RoundingTests(unittest.TestCase):
    def test_quarter_refund_rounds_half_up(self):
        from meridian.domain.policy import refund_cents

        self.assertEqual(refund_cents(2162, timedelta(hours=3)), 541)   # 540.5 -> 541
        self.assertEqual(refund_cents(2161, timedelta(hours=3)), 540)   # 540.25 -> 540

    def test_half_refund_rounds_half_up(self):
        from meridian.domain.policy import refund_cents

        self.assertEqual(refund_cents(2161, timedelta(hours=30)), 1081)  # 1080.5 -> 1081

    def test_zero_price_refunds_zero(self):
        from meridian.domain.policy import refund_cents

        self.assertEqual(refund_cents(0, timedelta(days=30)), 0)


class PersistenceAndApiTests(unittest.TestCase):
    def test_refund_round_trips_through_the_store(self):
        service, tmpdir = build(self, START - timedelta(days=1))
        booking = service.create_booking("s-focus", "m-ada", START, START + timedelta(hours=2))
        service.cancel_booking(booking.id)
        reloaded = Repositories(JsonStore(tmpdir + "/data.json")).bookings.get(booking.id)
        self.assertEqual(reloaded.refund_cents, booking.price_cents // 2)
        self.assertEqual(reloaded.status, "cancelled")

    def test_cancel_endpoint_reports_the_refund(self):
        from meridian.api.handlers import build_router

        service, _ = build(self, START - timedelta(days=7))
        booking = service.create_booking("s-focus", "m-ada", START, START + timedelta(hours=2))
        response = build_router(service).dispatch("POST", "/bookings/%s/cancel" % booking.id)
        self.assertEqual(response.status, 200)
        self.assertEqual(response.body["refund_cents"], booking.price_cents)

    def test_double_cancel_is_still_rejected(self):
        service, _ = build(self, START - timedelta(days=7))
        booking = service.create_booking("s-focus", "m-ada", START, START + timedelta(hours=2))
        service.cancel_booking(booking.id)
        with self.assertRaises(ValidationError):
            service.cancel_booking(booking.id)


if __name__ == "__main__":
    unittest.main()
