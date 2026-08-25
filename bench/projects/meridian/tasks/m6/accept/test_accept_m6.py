"""Held-out acceptance tests for m6. Never present in an arm's worktree.

m6 is the corpus's first bug report rather than a feature request, and its brief
is deliberately terse: it names the symptom and refuses to name the rule. So
these tests are written to be **blind to the mechanism**. Two different fixes are
legal — refuse the booking that would be trapped, or refuse the confirmation that
would spring the trap — and a suite that pinned either one would score an arm on
guessing our implementation rather than on finding the invariant. What is pinned
is the invariant itself, and that *something* refuses.

Everything here binds to API briefed in m1 (`buffer_minutes`, the collision rule,
`ConflictError`) or m5 (`hold_space` / `confirm_hold` / `release_hold` and their
HTTP mappings). Nothing binds to a symbol this brief invented, because it
invented none.
"""

import shutil
import tempfile
import unittest
from datetime import timedelta

from meridian.api.handlers import build_router
from meridian.clock import FixedClock, utc
from meridian.domain.intervals import overlaps
from meridian.domain.models import CONFIRMED, Member, Space
from meridian.errors import ConflictError
from meridian.service.booking import BookingService
from meridian.store.jsonstore import JsonStore
from meridian.store.repositories import Repositories

BAY = Space(id="s-bay", name="Bay 2", capacity=6, hourly_cents=1500, buffer_minutes=15)
FLAT = Space(id="s-flat", name="Flat White", capacity=2, hourly_cents=800)
ADA = Member(id="m-ada", name="Ada", email="ada@example.com")
BOB = Member(id="m-bob", name="Bob", email="bob@example.com")
NOW = utc(2026, 9, 1, 7, 0)


def at(hour, minute=0):
    return utc(2026, 9, 1, hour, minute)


def fresh(testcase):
    tmpdir = tempfile.mkdtemp(prefix="m6-accept-")
    testcase.addCleanup(shutil.rmtree, tmpdir, True)
    repos = Repositories(JsonStore(tmpdir + "/data.json"))
    for space in (BAY, FLAT):
        repos.spaces.add(space)
    for member in (ADA, BOB):
        repos.members.add(member)
    repos.commit()
    clock = FixedClock(NOW)
    return BookingService(repos, clock), clock, repos


def confirmed_in(repos, space_id):
    return [b for b in repos.bookings.for_space(space_id) if b.status == CONFIRMED]


def changeover_is_respected(space, bookings):
    """The m1 rule, restated over whatever ended up confirmed.

    Two confirmed bookings collide when their intervals overlap once each is
    extended by the space's changeover. This is the brief's "rule that is already
    in this codebase" -- read off m1's brief, not off any particular tree.
    """
    buffer_ = timedelta(minutes=space.buffer_minutes)
    for i, a in enumerate(bookings):
        for b in bookings[i + 1:]:
            if overlaps(a.start, a.end + buffer_, b.start, b.end + buffer_):
                return False
    return True


def run_the_reported_sequence(service):
    """Hold 09:00-10:00, book 10:00-11:00, confirm the hold.

    Returns which steps refused. Either refusal is a legal fix; no refusal at all
    is the bug.
    """
    refused = []
    hold = service.hold_space("s-bay", "m-ada", at(9), at(10), minutes=15)
    try:
        service.create_booking("s-bay", "m-bob", at(10), at(11))
    except ConflictError:
        refused.append("create")
    try:
        service.confirm_hold(hold.id)
    except ConflictError:
        refused.append("confirm")
    return hold, refused


