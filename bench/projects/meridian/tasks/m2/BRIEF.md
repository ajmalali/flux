# Cancellation policy with tiered refunds

Cancelling a booking currently just flips its status. Members are refunded by hand.
Meridian needs a policy.

## 1. The tiers

The refund depends on how far ahead of the booking's **start** the cancellation
happens. Let `gap = booking.start - cancelled_at`.

| gap | refund |
|---|---|
| 48 hours or more | 100% of `price_cents` |
| 24 hours or more, but under 48 | 50% |
| 2 hours or more, but under 24 | 25% |
| under 2 hours, including after the booking has started | 0% |

Boundaries belong to the **more generous** tier: a gap of exactly 48 hours refunds
100%, exactly 24 hours refunds 50%, exactly 2 hours refunds 25%.

Refunds are integer cents, rounded **half up** at the cent. `meridian/domain/pricing.py`
already has `round_half_up` — use it rather than a second rounding rule.

## 2. Where it lives

A new module `meridian/domain/policy.py` owns the tiers and the arithmetic. It is
domain code: pure, no clock reads, no I/O. The time of cancellation is passed in.

## 3. What changes elsewhere

- `Booking` gains `refund_cents: int = 0`. A confirmed booking always has `0`.
  It must round-trip through the JSON store, and bookings stored before this
  change must still load.
- `BookingService.cancel_booking` computes the refund against `clock.now()`,
  records it on the cancelled booking, and persists it. It still refuses to
  cancel an already-cancelled booking with `ValidationError`.
- Cancelling a booking whose start has already passed is allowed, and refunds `0`.
- The cancel endpoint's JSON body includes `refund_cents`, as does every other
  place a booking is serialised.

## Definition of done

- `python3 -m unittest discover -s tests` passes, with new tests covering each
  tier and both sides of each boundary.
- No new dependencies; `domain` stays pure; money stays in integer cents.
