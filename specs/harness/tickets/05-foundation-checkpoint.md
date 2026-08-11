---
id: FLX-05
title: "Checkpoint: foundation works end-to-end on this machine"
status: done
agent: build
effort: low
blockers: [FLX-02, FLX-03, FLX-04, FLX-18, FLX-19, FLX-20]
checkpoint: human-verify
---
Spec: specs/harness/spec.md (AC-1..5, AC-13 partial).

## Context
Human-verify checkpoint (the PAUL format: what was built / how to verify / resume signal). The agent prepares everything mechanical; the human confirms the felt experience — hook injection and statusline can only be judged from a real session.

## Tasks
1. Files: (none — installation state)
   Action: install the plugin from the local marketplace (`/plugin marketplace add /Users/ajmalali/Dev/flux` → `/plugin install flux@flux`), add the statusLine setting from README, then print the verification script for the human:
   - open a NEW terminal in the flux repo → primed context block appears; statusline shows `FLX-NN-done · main · ctx N% · 83.6k`, naming the last ticket finished (the format FLX-20 settled on — see README, not the older `FLX-NN-unclaimed` or `— · flux · idle` lines)
   - claim a ticket (set `status: claimed` in any ticket file) → new session: prime + statusline both show it, and the statusline is right on its FIRST render, before any turn has ended — that is the check that failed here last time and became FLX-19
   - `/clear` → prime re-fires
   - drift: `git commit --allow-empty -m "wip: no ticket id here"` → next session shows `1 commits not linked to tickets` → drop it with `git reset --soft HEAD~1`. The probe has to be a commit prime has never seen a ticket id in, and it has to go afterwards rather than stay, because only /sync (FLX-14, not built yet) advances `last_synced_commit` — left in place it warns forever. Use `--soft`, not `--hard`: the probe commit is empty, so soft removes it and touches neither the index nor the working tree. The earlier version of this script said `--hard` and cost this repo two tickets' worth of uncommitted work.
   Verify: human runs the four checks
   Done: human replies confirming all four; any failure becomes a new ticket blocking this one (AC-1..5)

## Result — 2026-08-11
Closed. What each check was verified by, since they were not all verified the
same way and the difference matters to anyone reading this later:

1. Fresh session — human, in a real terminal. Status line rendered. The primed
   block was not seen and cannot be: SessionStart stdout goes to the model's
   context and is never printed (ADR-0007, found here). Confirmed instead from
   this repo's transcript, where the block arrives as a `hook_success`
   attachment. Three tickets came out of this check: FLX-21, FLX-22, FLX-23.
2. Claim outside a session — run against the real ticket store rather than a
   fixture: claimed FLX-06 from a shell, statusline stale beforehand, prime
   fired, first render read `FLX-06-claimed` with no heartbeat between. The
   FLX-19 regression is closed. Not repeated inside a live session, because
   checks 1 and 3 already establish that the hook fires there.
3. `/clear` re-fires prime — human, and confirmed in the transcript as
   `hookName: SessionStart:clear`.
4. Drift — both halves. Two probe commits produced `⚠ 2 drift · … · /sync` on
   the status line; removing them cleared the segment and the hint unprompted.

## Test plan
This ticket IS the manual test plan for the foundation.

## Boundaries
Fix nothing in this ticket — failures spawn tickets. Keeps the checkpoint cheap and the fixes routed.
