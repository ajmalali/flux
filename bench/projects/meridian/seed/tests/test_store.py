import os
import tempfile
import unittest

from meridian.clock import utc
from meridian.domain.models import Booking, Space
from meridian.errors import NotFound
from meridian.store.jsonstore import JsonStore
from meridian.store.repositories import Repositories, from_iso, to_iso


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="meridian-store-")
        self.addCleanup(__import__("shutil").rmtree, self.tmpdir, True)
        self.path = os.path.join(self.tmpdir, "data.json")

    def test_roundtrips_through_disk(self):
        repos = Repositories(JsonStore(self.path))
        repos.spaces.add(Space(id="s-1", name="One", capacity=2, hourly_cents=100))
        repos.bookings.add(Booking(id="b-1", space_id="s-1", member_id="m-1",
                                   start=utc(2026, 9, 1, 10), end=utc(2026, 9, 1, 11),
                                   price_cents=100, created_at=utc(2026, 9, 1, 9)))
        repos.commit()

        reloaded = Repositories(JsonStore(self.path))
        booking = reloaded.bookings.get("b-1")
        self.assertEqual(booking.start, utc(2026, 9, 1, 10))
        self.assertEqual(reloaded.spaces.get("s-1").name, "One")

    def test_missing_id_raises_not_found(self):
        repos = Repositories(JsonStore(self.path))
        with self.assertRaises(NotFound):
            repos.spaces.get("nope")

    def test_iso_roundtrip_keeps_utc(self):
        self.assertEqual(from_iso(to_iso(utc(2026, 9, 1, 10))), utc(2026, 9, 1, 10))

    def test_save_leaves_no_temp_files(self):
        repos = Repositories(JsonStore(self.path))
        repos.spaces.add(Space(id="s-1", name="One", capacity=2, hourly_cents=100))
        repos.commit()
        self.assertEqual([n for n in os.listdir(self.tmpdir) if n.endswith(".tmp")], [])
