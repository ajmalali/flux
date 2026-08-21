"""Slug generation."""

import re
import unicodedata

_SEPARATORS = re.compile(r"[^a-z0-9]+")


def slugify(text, max_length=None):
    """Return a URL-safe slug for ``text``, optionally capped at ``max_length``."""
    if text is None:
        raise TypeError("text must be a string")
    normalized = unicodedata.normalize("NFKD", str(text))
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = _SEPARATORS.sub("-", ascii_only).strip("-")
    if max_length is None:
        return slug
    if max_length <= 0:
        raise ValueError("max_length must be a positive integer")
    if len(slug) <= max_length:
        return slug
    words = slug.split("-")
    kept = []
    for word in words:
        candidate = "-".join(kept + [word])
        if len(candidate) > max_length:
            break
        kept.append(word)
    if kept:
        return "-".join(kept)
    return words[0][:max_length].rstrip("-")