class TheReportedSequence(unittest.TestCase):
    def test_something_refuses_the_step_that_would_create_the_clash(self):
        service, _, _ = fresh(self)
        _, refused = run_the_reported_sequence(service)
        self.assertTrue(
            refused,
            "the sequence in the ticket was accepted end to end -- this is the bug",
        )

    def test_the_room_is_never_left_double_booked(self):
        """The invariant, whichever step did the refusing."""
        service, _, repos = fresh(self)
        run_the_reported_sequence(service)
        self.assertTrue(
            changeover_is_respected(BAY, confirmed_in(repos, "s-bay")),
            "two confirmed bookings ended up inside each other's changeover",
        )

    def test_the_refusal_is_the_systems_existing_one(self):
        """Ops read these errors: a taken slot is a ConflictError, not a crash."""
        service, _, _ = fresh(self)
        hold = service.hold_space("s-bay", "m-ada", at(9), at(10), minutes=15)
        try:
            service.create_booking("s-bay", "m-bob", at(10), at(11))
        except ConflictError:
            return  # refused at the booking; nothing left to trap
        with self.assertRaises(ConflictError):
            service.confirm_hold(hold.id)

    def test_the_same_trap_the_other_way_round(self):
        """Two adjacent holds cannot both become confirmed in a buffered space."""
        service, _, repos = fresh(self)
        first = service.hold_space("s-bay", "m-ada", at(13), at(14), minutes=30)
        second = service.hold_space("s-bay", "m-bob", at(14), at(15), minutes=30)
        refused = 0
        for hold in (first, second):
            try:
                service.confirm_hold(hold.id)
            except ConflictError:
                refused += 1
        self.assertEqual(refused, 1, "exactly one of the two can be honoured")
        self.assertTrue(changeover_is_respected(BAY, confirmed_in(repos, "s-bay")))


class NotOverCorrected(unittest.TestCase):
    """The fix must not cost the behaviour the previous phases established."""

    def test_a_hold_with_nothing_against_it_still_confirms(self):
        service, _, repos = fresh(self)
        hold = service.hold_space("s-bay", "m-ada", at(9), at(10), minutes=15)
        confirmed = service.confirm_hold(hold.id)
        self.assertEqual(confirmed.status, CONFIRMED)
        self.assertEqual(confirmed.id, hold.id)
        self.assertIsNone(confirmed.expires_at)
        self.assertEqual(confirmed.price_cents, hold.price_cents)
        self.assertEqual(len(confirmed_in(repos, "s-bay")), 1)

    def test_a_space_with_no_changeover_still_books_back_to_back(self):
        service, _, repos = fresh(self)
        hold = service.hold_space("s-flat", "m-ada", at(9), at(10), minutes=15)
        service.create_booking("s-flat", "m-bob", at(10), at(11))
        service.confirm_hold(hold.id)
        self.assertEqual(len(confirmed_in(repos, "s-flat")), 2)

    def test_a_live_hold_still_claims_only_its_own_interval(self):
        """m5, unchanged: a hold is not occupancy, so it carries no changeover."""
        service, _, _ = fresh(self)
        service.hold_space("s-bay", "m-ada", at(9), at(10), minutes=15)
        service.hold_space("s-bay", "m-bob", at(10), at(11), minutes=15)

    def test_a_released_hold_traps_nothing(self):
        service, _, repos = fresh(self)
        hold = service.hold_space("s-bay", "m-ada", at(9), at(10), minutes=15)
        service.release_hold(hold.id)
        service.create_booking("s-bay", "m-bob", at(10), at(11))
        self.assertEqual(len(confirmed_in(repos, "s-bay")), 1)
        self.assertTrue(changeover_is_respected(BAY, confirmed_in(repos, "s-bay")))

    def test_an_expired_hold_cannot_be_confirmed_at_all(self):
        service, clock, _ = fresh(self)
        hold = service.hold_space("s-bay", "m-ada", at(9), at(10), minutes=15)
        clock.advance(timedelta(minutes=20))
        with self.assertRaises(ConflictError):
            service.confirm_hold(hold.id)


class OverHttp(unittest.TestCase):
    def test_the_front_end_sees_a_409_and_not_a_500(self):
        service, _, repos = fresh(self)
        router = build_router(service)
        hold = service.hold_space("s-bay", "m-ada", at(9), at(10), minutes=15)
        try:
            service.create_booking("s-bay", "m-bob", at(10), at(11))
        except ConflictError:
            self.assertTrue(changeover_is_respected(BAY, confirmed_in(repos, "s-bay")))
            return  # refused before the trap could be set
        response = router.dispatch("POST", "/holds/%s/confirm" % hold.id, None, {})
        self.assertEqual(response.status, 409)
        self.assertTrue(changeover_is_respected(BAY, confirmed_in(repos, "s-bay")))


if __name__ == "__main__":
    unittest.main()
