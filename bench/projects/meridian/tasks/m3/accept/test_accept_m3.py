"""Held-out acceptance tests for m3."""

import shutil
import tempfile
import unittest
from datetime import timedelta

from meridian.clock import FixedClock, utc
from meridian.domain.models import Member, Space
from meridian.errors import ConflictError, NotFound, OutsideOpeningHours, ValidationError
from meridian.service.booking import BookingService
from meridian.store.jsonstore import JsonStore
from meridian.store.repositories import Repositories

# Tuesday 2026-09-01, 10:00 UTC.
START = utc(2026, 9, 1, 10)
END = utc(2026, 9, 1, 12)


def build(testcase, now=None, buffer_minutes=15):
    tmpdir = tempfile.mkdtemp(prefix="m3-accept-")
    testcase.addCleanup(shutil.rmtree, tmpdir, True)
    repos = Repositories(JsonStore(tmpdir + "/data.json"))
    repos.spaces.add(Space(id="s-focus", name="Focus", capacity=4, hourly_cents=1200,
                           buffer_minutes=buffer_minutes))
    repos.members.add(Member(id="m-ada", name="Ada", email="ada@example.com"))
    repos.members.add(Member(id="m-grace", name="Grace", email="g@example.com"))
    repos.commit()
    return BookingService(repos, FixedClock(now or utc(2026, 8, 1, 9))), tmpdir


def weeks_later(moment, k):
    return moment + timedelta(days=7 * k)


class CreateSeriesTests(unittest.TestCase):
    def setUp(self):
        self.service, self.tmpdir = build(self)

    def test_creates_one_booking_per_week(self):
        series = self.service.create_series("s-focus", "m-ada", START, END, 4)
        self.assertEqual(len(series), 4)
        self.assertEqual([b.start for b in series], [weeks_later(START, k) for k in range(4)])
        self.assertEqual([b.end for b in series], [weeks_later(END, k) for k in range(4)])

    def test_all_occurrences_share_one_series_id(self):
        series = self.service.create_series("s-focus", "m-ada", START, END, 3)
        ids = {b.series_id for b in series}
        self.assertEqual(len(ids), 1)
        self.assertTrue(ids.pop())

    def test_two_series_do_not_share_an_id(self):
        first = self.service.create_series("s-focus", "m-ada", START, END, 2)
        second = self.service.create_series("s-focus", "m-ada",
                                            START + timedelta(hours=3),
                                            END + timedelta(hours=3), 2)
        self.assertNotEqual(first[0].series_id, second[0].series_id)

    def test_one_off_bookings_have_no_series(self):
        booking = self.service.create_booking("s-focus", "m-ada", START, END)
        self.assertEqual(booking.series_id, "")

    def test_each_occurrence_is_priced(self):
        series = self.service.create_series("s-focus", "m-ada", START, END, 2)
        self.assertTrue(all(b.price_cents == 2400 for b in series))

    def test_series_ids_are_unique_per_booking(self):
        series = self.service.create_series("s-focus", "m-ada", START, END, 5)
        self.assertEqual(len({b.id for b in series}), 5)

    def test_persists(self):
        series = self.service.create_series("s-focus", "m-ada", START, END, 3)
        repos = Repositories(JsonStore(self.tmpdir + "/data.json"))
        stored = repos.bookings.for_series(series[0].series_id)
        self.assertEqual([b.id for b in stored], [b.id for b in series])


class WeeksValidationTests(unittest.TestCase):
    def setUp(self):
        self.service, _ = build(self)

    def test_zero_weeks_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.service.create_series("s-focus", "m-ada", START, END, 0)

    def test_negative_weeks_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.service.create_series("s-focus", "m-ada", START, END, -1)

    def test_more_than_a_year_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.service.create_series("s-focus", "m-ada", START, END, 53)

    def test_one_week_is_allowed(self):
        self.assertEqual(len(self.service.create_series("s-focus", "m-ada", START, END, 1)), 1)

    def test_fifty_two_weeks_is_allowed(self):
        self.assertEqual(len(self.service.create_series("s-focus", "m-ada", START, END, 52)), 52)


