# Bay 2 was double-booked back to back

Ops escalated this on 1 September.

Bay 2 is configured with a fifteen-minute changeover. Two confirmed bookings
ended up in it with nothing in between — 09:00–10:00 and 10:00–11:00 — so the
second member walked in while the first was still packing up.

Nobody edited the data by hand, and nothing errored. What the audit log shows,
in order:

1. 09:00–10:00 in Bay 2 was put on hold.
2. 10:00–11:00 in Bay 2 was booked by a different member.
3. The hold from step 1 was confirmed.

Every one of those went through the normal flow and every one was accepted.

## What we want

It must not be possible to end up in that state. Refuse whichever step would
create it, and refuse it the way this system already refuses a slot that is
taken — ops read those errors, and the HTTP status matters to the front end.

We are not telling you where the fix goes or what the rule is. The rule this
violates is already in this codebase and is already enforced everywhere else;
find it, and find the path that gets around it.

## Constraints

- **Do not change what a hold claims while it is still only a hold.** That was
  settled in the previous phase and it is not what went wrong here.
- A space with **no** changeover configured must still allow back-to-back
  bookings. Do not over-correct.
- Holds that have expired or been released still claim nothing.

## Definition of done

- `python3 -m unittest discover -s tests` passes, and the tests you add cover
  the sequence above.
- No new dependencies. The layering rules in `CLAUDE.md` still hold: the rule
  lives in `domain`/`service`, never in `api` or `store`.
