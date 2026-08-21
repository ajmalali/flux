# No double-booking, with a per-space changeover buffer

Meridian currently lets two members book the same space at the same time. It also
has no notion of the changeover time a space needs between bookings.

## 1. Spaces get a changeover buffer

`Space` gains a field `buffer_minutes: int = 0` — the minutes a space needs after a
booking ends before it can be occupied again. It must round-trip through the JSON
store like every other field, and existing stored spaces without the field must
still load (defaulting to `0`).

## 2. Two confirmed bookings in the same space must not collide

A confirmed booking occupies its own interval **and** the `buffer_minutes` that
follow it. Two confirmed bookings in the same space collide when those occupied
windows overlap — where "overlap" is the existing half-open rule, so windows that
merely touch do not collide.

Concretely, for bookings A and B in the same space, they collide when
`overlaps(A.start, A.end + buffer, B.start, B.end + buffer)`. Note this is
order-independent: it does not matter which was booked first.

Examples for a space with `buffer_minutes = 15`:

| existing | requested | outcome |
|---|---|---|
| 10:00–12:00 | 12:15–13:00 | allowed — exactly 15 minutes of changeover |
| 10:00–12:00 | 12:10–13:00 | rejected — only 10 minutes |
| 10:00–12:00 | 12:00–13:00 | rejected — no changeover at all |
| 10:00–12:00 | 09:00–10:00 | rejected — the earlier booking's own buffer runs into 10:00 |
| 10:00–12:00 | 08:00–09:30 | allowed |

With `buffer_minutes = 0`, back-to-back bookings (10:00–12:00 then 12:00–13:00)
are allowed, exactly as half-open intervals imply.

Cancelled bookings occupy nothing — neither their interval nor a buffer.
Bookings in *other* spaces are irrelevant.

## 3. Where the rule lives

The rule is a domain rule. `meridian/domain/availability.py` owns it: the
functions that compute what is occupied and whether an interval is free must
account for the buffer, and `free_slots` must subtract the buffer along with the
booking. The service layer calls the domain; it does not reimplement the
comparison. (See CLAUDE.md — `domain` stays pure and one-directional.)

## 4. Behaviour at the service layer

- `BookingService.create_booking` raises `ConflictError` when the request collides
  with an existing confirmed booking in that space. The message must name the id
  of the booking it collided with.
- `BookingService.reschedule_booking` applies the same rule, but a booking never
  collides with itself.
- Opening-hours validation is unchanged and still takes precedence: a request
  outside opening hours raises `OutsideOpeningHours` whether or not it also
  collides.

## Definition of done

- `python3 -m unittest discover -s tests` passes, with new tests covering the
  rule (including the buffer boundary cases above).
- No new dependencies. Layering and the money/time conventions in CLAUDE.md hold.
