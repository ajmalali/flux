"""What a cancellation is worth back.

Pure domain code: the moment of cancellation arrives as an argument, never from a
clock, and the tiers are data rather than a chain of hand-written comparisons so
that adding one cannot change the shape of the rule.
"""

from datetime import timedelta

from .pricing import round_half_up

# (minimum gap before the booking starts, refund percent). Highest tier first;
# boundaries belong to the more generous tier, so these are >= comparisons.
TIERS = (
    (timedelta(hours=48), 100),
    (timedelta(hours=24), 50),
    (timedelta(hours=2), 25),
)


def refund_percent(gap):
    """The percentage refunded for a cancellation ``gap`` ahead of the start."""
    for minimum, percent in TIERS:
        if gap >= minimum:
            return percent
    return 0


def refund_cents(price_cents, gap):
    """The refund on ``price_cents`` for a cancellation ``gap`` ahead of the start."""
    percent = refund_percent(gap)
    if percent == 0 or price_cents == 0:
        return 0
    if percent == 100:
        return price_cents
    return round_half_up(price_cents * percent, 100)


def refund_for(booking, cancelled_at):
    """The refund owed on ``booking`` if it is cancelled at ``cancelled_at``."""
    return refund_cents(booking.price_cents, booking.start - cancelled_at)
