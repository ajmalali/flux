"""Persistence for the entities. Rules live in ``domain``; this layer only stores.

Datetimes are ISO-8601 strings on disk and timezone-aware UTC objects in memory;
the conversion lives here and nowhere else.
"""

from datetime import datetime, timezone

from ..domain.models import Booking, Member, Space
from ..errors import NotFound


def to_iso(moment):
    return moment.astimezone(timezone.utc).isoformat()


def from_iso(text):
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class _Repository(object):
    table_name = ""
    entity = None
    date_fields = ()

    def __init__(self, store):
        self.store = store

    # -- serialisation ---------------------------------------------------
    def _to_row(self, obj):
        row = dict(obj.__dict__)
        for field_name in self.date_fields:
            row[field_name] = to_iso(row[field_name])
        return row

    def _from_row(self, row):
        data = dict(row)
        for field_name in self.date_fields:
            data[field_name] = from_iso(data[field_name])
        return self.entity(**data)

    # -- queries ---------------------------------------------------------
    def all(self):
        return [self._from_row(row) for row in self.store.table(self.table_name)]

    def get(self, identifier):
        for row in self.store.table(self.table_name):
            if row["id"] == identifier:
                return self._from_row(row)
        raise NotFound("no %s with id %r" % (self.table_name[:-1], identifier))

    def exists(self, identifier):
        return any(row["id"] == identifier for row in self.store.table(self.table_name))

    # -- mutations -------------------------------------------------------
    def add(self, obj):
        if self.exists(obj.id):
            raise ValueError("duplicate id %r in %s" % (obj.id, self.table_name))
        self.store.table(self.table_name).append(self._to_row(obj))
        return obj

    def replace(self, obj):
        table = self.store.table(self.table_name)
        for index, row in enumerate(table):
            if row["id"] == obj.id:
                table[index] = self._to_row(obj)
                return obj
        raise NotFound("no %s with id %r" % (self.table_name[:-1], obj.id))


class SpaceRepository(_Repository):
    table_name = "spaces"
    entity = Space


class MemberRepository(_Repository):
    table_name = "members"
    entity = Member


class BookingRepository(_Repository):
    table_name = "bookings"
    entity = Booking
    date_fields = ("start", "end", "created_at")

    def for_space(self, space_id):
        return [b for b in self.all() if b.space_id == space_id]

    def for_member(self, member_id):
        return [b for b in self.all() if b.member_id == member_id]

    def for_series(self, series_id):
        """Every occurrence of ``series_id``, chronologically."""
        if not series_id:
            return []
        found = [b for b in self.all() if b.series_id == series_id]
        return sorted(found, key=lambda b: b.start)


class Repositories(object):
    """The three repositories over one store, so callers pass one object."""

    def __init__(self, store):
        self.store = store
        self.spaces = SpaceRepository(store)
        self.members = MemberRepository(store)
        self.bookings = BookingRepository(store)

    def commit(self):
        self.store.save()
