"""Held-out acceptance tests for m5. Never present in an arm's worktree.

Written to be blind to whether m1-m4 are in the tree: no test here creates two
overlapping *confirmed* bookings, sets a changeover buffer, or asserts anything
about how cancelled bookings are reported. What it pins is holds.
"""

import shutil
import tempfile
import unittest
from datetime import timedelta

from meridian.api.handlers import build_router
from meridian.clock import FixedClock, utc
from meridian.domain.intervals import Interval
from meridian.domain.availability import free_slots, is_free
from meridian.domain.models import CANCELLED, CONFIRMED, HOLD, STATUSES, Booking, Member, Space
from meridian.domain.pricing import quote
from meridian.errors import ConflictError, NotFound, OutsideOpeningHours, ValidationError
from meridian.service.booking import BookingService
from meridian.service import reporting
from meridian.store.jsonstore import JsonStore
from meridian.store.repositories import Repositories

FOCUS = Space(id="s-focus", name="Focus Room", capacity=4, hourly_cents=1200)
STUDIO = Space(id="s-studio", name="Studio", capacity=12, hourly_cents=3000,
               open_hour=9, close_hour=18)
ADA = Member(id="m-ada", name="Ada", email="ada@example.com")
NOW = utc(2026, 9, 1, 7, 0)


def at(hour, minute=0):
    return utc(2026, 9, 1, hour, minute)


def fresh(testcase):
    """A service on a real JSON file, so the store is exercised like production."""
    tmpdir = tempfile.mkdtemp(prefix="m5-accept-")
    testcase.addCleanup(shutil.rmtree, tmpdir, True)
    path = tmpdir + "/data.json"
    repos = Repositories(JsonStore(path))
    for space in (FOCUS, STUDIO):
        repos.spaces.add(space)
    repos.members.add(ADA)
    repos.commit()
    clock = FixedClock(NOW)
    return BookingService(repos, clock), clock, path


class HoldModelTests(unittest.TestCase):
    def test_hold_is_a_status(self):
        self.assertEqual(HOLD, "hold")
        self.assertIn(HOLD, STATUSES)

    def test_expires_at_defaults_to_none_and_confirmed_is_not_a_hold(self):
        booking = Booking(id="b-1", space_id="s", member_id="m", start=at(10), end=at(11),
                          price_cents=100, created_at=NOW)
        self.assertIsNone(booking.expires_at)
        self.assertFalse(booking.is_hold)

    def test_a_live_hold_stops_being_live_at_its_expiry(self):
        service, clock, _ = fresh(self)
        hold = service.hold_space("s-focus", "m-ada", at(10), at(12), minutes=15)
        self.assertTrue(hold.is_hold)
        self.assertTrue(hold.is_live_hold(NOW))
        self.assertTrue(hold.is_live_hold(NOW + timedelta(minutes=14, seconds=59)))
        # Half-open, like every other interval in this codebase.
        self.assertFalse(hold.is_live_hold(NOW + timedelta(minutes=15)))
        self.assertFalse(hold.is_live_hold(NOW + timedelta(minutes=16)))

    def test_a_hold_is_not_an_active_booking(self):
        service, _, _ = fresh(self)
        hold = service.hold_space("s-focus", "m-ada", at(10), at(12))
        self.assertFalse(hold.is_active)


class HoldCreationTests(unittest.TestCase):
    def test_a_hold_is_recorded_with_status_expiry_and_the_quoted_price(self):
        service, _, _ = fresh(self)
        hold = service.hold_space("s-focus", "m-ada", at(10), at(12))
        self.assertEqual(hold.status, HOLD)
        self.assertEqual(hold.expires_at, NOW + timedelta(minutes=15))
        self.assertEqual(hold.created_at, NOW)
        self.assertEqual(hold.price_cents, quote(FOCUS, ADA, Interval(at(10), at(12))))

    def test_the_hold_window_is_configurable(self):
        service, _, _ = fresh(self)
        hold = service.hold_space("s-focus", "m-ada", at(10), at(12), minutes=45)
        self.assertEqual(hold.expires_at, NOW + timedelta(minutes=45))

    def test_a_hold_window_must_be_positive(self):
        service, _, _ = fresh(self)
        for bad in (0, -5):
            with self.assertRaises(ValidationError):
                service.hold_space("s-focus", "m-ada", at(10), at(12), minutes=bad)

    def test_holds_validate_what_bookings_validate(self):
        service, _, _ = fresh(self)
        with self.assertRaises(NotFound):
            service.hold_space("s-nope", "m-ada", at(10), at(12))
        with self.assertRaises(NotFound):
            service.hold_space("s-focus", "m-nope", at(10), at(12))
        with self.assertRaises(OutsideOpeningHours):
            service.hold_space("s-focus", "m-ada", at(6), at(7))
        with self.assertRaises(ValidationError):
            service.hold_space("s-focus", "m-ada", at(12), at(10))


