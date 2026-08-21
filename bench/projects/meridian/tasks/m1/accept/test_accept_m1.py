"""Held-out acceptance tests for m1. Never present in an arm's worktree."""

import shutil
import tempfile
import unittest
from datetime import timedelta

from meridian.clock import FixedClock, utc
from meridian.domain.models import Member, Space
from meridian.errors import ConflictError, OutsideOpeningHours
from meridian.service.booking import BookingService
from meridian.store.jsonstore import JsonStore
from meridian.store.repositories import Repositories


def service_with_buffer(testcase, buffer_minutes):
    tmpdir = tempfile.mkdtemp(prefix="m1-accept-")
    testcase.addCleanup(shutil.rmtree, tmpdir, True)
    repos = Repositories(JsonStore(tmpdir + "/data.json"))
    repos.spaces.add(Space(id="s-focus", name="Focus Room", capacity=4,
                           hourly_cents=1200, buffer_minutes=buffer_minutes))
    repos.spaces.add(Space(id="s-other", name="Other", capacity=4, hourly_cents=1200))
    repos.members.add(Member(id="m-ada", name="Ada", email="ada@example.com"))
    repos.members.add(Member(id="m-grace", name="Grace", email="g@example.com"))
    repos.commit()
    return BookingService(repos, FixedClock(utc(2026, 9, 1, 7)))


def at(hour, minute=0):
    return utc(2026, 9, 1, hour, minute)


class BufferFieldTests(unittest.TestCase):
    def test_space_has_a_buffer_defaulting_to_zero(self):
        space = Space(id="s", name="S", capacity=1, hourly_cents=100)
        self.assertEqual(space.buffer_minutes, 0)

    def test_buffer_round_trips_through_the_store(self):
        tmpdir = tempfile.mkdtemp(prefix="m1-store-")
        self.addCleanup(shutil.rmtree, tmpdir, True)
        path = tmpdir + "/data.json"
        repos = Repositories(JsonStore(path))
        repos.spaces.add(Space(id="s", name="S", capacity=1, hourly_cents=100,
                               buffer_minutes=30))
        repos.commit()
        self.assertEqual(Repositories(JsonStore(path)).spaces.get("s").buffer_minutes, 30)


class CollisionTests(unittest.TestCase):
    def setUp(self):
        self.service = service_with_buffer(self, 15)
        self.existing = self.service.create_booking("s-focus", "m-ada", at(10), at(12))

    def book(self, start, end, member="m-grace", space="s-focus"):
        return self.service.create_booking(space, member, start, end)

    def test_exact_buffer_gap_is_allowed(self):
        self.assertIsNotNone(self.book(at(12, 15), at(13)))

    def test_short_gap_is_rejected(self):
        with self.assertRaises(ConflictError):
            self.book(at(12, 10), at(13))

    def test_touching_without_buffer_is_rejected(self):
        with self.assertRaises(ConflictError):
            self.book(at(12), at(13))

    def test_direct_overlap_is_rejected(self):
        with self.assertRaises(ConflictError):
            self.book(at(11), at(13))

    def test_the_rule_is_order_independent(self):
        """The earlier booking's own buffer runs into the existing one."""
        with self.assertRaises(ConflictError):
            self.book(at(9), at(10))

    def test_earlier_booking_with_enough_gap_is_allowed(self):
        self.assertIsNotNone(self.book(at(8), at(9, 30)))

    def test_conflict_message_names_the_other_booking(self):
        try:
            self.book(at(11), at(13))
        except ConflictError as exc:
            self.assertIn(self.existing.id, str(exc))
        else:
            self.fail("expected ConflictError")

    def test_other_spaces_are_unaffected(self):
        self.assertIsNotNone(self.book(at(10), at(12), space="s-other"))

    def test_cancelled_bookings_free_the_slot(self):
        self.service.cancel_booking(self.existing.id)
        self.assertIsNotNone(self.book(at(10), at(12)))

    def test_opening_hours_still_take_precedence(self):
        with self.assertRaises(OutsideOpeningHours):
            self.book(at(19), at(23))


class ZeroBufferTests(unittest.TestCase):
    def setUp(self):
        self.service = service_with_buffer(self, 0)
        self.service.create_booking("s-focus", "m-ada", at(10), at(12))

    def test_back_to_back_is_allowed_without_a_buffer(self):
        self.assertIsNotNone(self.service.create_booking("s-focus", "m-grace", at(12), at(13)))

    def test_overlap_is_still_rejected(self):
        with self.assertRaises(ConflictError):
            self.service.create_booking("s-focus", "m-grace", at(11, 59), at(13))


class RescheduleTests(unittest.TestCase):
    def setUp(self):
        self.service = service_with_buffer(self, 15)
        self.a = self.service.create_booking("s-focus", "m-ada", at(10), at(12))
        self.b = self.service.create_booking("s-focus", "m-grace", at(14), at(15))

    def test_a_booking_does_not_collide_with_itself(self):
        moved = self.service.reschedule_booking(self.b.id, at(14, 30), at(15, 30))
        self.assertEqual(moved.start, at(14, 30))

    def test_reschedule_into_a_conflict_is_rejected(self):
        with self.assertRaises(ConflictError):
            self.service.reschedule_booking(self.b.id, at(12), at(13))

    def test_reschedule_respecting_the_buffer_is_allowed(self):
        moved = self.service.reschedule_booking(self.b.id, at(12, 15), at(13))
        self.assertEqual(moved.start, at(12, 15))


class DomainOwnsTheRuleTests(unittest.TestCase):
    """CLAUDE.md: the rule is a domain rule, and free_slots must reflect it."""

    def test_free_slots_subtracts_the_buffer(self):
        from meridian.domain.availability import free_slots
        from meridian.domain.models import Booking

        space = Space(id="s", name="S", capacity=1, hourly_cents=100, buffer_minutes=15)
        booking = Booking(id="b", space_id="s", member_id="m", start=at(10), end=at(12),
                          price_cents=0, created_at=at(7))
        slots = free_slots(space, [booking], at(0))
        self.assertEqual([(s.start.hour, s.start.minute) for s in slots], [(8, 0), (12, 15)])

    def test_is_free_respects_the_buffer(self):
        from meridian.domain.availability import is_free
        from meridian.domain.intervals import Interval
        from meridian.domain.models import Booking

        space = Space(id="s", name="S", capacity=1, hourly_cents=100, buffer_minutes=15)
        booking = Booking(id="b", space_id="s", member_id="m", start=at(10), end=at(12),
                          price_cents=0, created_at=at(7))
        self.assertFalse(is_free(space, [booking], Interval(at(12), at(13))))
        self.assertTrue(is_free(space, [booking], Interval(at(12, 15), at(13))))


if __name__ == "__main__":
    unittest.main()
