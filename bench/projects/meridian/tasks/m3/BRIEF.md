# Recurring weekly bookings

Members want a standing slot — "the Focus Room, Tuesdays 10–12, for the next eight
weeks" — without booking it eight times.

## 1. Bookings belong to a series

`Booking` gains `series_id: str = ""`. A one-off booking keeps `""`. Every booking
created as part of the same series shares one non-empty id, and two different
series never share one. It round-trips through the JSON store, and bookings stored
before this change still load.

`BookingRepository` gains `for_series(series_id)`, returning that series' bookings
in chronological order.

## 2. Creating a series

    BookingService.create_series(space_id, member_id, start, end, weeks,
                                 skip_conflicts=False) -> list[Booking]

- Occurrence `k` (0-based) runs from `start + 7k days` to `end + 7k days`.
- `weeks` must be an integer from 1 to 52 inclusive; anything else is a
  `ValidationError`.
- **Every occurrence is subject to the existing rules**: opening hours, and the
  changeover-buffer collision rule from the double-booking work. A series does not
  get to skip them.
- Default (`skip_conflicts=False`) is **all or nothing**: if any occurrence would
  collide with an existing confirmed booking, raise `ConflictError` and persist
  nothing at all — no partial series is left behind.
- With `skip_conflicts=True`, colliding occurrences are skipped and the rest are
  created. The returned list contains only what was created. If *every* occurrence
  collides, raise `ConflictError`.
- An occurrence outside opening hours raises `OutsideOpeningHours` regardless of
  `skip_conflicts` — the request itself is wrong, not merely unlucky.
- Each booking is priced individually by the existing pricing rules.
- The returned list is in chronological order.

## 3. Cancelling a series

    BookingService.cancel_series(series_id) -> list[Booking]

- Cancels every still-confirmed booking in the series, each refunded by the
  existing cancellation policy, evaluated against `clock.now()` per booking — so
  the near occurrence and the distant one can land in different refund tiers.
- Already-cancelled bookings in the series are left alone.
- An unknown `series_id` raises `NotFound`.
- A series with nothing left to cancel raises `ValidationError`.
- Returns the bookings it cancelled, in chronological order.

## 4. API

`GET /series/{series_id}` returns `{"series_id": ..., "bookings": [...]}` using the
existing booking serialisation, `404` when the series is unknown.

## Definition of done

- `python3 -m unittest discover -s tests` passes, with new tests covering the
  atomic-failure case, the skip case, and the mixed-refund cancellation.
- No new dependencies. Layering holds: the recurrence arithmetic and rule checks
  stay where the existing rules live, and `api` stays thin.
