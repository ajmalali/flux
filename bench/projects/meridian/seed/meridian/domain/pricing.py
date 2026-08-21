"""What a booking costs.

Money is integer cents everywhere. The only rounding in the system happens here,
in :func:`quote`, and it happens once — a discount applied to an already-rounded
block price, rounded half-up to the cent.
"""

from ..errors import ValidationError
from .models import PLAN_PRO

BLOCK_MINUTES = 15
MINIMUM_MINUTES = 60
PRO_DISCOUNT_PERCENT = 10


def billable_minutes(interval):
    """Chargeable minutes: rounded up to a whole block, never below the minimum."""
    minutes = interval.minutes
    if minutes <= 0:
        raise ValidationError("cannot price an empty interval")
    blocks = (minutes + BLOCK_MINUTES - 1) // BLOCK_MINUTES
    return max(blocks * BLOCK_MINUTES, MINIMUM_MINUTES)


def round_half_up(numerator, denominator):
    """Integer division rounding .5 away from zero. Explicit, because money."""
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    return (numerator * 2 + denominator) // (denominator * 2)


def quote(space, member, interval):
    """Price ``interval`` in ``space`` for ``member``, in cents."""
    minutes = billable_minutes(interval)
    gross = round_half_up(space.hourly_cents * minutes, 60)
    if member.plan == PLAN_PRO:
        discount = round_half_up(gross * PRO_DISCOUNT_PERCENT, 100)
        return gross - discount
    return gross
