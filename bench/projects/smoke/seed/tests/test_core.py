import unittest

from slugify import slugify


class SlugifyTests(unittest.TestCase):
    def test_lowercases_and_hyphenates(self):
        self.assertEqual(slugify("Hello World"), "hello-world")

    def test_strips_accents(self):
        self.assertEqual(slugify("Crème Brûlée"), "creme-brulee")

    def test_collapses_separators(self):
        self.assertEqual(slugify("a -- b__c"), "a-b-c")

    def test_trims_edges(self):
        self.assertEqual(slugify("  !hi!  "), "hi")
