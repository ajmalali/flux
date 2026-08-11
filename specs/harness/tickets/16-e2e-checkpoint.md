---
id: FLX-16
title: "Checkpoint: full loop dogfooded on a real feature"
status: open
agent: build
effort: low
blockers: [FLX-08, FLX-09, FLX-10, FLX-11, FLX-12, FLX-13, FLX-14]
checkpoint: human-verify
---
Spec: specs/harness/spec.md (all ACs).

## Context
The harness is done when it has carried one real, small feature end-to-end on a real repo (a zaps repo or a sandbox) — not when its parts pass their own tests. Human-verify: the felt experience is the acceptance criterion.

## Tasks
1. Files: (none)
   Action: guide the human through the loop on a feature of their choice: /flux-init on the target repo → /plan → (fresh session) /tickets → /build one ticket → /show-work → deliberately make one raw commit → next session shows drift → /sync. Collect friction notes at each step.
   Verify: human completes the loop
   Done: human confirms each step; every friction note becomes a ticket with `discovered-from: FLX-16` (ACs 1-11, 13)

## Test plan
This ticket is the acceptance test for the project.

## Boundaries
Fix nothing here — friction becomes tickets. /run (FLX-15) is deliberately absent from this loop; it gets its own live verify.
