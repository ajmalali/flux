---
id: FLX-22
title: Prime asks for a relay, and the counts read as English
status: done
agent: chore
effort: low
blockers: [FLX-21]
checkpoint: none
---
Spec: specs/harness/spec.md (AC-1, AC-4), ADR-0007.

## Context
Two things, both from watching FLX-21 land.

The counts do not agree with their nouns: `⚠ 1 drift` is right and `⚠ 2 drift`
is not, and prime says "1 commits not linked to tickets". Small, but this is the
line the human reads every second of every session, and broken agreement is what
makes a tool feel unmaintained.

Second, ADR-0007 says the primed block is invisible to the human and concludes
that anything needing human action goes to the status line. That holds for
standing state, but it leaves the block itself unread by anyone but the model —
and the block carries things the status line has no room for, handoffs above
all. Prime can close that gap itself: it writes into the model's context, so it
can ask the model to relay. One line, at the top of the first reply, naming only
what needs a person. Note the ceiling honestly — Claude Code produces no turn
before the user types, so the relay lands atop the answer to the first prompt,
not on the empty screen.

## Tasks
1. Files: bin/flux-statusline, bin/flux-prime
   Action: agree the noun with the count — `⚠ 1 drift` / `⚠ 2 drifts`, and
   "1 commit not linked to tickets" / "2 commits not linked to tickets".
   Verify: bash tests/run.sh statusline prime
   Done: both singular and plural pinned by fixtures
2. Files: bin/flux-prime
   Action: close the block with one line asking the model to relay the state to
   the user in its first reply, since the user cannot see the block.
   Verify: bash tests/run.sh prime
   Done: the line is present whenever prime prints anything at all
3. Files: tests/fixtures/prime/*, tests/fixtures/statusline/
   Action: every prime fixture's expected.txt gains the relay line; add a
   singular-drift statusline case beside the plural one.
   Verify: bash tests/run.sh
   Done: all suites green

## Test plan
The singular cases are the point — the plural ones already pass by accident.

## Boundaries
The relay is one line and asks for one line back. It must not turn into a
session-opening monologue: the status line already carries standing state, and
the block is for the model's orientation first.
