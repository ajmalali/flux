---
id: FLX-23
title: The status line names the verb, but only when there is one to name
status: done
agent: build
effort: low
blockers: [FLX-21, FLX-22]
checkpoint: none
---
Spec: specs/harness/spec.md (AC-4), ADR-0007.

## Context
The line reports state accurately and leaves the reader to know what to do about
it. `⚠ 2 drift` assumes you remember that /sync is the answer; a window at 78%
assumes you think to pause before it costs you the session. The harness has the
verbs, so the line can name one.

It names at most one, and only when there is something to act on — the same rule
that keeps the drift segment off the line the rest of the time. A hint that is
always present is furniture, and furniture is not read. Priority is by cost of
inaction: a full context window loses the session, drift only loses
attribution.

    FLX-06-claimed · main · ctx 78% · 140k · /pause
    FLX-21-done · main · ⚠ 2 drift · ctx 41% · 82.4k · /sync
    FLX-06-claimed · main · ctx 41% · 82.4k

Both verbs are unbuilt (FLX-13, FLX-14). Naming them anyway is deliberate and
already the precedent — prime's block has said "run /sync when convenient" since
FLX-02. The pluralisation added in FLX-22 comes back out at the same time:
`drift` is the condition the commits add up to, and it does not take an -s.

## Tasks
1. Files: bin/flux-statusline
   Action: append ` · <verb>` when a condition warrants one — context at or over
   HINT_CTX_PCT → /pause, else drift → /sync, else nothing. Arithmetic only: no
   new file reads, no forks, both inputs are already in hand.
   Verify: bash tests/run.sh statusline
   Done: hint present only under those conditions, and never two at once
2. Files: tests/fixtures/statusline/
   Action: cases for each hint, for the priority order when both fire, and the
   silence of the steady state. Retarget the two drift fixtures, which now end
   in the verb.
   Verify: bash tests/run.sh
   Done: every existing case still renders unchanged apart from those two
3. Files: README.md, specs/harness/spec.md
   Action: document the rule, not the list — the list will grow with the skills.
   Verify: grep for `drifts` returns nothing outside FLX-22's own record
   Done: AC-4 describes hints and the plural is gone everywhere

## Test plan
The steady-state case is the one that matters: two existing fixtures already
assert a line with no hint, and they must not move.

## Boundaries
No new reads in the statusline (FLX-04): a hint that needs data the hooks have
not already stamped is a hint for a later ticket. Unconsumed handoffs are the
obvious next candidate and are deliberately left out — no verb consumes one yet,
and pointing at a verb we have not chosen is the guessing ADR-0006 removed.
