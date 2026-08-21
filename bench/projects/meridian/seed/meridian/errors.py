"""Every failure Meridian signals deliberately.

Bare exceptions and ``None``-as-failure are banned (see CLAUDE.md): a caller
must be able to tell "the space does not exist" from "the space is not free"
without parsing a message.
"""


class MeridianError(Exception):
    """Base class for everything this package raises on purpose."""


class NotFound(MeridianError):
    """A referenced entity does not exist."""


class ValidationError(MeridianError):
    """The request is malformed or self-contradictory."""


class OutsideOpeningHours(ValidationError):
    """The requested interval falls outside the space's opening hours."""


class ConflictError(MeridianError):
    """The request is well-formed but cannot be satisfied by current state."""
