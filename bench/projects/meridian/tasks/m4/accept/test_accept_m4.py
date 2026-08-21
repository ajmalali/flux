"""Held-out acceptance tests for m4."""

import shutil
import tempfile
import unittest
from datetime import timedelta

from meridian.api.handlers import build_router
from meridian.clock import FixedClock, utc
from meridian.domain.models import Member, Space
from meridian.service.booking import BookingService
from meridian.service.reporting import utilization, utilization_by_space
from meridian.store.jsonstore import JsonStore
from meridian.store.repositories import Repositories

DAY = utc(2026, 9, 1)


def build(testcase, buffer_minutes=15):
    tmpdir = tempfile.mkdtemp(prefix="m4-accept-")
    testcase.addCleanup(shutil.rmtree, tmpdir, True)
    repos = Repositories(JsonStore(tmpdir + "/data.json"))
    repos.spaces.add(Space(id="s-focus", name="Focus", capacity=4, hourly_cents=1200,
                           buffer_minutes=buffer_minutes))
    repos.spaces.add(Space(id="s-studio", name="Studio", capacity=12, hourly_cents=3000,
                           open_hour=9, close_hour=18))
    repos.members.add(Member(id="m-ada", name="Ada", email="ada@example.com"))
    repos.commit()
    return BookingService(repos, FixedClock(utc(2026, 8, 1, 9)))


def book(service, hour, hours, space="s-focus"):
    start = utc(2026, 9, 1, hour)
    return service.create_booking(space, "m-ada", start, start + timedelta(hours=hours))


class TheReportedBugTests(unittest.TestCase):
    def test_cancelled_bookings_are_not_utilisation(self):
        """The exact scenario from the report: 3x3h, two cancelled, 12h day."""
        service = build(self)
        first = book(service, 8, 3)
        second = book(service, 12, 3)
        third = book(service, 16, 3)
        service.cancel_booking(second.id)
        service.cancel_booking(third.id)
        self.assertEqual(utilization(service.repos, "s-focus", DAY), 25.0)
        self.assertEqual(first.status, "confirmed")

    def test_a_fully_cancelled_day_is_zero(self):
        service = build(self)
        booking = book(service, 8, 6)
        service.cancel_booking(booking.id)
        self.assertEqual(utilization(service.repos, "s-focus", DAY), 0.0)


class BufferIsNotUtilisationTests(unittest.TestCase):
    def test_the_changeover_buffer_is_not_counted(self):
        """15 minutes of changeover after a 3h booking is unavailability, not use."""
        service = build(self, buffer_minutes=15)
        book(service, 8, 3)
        self.assertEqual(utilization(service.repos, "s-focus", DAY), 25.0)

    def test_a_large_buffer_changes_nothing(self):
        service = build(self, buffer_minutes=120)
        book(service, 8, 3)
        self.assertEqual(utilization(service.repos, "s-focus", DAY), 25.0)


class StillWorksTests(unittest.TestCase):
    def test_empty_day(self):
        self.assertEqual(utilization(build(self).repos, "s-focus", DAY), 0.0)

    def test_two_bookings_add_up(self):
        service = build(self)
        book(service, 8, 3)
        book(service, 14, 3)
        self.assertEqual(utilization(service.repos, "s-focus", DAY), 50.0)

    def test_other_days_are_excluded(self):
        service = build(self)
        start = utc(2026, 9, 8, 8)
        service.create_booking("s-focus", "m-ada", start, start + timedelta(hours=6))
        self.assertEqual(utilization(service.repos, "s-focus", DAY), 0.0)

    def test_one_decimal_place(self):
        service = build(self)
        book(service, 8, 1)
        self.assertEqual(utilization(service.repos, "s-focus", DAY), 8.3)


class BySpaceTests(unittest.TestCase):
    def test_includes_every_space_even_unused_ones(self):
        service = build(self)
        book(service, 8, 3)
        report = utilization_by_space(service.repos, DAY)
        self.assertEqual(set(report), {"s-focus", "s-studio"})
        self.assertEqual(report["s-studio"], 0.0)

    def test_each_space_is_measured_against_its_own_hours(self):
        """The Studio is open 09:00-18:00 -- nine hours, not twelve."""
        service = build(self)
        start = utc(2026, 9, 1, 9)
        service.create_booking("s-studio", "m-ada", start, start + timedelta(hours=3))
        report = utilization_by_space(service.repos, DAY)
        self.assertEqual(report["s-studio"], 33.3)

    def test_agrees_with_the_single_space_report(self):
        service = build(self)
        book(service, 8, 3)
        report = utilization_by_space(service.repos, DAY)
        self.assertEqual(report["s-focus"], utilization(service.repos, "s-focus", DAY))

    def test_cancellations_are_excluded_here_too(self):
        service = build(self)
        booking = book(service, 8, 3)
        service.cancel_booking(booking.id)
        self.assertEqual(utilization_by_space(service.repos, DAY)["s-focus"], 0.0)


class UtilizationApiTests(unittest.TestCase):
    def setUp(self):
        self.service = build(self)
        book(self.service, 8, 3)
        self.router = build_router(self.service)

    def test_single_space(self):
        response = self.router.dispatch("GET", "/spaces/s-focus/utilization",
                                        query={"day": "2026-09-01"})
        self.assertEqual(response.status, 200)
        self.assertEqual(response.body["space_id"], "s-focus")
        self.assertEqual(response.body["day"], "2026-09-01")
        self.assertEqual(response.body["percent"], 25.0)

    def test_unknown_space_is_404(self):
        self.assertEqual(
            self.router.dispatch("GET", "/spaces/s-nope/utilization",
                                 query={"day": "2026-09-01"}).status, 404)

    def test_missing_day_is_400(self):
        self.assertEqual(
            self.router.dispatch("GET", "/spaces/s-focus/utilization", query={}).status, 400)

    def test_unparseable_day_is_400(self):
        self.assertEqual(
            self.router.dispatch("GET", "/spaces/s-focus/utilization",
                                 query={"day": "not-a-date"}).status, 400)

    def test_all_spaces(self):
        response = self.router.dispatch("GET", "/utilization", query={"day": "2026-09-01"})
        self.assertEqual(response.status, 200)
        self.assertEqual(response.body["day"], "2026-09-01")
        self.assertEqual(response.body["spaces"]["s-focus"], 25.0)
        self.assertEqual(response.body["spaces"]["s-studio"], 0.0)

    def test_all_spaces_missing_day_is_400(self):
        self.assertEqual(self.router.dispatch("GET", "/utilization", query={}).status, 400)

    def test_existing_endpoints_still_work(self):
        self.assertEqual(self.router.dispatch("GET", "/spaces").status, 200)


if __name__ == "__main__":
    unittest.main()
