# Fix the utilisation report, and break it down by space

## 1. The bug

Operations does not trust the daily utilisation number any more.

On 2026-09-01 the Focus Room (open 08:00–20:00, so twelve hours) had three
bookings of three hours each. Two of them were cancelled. The room was therefore
occupied for three of its twelve open hours — 25%.

`python3 -m meridian.cli utilization --space s-focus --day 2026-09-01` reports
**75.0**.

Reproduce it, find the cause, fix it, and leave a regression test behind that
would have caught it.

## 2. While you are in there: what counts as utilised

Make this explicit in the code and in a test, because it is currently ambiguous:
utilisation measures the time a space was **occupied**, not the time it was
**unavailable**. The changeover buffer introduced with the double-booking rule
blocks the room from being rebooked, but it is not utilisation and must not be
counted.

## 3. Break it down by space

    meridian.service.reporting.utilization_by_space(repos, day) -> dict

Returns `{space_id: percent}` for **every** space known to the store, including
spaces with no bookings at all (`0.0`). Percentages follow the existing rule: one
decimal place, computed against that space's own opening hours — the Studio's day
is nine hours, not twelve.

## 4. Expose it over the API

- `GET /spaces/{space_id}/utilization?day=YYYY-MM-DD`
  → `200 {"space_id": ..., "day": "YYYY-MM-DD", "percent": 25.0}`
  → `404` when the space is unknown
  → `400` when `day` is missing, or is not a `YYYY-MM-DD` date
- `GET /utilization?day=YYYY-MM-DD`
  → `200 {"day": "YYYY-MM-DD", "spaces": {space_id: percent, ...}}`
  → `400` on the same bad input

The date is a plain UTC calendar date. `api` stays thin: parsing and formatting
only, with the reporting rule left in `service`.

## Definition of done

- `python3 -m unittest discover -s tests` passes, including a regression test for
  the bug and a test pinning the buffer decision.
- No new dependencies. The CLI's existing `utilization` command keeps working.
