"""Orchestration: the only layer allowed to touch both ``domain`` and ``store``.

Every mutation here follows the same shape — validate references, apply the
domain rules, write, commit — so a new rule has exactly one obvious home.
"""

from dataclasses import replace
from datetime import timedelta

from ..domain.availability import find_conflict, within_opening_hours
from ..domain.intervals import Interval
from ..domain.models import Booking, CANCELLED, CONFIRMED, HOLD
from ..domain.policy import refund_for
from ..domain.pricing import quote
from ..errors import ConflictError, NotFound, OutsideOpeningHours, ValidationError


class BookingService(object):
    def __init__(self, repos, clock, id_factory=None):
        self.repos = repos
        self.clock = clock
        self._id_factory = id_factory or _sequential_ids(repos)

    # -- commands --------------------------------------------------------

    def create_booking(self, space_id, member_id, start, end):
        space = self.repos.spaces.get(space_id)
        member = self.repos.members.get(member_id)
        interval = _interval(start, end)

        if not within_opening_hours(space, interval):
            raise OutsideOpeningHours(
                "%s is open %02d:00-%02d:00" % (space.name, space.open_hour, space.close_hour)
            )
        self._reject_conflicts(space, interval)

        booking = Booking(
            id=self._id_factory(),
            space_id=space.id,
            member_id=member.id,
            start=interval.start,
            end=interval.end,
            price_cents=quote(space, member, interval),
            created_at=self.clock.now(),
        )
        self.repos.bookings.add(booking)
        self.repos.commit()
        return booking

    MAX_SERIES_WEEKS = 52

    def create_series(self, space_id, member_id, start, end, weeks, skip_conflicts=False):
        """Create one booking per week for ``weeks`` weeks, sharing a series id.

        All-or-nothing by default: every occurrence is checked against the same
        rules a single booking faces *before* anything is written, so a partial
        series can never be left behind for someone to clean up.
        """
        space = self.repos.spaces.get(space_id)
        member = self.repos.members.get(member_id)
        if not isinstance(weeks, int) or isinstance(weeks, bool):
            raise ValidationError("weeks must be an integer")
        if not 1 <= weeks <= self.MAX_SERIES_WEEKS:
            raise ValidationError("weeks must be between 1 and %d" % self.MAX_SERIES_WEEKS)

        existing = self.repos.bookings.for_space(space.id)
        planned = []
        for week in range(weeks):
            offset = timedelta(days=7 * week)
            interval = _interval(start + offset, end + offset)
            if not within_opening_hours(space, interval):
                raise OutsideOpeningHours(
                    "%s is open %02d:00-%02d:00" % (space.name, space.open_hour, space.close_hour)
                )
            clash = find_conflict(space, existing + planned, interval)
            if clash is None:
                planned.append(_planned(interval))
            elif not skip_conflicts:
                raise ConflictError(
                    "%s is already booked: occurrence %s conflicts with %s"
                    % (space.name, interval.start.isoformat(), clash.id)
                )
        if not planned:
            raise ConflictError("every occurrence of the series conflicts with an existing booking")

        series_id = self._next_series_id()
        created = []
        for interval in [p.interval for p in planned]:
            booking = Booking(
                id=self._id_factory(),
                space_id=space.id,
                member_id=member.id,
                start=interval.start,
                end=interval.end,
                price_cents=quote(space, member, interval),
                created_at=self.clock.now(),
                series_id=series_id,
            )
            self.repos.bookings.add(booking)
            created.append(booking)
        self.repos.commit()
        return created

    def cancel_series(self, series_id):
        """Cancel every still-confirmed occurrence, each refunded on its own merits."""
        occurrences = self.repos.bookings.for_series(series_id)
        if not occurrences:
            raise NotFound("no series with id %r" % (series_id,))
        active = [b for b in occurrences if b.is_active]
        if not active:
            raise ValidationError("series %s has nothing left to cancel" % series_id)
        now = self.clock.now()
        cancelled = []
        for booking in active:
            updated = booking.cancelled(refund_cents=refund_for(booking, now))
            self.repos.bookings.replace(updated)
            cancelled.append(updated)
        self.repos.commit()
        return cancelled

    def _next_series_id(self):
        used = {b.series_id for b in self.repos.bookings.all() if b.series_id}
        return "sr-%04d" % (len(used) + 1)

    # -- holds -----------------------------------------------------------

    def hold_space(self, space_id, member_id, start, end, minutes=15):
        """Claim a slot for ``minutes`` without paying for it yet."""
        if isinstance(minutes, bool) or not isinstance(minutes, int) or minutes <= 0:
            raise ValidationError("a hold lasts a positive number of minutes")
        space = self.repos.spaces.get(space_id)
        member = self.repos.members.get(member_id)
        interval = _interval(start, end)

        if not within_opening_hours(space, interval):
            raise OutsideOpeningHours(
                "%s is open %02d:00-%02d:00" % (space.name, space.open_hour, space.close_hour)
            )
        self._reject_conflicts(space, interval)

        now = self.clock.now()
        hold = Booking(
            id=self._id_factory(),
            space_id=space.id,
            member_id=member.id,
            start=interval.start,
            end=interval.end,
            price_cents=quote(space, member, interval),
            created_at=now,
            status=HOLD,
            expires_at=now + timedelta(minutes=minutes),
        )
        self.repos.bookings.add(hold)
        self.repos.commit()
        return hold

    def confirm_hold(self, hold_id):
        """Turn a live hold into the booking it was standing in for.

        The collision rule has to be re-applied here, and this is the whole of
        m6. A hold claims its bare interval; a confirmed booking claims that
        interval *plus* the space's changeover. So the moment of confirmation is
        the moment the claim grows, and between taking the hold and confirming it
        somebody else may have been let into the time the changeover needs. The
        check at ``hold_space`` cannot see that -- it ran against a smaller claim,
        earlier -- which is exactly how the reported sequence slipped through
        without any step being wrong on its own.
        """
        hold = self._hold(hold_id)
        if not hold.is_live_hold(self.clock.now()):
            raise ConflictError("hold %s has expired" % hold_id)
        space = self.repos.spaces.get(hold.space_id)
        self._reject_conflicts(space, hold.interval, ignore_id=hold.id)
        confirmed = replace(hold, status=CONFIRMED, expires_at=None)
        self.repos.bookings.replace(confirmed)
        self.repos.commit()
        return confirmed

    def release_hold(self, hold_id):
        """Give the slot back, whether or not the hold had already run out."""
        hold = self._hold(hold_id)
        released = replace(hold, status=CANCELLED, expires_at=None)
        self.repos.bookings.replace(released)
        self.repos.commit()
        return released

    def _hold(self, hold_id):
        booking = self.repos.bookings.get(hold_id)
        if not booking.is_hold:
            raise ValidationError("booking %s is not a hold" % hold_id)
        return booking

    def cancel_booking(self, booking_id):
        booking = self.repos.bookings.get(booking_id)
        if not booking.is_active:
            raise ValidationError("booking %s is already cancelled" % booking_id)
        cancelled = booking.cancelled(refund_cents=refund_for(booking, self.clock.now()))
        self.repos.bookings.replace(cancelled)
        self.repos.commit()
        return cancelled

    def reschedule_booking(self, booking_id, start, end):
        booking = self.repos.bookings.get(booking_id)
        if not booking.is_active:
            raise ValidationError("booking %s is cancelled" % booking_id)
        space = self.repos.spaces.get(booking.space_id)
        member = self.repos.members.get(booking.member_id)
        interval = _interval(start, end)
        if not within_opening_hours(space, interval):
            raise OutsideOpeningHours(
                "%s is open %02d:00-%02d:00" % (space.name, space.open_hour, space.close_hour)
            )
        self._reject_conflicts(space, interval, ignore_id=booking.id)
        moved = type(booking)(
            id=booking.id,
            space_id=booking.space_id,
            member_id=booking.member_id,
            start=interval.start,
            end=interval.end,
            price_cents=quote(space, member, interval),
            created_at=booking.created_at,
            status=booking.status,
            refund_cents=booking.refund_cents,
            series_id=booking.series_id,
        )
        self.repos.bookings.replace(moved)
        self.repos.commit()
        return moved

    # -- rules -----------------------------------------------------------

    def _reject_conflicts(self, space, interval, ignore_id=None):
        """Delegate the collision rule to the domain; never restate it here.

        The moment comes from the injected clock and is handed down, because the
        domain is not allowed to read one -- and without it an expired hold would
        go on blocking for ever.
        """
        clash = find_conflict(space, self.repos.bookings.for_space(space.id),
                              interval, ignore_id=ignore_id, now=self.clock.now())
        if clash is not None:
            raise ConflictError(
                "%s is already booked: conflicts with %s (%s-%s)"
                % (space.name, clash.id, clash.start.isoformat(), clash.end.isoformat())
            )

    # -- queries ---------------------------------------------------------

    def bookings_for_space(self, space_id):
        if not self.repos.spaces.exists(space_id):
            raise NotFound("no space with id %r" % (space_id,))
        return self.repos.bookings.for_space(space_id)


def _interval(start, end):
    try:
        return Interval(start, end)
    except ValueError as exc:
        raise ValidationError(str(exc))


class _planned(object):
    """A validated occurrence, held until the whole series is known to be legal.

    Carries just enough of a booking's shape for find_conflict to judge the next
    occurrence against the ones already planned but not yet written."""

    status = "confirmed"
    id = "<planned>"

    def __init__(self, interval):
        self.interval = interval
        self.start = interval.start
        self.end = interval.end


def _sequential_ids(repos):
    def make():
        return "b-%04d" % (len(repos.bookings.all()) + 1)

    return make
