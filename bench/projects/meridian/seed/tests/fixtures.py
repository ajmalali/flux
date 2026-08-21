"""Shared test scaffolding: an in-memory store seeded with two spaces and two members."""

import os
import tempfile

from meridian.clock import FixedClock, utc
from meridian.domain.models import Member, Space
from meridian.service.booking import BookingService
from meridian.store.jsonstore import JsonStore
from meridian.store.repositories import Repositories

FOCUS = Space(id="s-focus", name="Focus Room", capacity=4, hourly_cents=1200)
STUDIO = Space(id="s-studio", name="Studio", capacity=12, hourly_cents=3000,
               open_hour=9, close_hour=18)
ADA = Member(id="m-ada", name="Ada", email="ada@example.com", plan="basic")
GRACE = Member(id="m-grace", name="Grace", email="grace@example.com", plan="pro")

NOW = utc(2026, 9, 1, 7, 0)


def make_service(tmpdir, clock=None):
    store = JsonStore(os.path.join(tmpdir, "data.json"))
    repos = Repositories(store)
    for space in (FOCUS, STUDIO):
        repos.spaces.add(space)
    for member in (ADA, GRACE):
        repos.members.add(member)
    repos.commit()
    return BookingService(repos, clock or FixedClock(NOW))


def temp_service(testcase, clock=None):
    tmpdir = tempfile.mkdtemp(prefix="meridian-test-")
    testcase.addCleanup(_rmtree, tmpdir)
    return make_service(tmpdir, clock)


def _rmtree(path):
    import shutil

    shutil.rmtree(path, ignore_errors=True)
