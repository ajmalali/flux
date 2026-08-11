---
id: FLX-05
title: "Checkpoint: foundation works end-to-end on this machine"
status: open
agent: build
effort: low
blockers: [FLX-02, FLX-03, FLX-04]
checkpoint: human-verify
---
Spec: specs/harness/spec.md (AC-1..5, AC-13 partial).

## Context
Human-verify checkpoint (the PAUL format: what was built / how to verify / resume signal). The agent prepares everything mechanical; the human confirms the felt experience — hook injection and statusline can only be judged from a real session.

## Tasks
1. Files: (none — installation state)
   Action: install the plugin from the local marketplace (`/plugin marketplace add /Users/ajmalali/Dev/flux` → `/plugin install flux@flux`), add the statusLine setting from README, then print the verification script for the human:
   - open a NEW terminal in the flux repo → primed context block appears; statusline shows `— · flux · idle · ctx N%`
   - claim a ticket (set `status: claimed` in any ticket file) → new session: prime + statusline both show it
   - `/clear` → prime re-fires
   - make a commit with no ticket id in the message → next session shows the drift line
   Verify: human runs the four checks
   Done: human replies confirming all four; any failure becomes a new ticket blocking this one (AC-1..5)

## Test plan
This ticket IS the manual test plan for the foundation.

## Boundaries
Fix nothing in this ticket — failures spawn tickets. Keeps the checkpoint cheap and the fixes routed.
