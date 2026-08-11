---
id: FLX-20
title: Statusline names the last completed ticket, not a guess at the next one
status: done
agent: build
effort: low
blockers: [FLX-04, FLX-17, FLX-19]
checkpoint: none
---
Spec: specs/harness/spec.md (AC-4).

## Context
FLX-17 made the idle statusline read `FLX-06-unclaimed`, on the principle that
the line should always point at work. Using it says otherwise: the frontier head
is a derived guess, not a fact. It changes when a blocker closes, when a ticket
is filed above it, or when the human decides a lower-numbered blocked ticket
matters more — the FLX-19 → FLX-05 case, where the rule's answer (FLX-06) and
the right answer were different. A statusline that keeps naming a ticket nobody
committed to trains you to ignore it, and it is on screen constantly.

What is idle-time true is what was last finished. It is a fact, not a
projection; it does not move under you; and it answers the question you actually
have in a fresh terminal — where did I get to. The frontier keeps living in
prime's block, where it is shown as a list of several and its uncertainty is
visible.

"Most recent" is the work here. The markdown store has no timestamps, so recency
comes from git: the newest commit message naming a ticket whose status is done —
which is exactly this repo's convention (a ticket ends in a commit carrying its
id). Beads has real close timestamps and should use them. Neither should cost
the statusline anything: this resolves in the hooks, same as `next_ticket` did.

## Tasks
1. Files: bin/flux-common
   Action: add a `store_done` verb returning `id \t title` for the most recently
   completed ticket — beads sorted by close time, markdown resolved through
   `git log`, degrading to the last done ticket in file order outside a repo.
   Move `TICKET_ID_RE` here from bin/flux-prime; both now need it.
   Verify: bash tests/run.sh heartbeat
   Done: verb resolves out-of-order completions correctly (FLX-19 after FLX-13)
2. Files: bin/flux-heartbeat, bin/flux-prime, bin/flux-statusline
   Action: replace `next_ticket` with `last_done_ticket` in SESSION_KEYS and in
   both writers; the statusline renders `FLX-19-done` where it rendered
   `FLX-06-unclaimed`, and still `no tickets` when the store has neither a claim
   nor a completion.
   Verify: bash tests/run.sh
   Done: no reader or writer of `next_ticket` remains
3. Files: tests/fixtures/{heartbeat,statusline,prime}/
   Action: retarget the fixtures that pin the frontier head — heartbeat's
   next-ticket case becomes a last-done case with out-of-order commits, and the
   statusline's unclaimed case becomes the done case.
   Verify: bash tests/run.sh
   Done: all suites green, none still asserting on next_ticket
4. Files: README.md, docs/adr/, specs/harness/tickets/05-foundation-checkpoint.md
   Action: correct the README's "always points at work" paragraph and its sample
   lines; record the reversal as an ADR so the next reader does not restore
   `next_ticket` as an oversight; fix FLX-05's check 1, which quotes the old
   `FLX-NN-unclaimed` format.
   Verify: grep -r unclaimed README.md specs/ docs/ returns only the ADR's
   account of the old behaviour
   Done: no document still promises the frontier head in the status line

## Test plan
The heartbeat suite carries the interesting case: a repo whose most recent
ticket commit is not its highest-numbered ticket, proving recency comes from git
rather than from file order.

## Boundaries
Do not touch prime's frontier block — it lists several tickets and shows its own
uncertainty. Do not make the statusline resolve anything itself (FLX-04).
