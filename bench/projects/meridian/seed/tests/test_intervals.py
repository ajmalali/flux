import unittest

from meridian.clock import utc
from meridian.domain.intervals import Interval, merge, overlaps, subtract


class IntervalTests(unittest.TestCase):
    def test_must_end_after_it_starts(self):
        with self.assertRaises(ValueError):
            Interval(utc(2026, 9, 1, 10), utc(2026, 9, 1, 10))

    def test_minutes(self):
        self.assertEqual(Interval(utc(2026, 9, 1, 10), utc(2026, 9, 1, 11, 30)).minutes, 90)

    def test_half_open_touching_intervals_do_not_overlap(self):
        self.assertFalse(overlaps(utc(2026, 9, 1, 9), utc(2026, 9, 1, 10),
                                  utc(2026, 9, 1, 10), utc(2026, 9, 1, 11)))

    def test_genuine_overlap(self):
        self.assertTrue(overlaps(utc(2026, 9, 1, 9), utc(2026, 9, 1, 11),
                                 utc(2026, 9, 1, 10), utc(2026, 9, 1, 12)))

    def test_contains_is_half_open(self):
        span = Interval(utc(2026, 9, 1, 9), utc(2026, 9, 1, 10))
        self.assertTrue(span.contains(utc(2026, 9, 1, 9)))
        self.assertFalse(span.contains(utc(2026, 9, 1, 10)))

    def test_clamp_returns_none_when_disjoint(self):
        window = Interval(utc(2026, 9, 1, 8), utc(2026, 9, 1, 9))
        self.assertIsNone(Interval(utc(2026, 9, 1, 10), utc(2026, 9, 1, 11)).clamp(window))

    def test_merge_joins_touching_and_overlapping(self):
        merged = merge([
            Interval(utc(2026, 9, 1, 9), utc(2026, 9, 1, 10)),
            Interval(utc(2026, 9, 1, 10), utc(2026, 9, 1, 11)),
            Interval(utc(2026, 9, 1, 13), utc(2026, 9, 1, 14)),
        ])
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0].minutes, 120)

    def test_subtract_carves_a_hole(self):
        free = subtract(Interval(utc(2026, 9, 1, 8), utc(2026, 9, 1, 12)),
                        [Interval(utc(2026, 9, 1, 9), utc(2026, 9, 1, 10))])
        self.assertEqual([(f.start.hour, f.end.hour) for f in free], [(8, 9), (10, 12)])
