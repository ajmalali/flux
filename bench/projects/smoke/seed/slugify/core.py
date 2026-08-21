"""Slug generation."""

import re
import unicodedata

_SEPARATORS = re.compile(r"[^a-z0-9]+")


def slugify(text):
    """Return a URL-safe slug for ``text``."""
    if text is None:
        raise TypeError("text must be a string")
    normalized = unicodedata.normalize("NFKD", str(text))
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii").lower()
    return _SEPARATORS.sub("-", ascii_only).strip("-")
