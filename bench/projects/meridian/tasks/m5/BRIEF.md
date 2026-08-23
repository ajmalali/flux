# Holds: a slot can be reserved for fifteen minutes before it is paid for

Members keep losing rooms while they check with a colleague. Sales wants a
**hold**: a short-lived claim on a slot that blocks everyone else, and either
becomes a real booking or quietly evaporates.

## 1. What a hold is

A hold is a booking record with a different status and an expiry.

- `meridian/domain/models.py` gains `HOLD = "hold"`, listed in `STATUSES`
  alongside `CONFIRMED` and `CANCELLED`.
- `Booking` gains `expires_at`, a timezone-aware UTC datetime, **defaulting to
  `None`**. Only holds carry one; a confirmed or cancelled booking has `None`.
- `Booking.is_hold` → `True` when the status is `HOLD`.
- `Booking.is_live_hold(now)` → `True` when it is a hold and `now` is before
  `expires_at`. Expiry is half-open like every other interval here: at exactly
  `expires_at` the hold is **over**.
- `Booking.is_active` keeps its current meaning — confirmed only. Do not widen it.

Expiry is **evaluated, never swept**: there is no background job and no
`expire_holds()` call. A hold that has run out simply stops counting, everywhere,
the moment the clock passes it.

`expires_at` round-trips through the JSON store like every other datetime:
ISO-8601 on disk, aware UTC in memory, `null` when absent.

## 2. Creating, confirming, releasing

All three live on `BookingService` (`meridian/service/booking.py`):

    hold_space(space_id, member_id, start, end, minutes=15) -> Booking
    confirm_hold(hold_id) -> Booking
    release_hold(hold_id) -> Booking

- **`hold_space`** validates exactly what `create_booking` validates — unknown
  space or member → `NotFound`, a malformed interval → `ValidationError`,
  outside opening hours → `OutsideOpeningHours` — then records a booking with
  status `HOLD`, `created_at` and `expires_at` both taken from the injected
  clock (`expires_at = clock.now() + minutes`), and the price the existing
  `quote` returns for that interval. `minutes` must be a positive integer;
  anything else is a `ValidationError`.
- **`confirm_hold`** turns a live hold into a confirmed booking: same id, same
  interval, **the price quoted when the hold was taken**, `expires_at` back to
  `None`. A hold that has expired → `ConflictError`. A record that is not a hold
  → `ValidationError`. No such id → `NotFound`.
- **`release_hold`** gives the slot back: the record becomes `CANCELLED` with
  `expires_at` `None`, whether the hold was live or already expired. Not a hold
  → `ValidationError`. No such id → `NotFound`.

## 3. A live hold occupies the room

- `hold_space` raises `ConflictError` when the requested interval overlaps a
  **live hold** for that space.
- `create_booking` raises `ConflictError` in the same situation.
- An **expired** hold blocks nothing, and a **released** hold blocks nothing.
- A hold occupies exactly its own interval — no changeover buffer, no rounding.

This phase adds the hold rule and nothing else. Whatever the repository does
today about two *confirmed* bookings overlapping is out of scope: do not change
it in either direction.

## 4. Availability has to know the time

`domain` stays pure (CLAUDE.md: no clock reads, anything time-dependent takes the
time as an argument), so the two availability queries take the moment to judge
expiry against, as a trailing optional argument:

    free_slots(space, bookings, day, now=None) -> [Interval]
    is_free(space, bookings, interval, now=None) -> bool

- With a `now`, a live hold is busy and an expired one is not.
- With `now=None`, **every hold counts as live** — the safe reading, and the one
  a caller that has no clock should get.
- Cancelled records occupy nothing, exactly as now.

## 5. What the ticket says about reporting

> "Reporting already shares the availability rule, so once holds carry their own
> status the utilisation report will skip them automatically."
> — the note attached to the ticket

Do not take that on trust; check it against the code before you rely on it.

The requirement, either way: **a hold is never utilisation.** A live hold is time
the room is *unavailable*, which is a different question from whether it was
*used* — the same distinction the changeover buffer already draws. Live, expired
or released, a hold contributes zero to `utilization` (and to
`utilization_by_space` if that function exists in this tree).

## 6. Over the API

`meridian/api/handlers.py`, thin as ever — parse, delegate, serialise:

- `POST /spaces/{space_id}/holds`, body `{"member_id": ..., "start": ...,
  "end": ..., "minutes": 15}` (`minutes` optional)
  → `201` with the booking JSON
  → `404` unknown space or member · `409` `ConflictError` · `400` any other
    `MeridianError`
- `POST /holds/{booking_id}/confirm` → `200` with the booking JSON ·
  `404` unknown id · `409` expired · `400` not a hold
- `POST /holds/{booking_id}/release` → `200` with the booking JSON ·
  `404` unknown id · `400` not a hold

`start` and `end` arrive as ISO-8601 strings. `booking_json` gains an
`expires_at` key: the ISO-8601 string for a hold, `null` for anything else.

## Definition of done

- `python3 -m unittest discover -s tests` passes, and the tests you add cover
  expiry at the boundary, the conflict rule, the store round-trip, and what a
  hold does to the utilisation report.
- No new dependencies. Layering unchanged: the rule lives in `domain`/`service`,
  never in `api` or `store`.
- Nothing calls `datetime.now()`; the clock is the injected one.