class HoldConflictTests(unittest.TestCase):
    def test_a_live_hold_blocks_another_hold(self):
        service, _, _ = fresh(self)
        service.hold_space("s-focus", "m-ada", at(10), at(12))
        with self.assertRaises(ConflictError):
            service.hold_space("s-focus", "m-ada", at(11), at(13))

    def test_a_live_hold_blocks_a_booking(self):
        service, _, _ = fresh(self)
        service.hold_space("s-focus", "m-ada", at(10), at(12))
        with self.assertRaises(ConflictError):
            service.create_booking("s-focus", "m-ada", at(11), at(13))

    def test_an_expired_hold_blocks_nothing(self):
        service, clock, _ = fresh(self)
        service.hold_space("s-focus", "m-ada", at(10), at(12), minutes=15)
        clock.advance(timedelta(minutes=20))
        booking = service.create_booking("s-focus", "m-ada", at(10), at(12))
        self.assertEqual(booking.status, CONFIRMED)

    def test_a_released_hold_blocks_nothing(self):
        service, _, _ = fresh(self)
        hold = service.hold_space("s-focus", "m-ada", at(10), at(12))
        service.release_hold(hold.id)
        booking = service.create_booking("s-focus", "m-ada", at(10), at(12))
        self.assertEqual(booking.status, CONFIRMED)

    def test_holds_are_per_space_and_half_open(self):
        service, _, _ = fresh(self)
        service.hold_space("s-focus", "m-ada", at(10), at(12))
        # A different space is untouched.
        other = service.hold_space("s-studio", "m-ada", at(10), at(12))
        self.assertEqual(other.status, HOLD)
        # Touching at the boundary is not overlapping.
        after = service.hold_space("s-focus", "m-ada", at(12), at(13))
        self.assertEqual(after.status, HOLD)


class ConfirmAndReleaseTests(unittest.TestCase):
    def test_confirming_keeps_the_id_interval_and_quoted_price(self):
        service, clock, _ = fresh(self)
        hold = service.hold_space("s-focus", "m-ada", at(10), at(12))
        clock.advance(timedelta(minutes=5))
        confirmed = service.confirm_hold(hold.id)
        self.assertEqual(confirmed.id, hold.id)
        self.assertEqual(confirmed.status, CONFIRMED)
        self.assertEqual((confirmed.start, confirmed.end), (hold.start, hold.end))
        self.assertEqual(confirmed.price_cents, hold.price_cents)
        self.assertIsNone(confirmed.expires_at)
        self.assertEqual(service.repos.bookings.get(hold.id).status, CONFIRMED)

    def test_an_expired_hold_cannot_be_confirmed(self):
        service, clock, _ = fresh(self)
        hold = service.hold_space("s-focus", "m-ada", at(10), at(12), minutes=15)
        clock.advance(timedelta(minutes=15))
        with self.assertRaises(ConflictError):
            service.confirm_hold(hold.id)
        self.assertEqual(service.repos.bookings.get(hold.id).status, HOLD)

    def test_only_holds_can_be_confirmed_or_released(self):
        service, _, _ = fresh(self)
        booking = service.create_booking("s-focus", "m-ada", at(14), at(15))
        with self.assertRaises(ValidationError):
            service.confirm_hold(booking.id)
        with self.assertRaises(ValidationError):
            service.release_hold(booking.id)
        with self.assertRaises(NotFound):
            service.confirm_hold("b-nope")
        with self.assertRaises(NotFound):
            service.release_hold("b-nope")

    def test_releasing_works_live_or_expired(self):
        service, clock, _ = fresh(self)
        live = service.hold_space("s-focus", "m-ada", at(10), at(12))
        released = service.release_hold(live.id)
        self.assertEqual(released.status, CANCELLED)
        self.assertIsNone(released.expires_at)

        stale = service.hold_space("s-studio", "m-ada", at(10), at(12), minutes=15)
        clock.advance(timedelta(minutes=30))
        gone = service.release_hold(stale.id)
        self.assertEqual(gone.status, CANCELLED)
        self.assertIsNone(gone.expires_at)


class AvailabilityTests(unittest.TestCase):
    def test_free_slots_respects_the_moment_it_is_given(self):
        service, clock, _ = fresh(self)
        service.hold_space("s-focus", "m-ada", at(10), at(12), minutes=15)
        bookings = service.repos.bookings.for_space("s-focus")

        live = free_slots(FOCUS, bookings, at(8), now=NOW)
        self.assertNotIn(Interval(at(8), at(20)), live)
        self.assertTrue(any(s.start == at(8) and s.end == at(10) for s in live))
        self.assertTrue(any(s.start == at(12) and s.end == at(20) for s in live))

        expired = free_slots(FOCUS, bookings, at(8), now=NOW + timedelta(minutes=15))
        self.assertEqual([(s.start, s.end) for s in expired], [(at(8), at(20))])

    def test_without_a_moment_every_hold_counts_as_live(self):
        service, clock, _ = fresh(self)
        service.hold_space("s-focus", "m-ada", at(10), at(12), minutes=15)
        clock.advance(timedelta(days=400))
        bookings = service.repos.bookings.for_space("s-focus")
        self.assertFalse(is_free(FOCUS, bookings, Interval(at(10), at(11))))
        self.assertTrue(is_free(FOCUS, bookings, Interval(at(13), at(14))))

    def test_a_released_hold_frees_the_slot(self):
        service, _, _ = fresh(self)
        hold = service.hold_space("s-focus", "m-ada", at(10), at(12))
        service.release_hold(hold.id)
        bookings = service.repos.bookings.for_space("s-focus")
        self.assertTrue(is_free(FOCUS, bookings, Interval(at(10), at(12)), now=NOW))


