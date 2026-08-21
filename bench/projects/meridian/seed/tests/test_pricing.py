import unittest

from meridian.clock import utc
from meridian.domain.intervals import Interval
from meridian.domain.pricing import billable_minutes, quote, round_half_up
from tests.fixtures import ADA, FOCUS, GRACE


def span(start_hour, minutes):
    start = utc(2026, 9, 1, start_hour)
    return Interval(start, start + __import__("datetime").timedelta(minutes=minutes))


class PricingTests(unittest.TestCase):
    def test_round_half_up_goes_away_from_zero(self):
        self.assertEqual(round_half_up(5, 2), 3)
        self.assertEqual(round_half_up(4, 2), 2)

    def test_minimum_charge_is_one_hour(self):
        self.assertEqual(billable_minutes(span(10, 20)), 60)

    def test_part_blocks_round_up(self):
        self.assertEqual(billable_minutes(span(10, 76)), 90)

    def test_basic_member_pays_the_rate(self):
        self.assertEqual(quote(FOCUS, ADA, span(10, 120)), 2400)

    def test_pro_member_gets_ten_percent_off(self):
        self.assertEqual(quote(FOCUS, GRACE, span(10, 120)), 2160)