class ConflictTests(unittest.TestCase):
    def setUp(self):
        self.service, self.tmpdir = build(self)
        # Blocks the third occurrence only.
        self.blocker = self.service.create_booking(
            "s-focus", "m-grace", weeks_later(START, 2), weeks_later(END, 2))

    def test_default_is_all_or_nothing(self):
        with self.assertRaises(ConflictError):
            self.service.create_series("s-focus", "m-ada", START, END, 4)

    def test_nothing_is_persisted_when_it_fails(self):
        try:
            self.service.create_series("s-focus", "m-ada", START, END, 4)
        except ConflictError:
            pass
        remaining = self.service.repos.bookings.all()
        self.assertEqual([b.id for b in remaining], [self.blocker.id])

    def test_skip_conflicts_creates_the_rest(self):
        series = self.service.create_series("s-focus", "m-ada", START, END, 4,
                                            skip_conflicts=True)
        self.assertEqual([b.start for b in series],
                         [weeks_later(START, k) for k in (0, 1, 3)])

    def test_the_buffer_rule_applies_to_occurrences(self):
        """Ten minutes of changeover is not enough; the series must be refused."""
        with self.assertRaises(ConflictError):
            self.service.create_series("s-focus", "m-ada",
                                       weeks_later(END, 2) + timedelta(minutes=10),
                                       weeks_later(END, 2) + timedelta(minutes=70), 1)

    def test_exact_buffer_gap_is_accepted(self):
        series = self.service.create_series("s-focus", "m-ada",
                                            weeks_later(END, 2) + timedelta(minutes=15),
                                            weeks_later(END, 2) + timedelta(minutes=75), 1)
        self.assertEqual(len(series), 1)

    def test_everything_conflicting_still_raises_under_skip(self):
        with self.assertRaises(ConflictError):
            self.service.create_series("s-focus", "m-ada",
                                       weeks_later(START, 2), weeks_later(END, 2), 1,
                                       skip_conflicts=True)

    def test_opening_hours_are_not_skippable(self):
        with self.assertRaises(OutsideOpeningHours):
            self.service.create_series("s-focus", "m-ada", utc(2026, 9, 1, 19),
                                       utc(2026, 9, 1, 23), 3, skip_conflicts=True)


class CancelSeriesTests(unittest.TestCase):
    def setUp(self):
        # "Now" sits between the refund tiers of the first two occurrences:
        # occurrence 0 starts in 3 hours (25%), occurrence 1 a week later (100%).
        self.service, self.tmpdir = build(self, now=START - timedelta(hours=3))
        self.series = self.service.create_series("s-focus", "m-ada", START, END, 3)
        self.series_id = self.series[0].series_id

    def test_cancels_every_occurrence(self):
        cancelled = self.service.cancel_series(self.series_id)
        self.assertEqual(len(cancelled), 3)
        self.assertTrue(all(b.status == "cancelled" for b in cancelled))

    def test_refunds_are_tiered_per_occurrence(self):
        cancelled = self.service.cancel_series(self.series_id)
        self.assertEqual(cancelled[0].refund_cents, 600)    # 25% of 2400
        self.assertEqual(cancelled[1].refund_cents, 2400)   # a week out: full
        self.assertEqual(cancelled[2].refund_cents, 2400)

    def test_returns_chronological_order(self):
        cancelled = self.service.cancel_series(self.series_id)
        self.assertEqual([b.start for b in cancelled], sorted(b.start for b in cancelled))

    def test_already_cancelled_occurrences_are_left_alone(self):
        self.service.cancel_booking(self.series[1].id)
        cancelled = self.service.cancel_series(self.series_id)
        self.assertEqual([b.id for b in cancelled], [self.series[0].id, self.series[2].id])

    def test_unknown_series_is_not_found(self):
        with self.assertRaises(NotFound):
            self.service.cancel_series("sr-nope")

    def test_nothing_left_to_cancel_is_a_validation_error(self):
        self.service.cancel_series(self.series_id)
        with self.assertRaises(ValidationError):
            self.service.cancel_series(self.series_id)

    def test_cancelling_frees_the_slot(self):
        self.service.cancel_series(self.series_id)
        self.assertIsNotNone(self.service.create_booking("s-focus", "m-grace", START, END))


class SeriesApiTests(unittest.TestCase):
    def setUp(self):
        self.service, _ = build(self)
        self.series = self.service.create_series("s-focus", "m-ada", START, END, 3)

    def router(self):
        from meridian.api.handlers import build_router

        return build_router(self.service)

    def test_get_series(self):
        response = self.router().dispatch("GET", "/series/%s" % self.series[0].series_id)
        self.assertEqual(response.status, 200)
        self.assertEqual(response.body["series_id"], self.series[0].series_id)
        self.assertEqual(len(response.body["bookings"]), 3)
        self.assertEqual(response.body["bookings"][0]["id"], self.series[0].id)

    def test_unknown_series_is_404(self):
        self.assertEqual(self.router().dispatch("GET", "/series/sr-nope").status, 404)


if __name__ == "__main__":
    unittest.main()