class UtilizationTests(unittest.TestCase):
    """A hold makes a room unavailable. That is not the same as used."""

    def test_a_live_hold_is_not_utilisation(self):
        service, _, _ = fresh(self)
        service.create_booking("s-focus", "m-ada", at(10), at(13))
        service.hold_space("s-focus", "m-ada", at(14), at(16))
        self.assertEqual(reporting.utilization(service.repos, "s-focus", at(0)), 25.0)

    def test_expired_and_released_holds_are_not_utilisation_either(self):
        service, clock, _ = fresh(self)
        service.create_booking("s-focus", "m-ada", at(10), at(13))
        service.hold_space("s-focus", "m-ada", at(14), at(16), minutes=15)
        released = service.hold_space("s-focus", "m-ada", at(16), at(18))
        service.release_hold(released.id)
        clock.advance(timedelta(minutes=30))
        self.assertEqual(reporting.utilization(service.repos, "s-focus", at(0)), 25.0)

    def test_the_per_space_report_agrees_when_it_exists(self):
        by_space = getattr(reporting, "utilization_by_space", None)
        if by_space is None:
            self.skipTest("utilization_by_space is not part of this tree")
        service, _, _ = fresh(self)
        service.create_booking("s-focus", "m-ada", at(10), at(13))
        service.hold_space("s-focus", "m-ada", at(14), at(16))
        self.assertEqual(by_space(service.repos, at(0))["s-focus"], 25.0)


class StoreTests(unittest.TestCase):
    def test_expiry_survives_a_reload(self):
        service, _, path = fresh(self)
        hold = service.hold_space("s-focus", "m-ada", at(10), at(12))
        booking = service.create_booking("s-focus", "m-ada", at(14), at(15))

        reloaded = Repositories(JsonStore(path))
        self.assertEqual(reloaded.bookings.get(hold.id).expires_at, hold.expires_at)
        self.assertEqual(reloaded.bookings.get(hold.id).status, HOLD)
        self.assertIsNone(reloaded.bookings.get(booking.id).expires_at)


class ApiTests(unittest.TestCase):
    def _router(self):
        service, clock, _ = fresh(self)
        return build_router(service), service, clock

    def test_taking_a_hold_over_http(self):
        router, _, _ = self._router()
        response = router.dispatch("POST", "/spaces/s-focus/holds", None,
                                   {"member_id": "m-ada", "start": at(10).isoformat(),
                                    "end": at(12).isoformat()})
        self.assertEqual(response.status, 201)
        self.assertEqual(response.body["status"], HOLD)
        self.assertTrue(response.body["expires_at"].startswith("2026-09-01T07:15"))

        missing = router.dispatch("POST", "/spaces/s-nope/holds", None,
                                  {"member_id": "m-ada", "start": at(10).isoformat(),
                                   "end": at(12).isoformat()})
        self.assertEqual(missing.status, 404)

        clash = router.dispatch("POST", "/spaces/s-focus/holds", None,
                                {"member_id": "m-ada", "start": at(11).isoformat(),
                                 "end": at(13).isoformat()})
        self.assertEqual(clash.status, 409)

    def test_confirming_over_http(self):
        router, service, clock = self._router()
        hold = service.hold_space("s-focus", "m-ada", at(10), at(12), minutes=15)
        ok = router.dispatch("POST", "/holds/%s/confirm" % hold.id, None, {})
        self.assertEqual(ok.status, 200)
        self.assertEqual(ok.body["status"], CONFIRMED)
        self.assertIsNone(ok.body["expires_at"])

        stale = service.hold_space("s-studio", "m-ada", at(10), at(12), minutes=15)
        clock.advance(timedelta(minutes=20))
        expired = router.dispatch("POST", "/holds/%s/confirm" % stale.id, None, {})
        self.assertEqual(expired.status, 409)
        self.assertEqual(router.dispatch("POST", "/holds/b-nope/confirm", None, {}).status, 404)

    def test_releasing_over_http(self):
        router, service, _ = self._router()
        hold = service.hold_space("s-focus", "m-ada", at(10), at(12))
        ok = router.dispatch("POST", "/holds/%s/release" % hold.id, None, {})
        self.assertEqual(ok.status, 200)
        self.assertEqual(ok.body["status"], CANCELLED)

        booking = service.create_booking("s-focus", "m-ada", at(14), at(15))
        self.assertEqual(
            router.dispatch("POST", "/holds/%s/release" % booking.id, None, {}).status, 400)


if __name__ == "__main__":
    unittest.main()
