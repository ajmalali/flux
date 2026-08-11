---
id: FLX-13
title: Fix TSV row splitting in prime — empty fields collapse
status: done
agent: build
effort: low
blockers: [FLX-02, FLX-04]
checkpoint: none
---
Spec: specs/harness/spec.md (AC-2). Bug found while building FLX-04.

## Context
The store verbs in `bin/flux-common` emit tab-separated rows and prime reads them
with `IFS=$'\t' read -r a b c`. That is wrong: tab is IFS *whitespace*, so a run
of tabs counts as one separator and an empty field shifts every later field left.
A ticket whose frontmatter has no `agent` makes prime print the title as the tier:

    FLX-01 [Ticket with no agent field]

instead of `FLX-01 Ticket with no agent field`. Any row with an empty middle
column has the same problem.

Tabs stay the wire format — `@tsv` escapes tabs and newlines inside values, which
a raw separator does not. What changes is how rows are read. `split_row` already
landed in flux-common with FLX-04 (statusline reads its rows through it); prime is
the remaining caller still splitting rows with `read`.

## Tasks
1. Files: bin/flux-prime
   Action: read rows with `IFS= read -r` + `split_row` in all three loops —
   claimed, frontier, handoffs.
   Verify: bash tests/run.sh
   Done: a ticket with no `agent` renders `FLX-01 Ticket with no agent field`,
   every existing fixture still passes, shellcheck clean (AC-2)
2. Files: tests/fixtures/prime/missing-agent/
   Action: fixture with one agent-less and one routed open ticket.
   Verify: bash tests/run.sh prime
   Done: fails against the pre-fix prime, passes after — locks the untiered row

## Test plan
Fixtures: prime with an agent-less ticket (new); the whole existing prime,
heartbeat and statusline suites as the regression net.

## Boundaries
Reading only — no change to what the store verbs emit, no new fields, no beads
schema work. Heartbeat's `cut -f1` is already correct; leave it alone.
