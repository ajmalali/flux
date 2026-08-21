"""Held-out acceptance tests for s1. Never present in any arm's worktree."""

import unittest

from slugify import slugify


class MaxLengthTests(unittest.TestCase):
    def test_default_is_unchanged(self):
        self.assertEqual(slugify("Hello World"), "hello-world")
        self.assertEqual(slugify("Hello World", max_length=None), "hello-world")

    def test_cuts_on_word_boundary(self):
        self.assertEqual(slugify("the quick brown fox", max_length=12), "the-quick")

    def test_exact_fit_is_kept_whole(self):
        self.assertEqual(slugify("the quick brown fox", max_length=9), "the-quick")

    def test_hard_truncates_a_single_long_word(self):
        self.assertEqual(slugify("supercalifragilistic", max_length=5), "super")

    def test_never_leaves_a_trailing_hyphen(self):
        for limit in range(1, 20):
            slug = slugify("the quick brown fox", max_length=limit)
            self.assertFalse(slug.startswith("-"), limit)
            self.assertFalse(slug.endswith("-"), limit)
            self.assertLessEqual(len(slug), limit, limit)

    def test_rejects_non_positive_limits(self):
        with self.assertRaises(ValueError):
            slugify("hello world", max_length=0)
        with self.assertRaises(ValueError):
            slugify("hello world", max_length=-3)


if __name__ == "__main__":
    unittest.main()
