"""Orchestration: the only layer allowed to touch both ``domain`` and ``store``.

Every mutation here follows the same shape — validate references, apply the
domain rules, write, commit — so a new rule has exactly one obvious home.
"""

from ..domain.availability import within_opening_hours
from ..domain.intervals import Interval
from ..domain.models import Booking
from ..domain.pricing import quote
from ..errors import NotFound, OutsideOpeningHours, ValidationError


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

    def cancel_booking(self, booking_id):
        booking = self.repos.bookings.get(booking_id)
        if not booking.is_active:
            raise ValidationError("booking %s is already cancelled" % booking_id)
        cancelled = booking.cancelled()
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
        moved = type(booking)(
            id=booking.id,
            space_id=booking.space_id,
            member_id=booking.member_id,
            start=interval.start,
            end=interval.end,
            price_cents=quote(space, member, interval),
            created_at=booking.created_at,
            status=booking.status,
        )
        self.repos.bookings.replace(moved)
        self.repos.commit()
        return moved

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


def _sequential_ids(repos):
    def make():
        return "b-%04d" % (len(repos.bookings.all()) + 1)

    return make
