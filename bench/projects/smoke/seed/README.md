# slugify

A tiny stdlib-only slug generator. `slugify(text)` lowercases, strips accents,
replaces runs of non-alphanumerics with a single hyphen, and trims hyphens
from both ends.

Run the tests with `python3 -m unittest discover -s tests`.
