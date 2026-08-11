---
id: FLX-21
title: Drift is visible to the human, not only to the model
status: done
agent: build
effort: low
blockers: [FLX-02, FLX-04, FLX-20]
checkpoint: none
---
Spec: specs/harness/spec.md (AC-1, AC-4, AC-5).

## Context
Found running FLX-05's check 4. Prime's drift line is a nudge — "N commits not
linked to tickets, run /sync" — addressed to a human who cannot see it. Claude
Code adds SessionStart stdout to the model's context and does not render it in
the terminal (hooks docs, exit-code-0 table, re-read 2026-08-11), which is
confirmed in this repo's own transcripts: the block arrives as a `hook_success`
attachment and never reaches the screen. The warning therefore fires only if the
model happens to mention it, which is the one thing a deterministic hook was
supposed to stop depending on.

The human's surface is the statusline. It already carries what is true right now
and nothing else, so drift belongs there — but only when there is drift, so the
common case stays as clean as it is today:

    FLX-20-done · main · ctx 41% · 83.6k
    FLX-20-done · main · ⚠ 2 drift · ctx 41% · 83.6k

Counting it there is out of the question: that is a git log per keystroke. The
count is resolved in the hooks, exactly as the ticket is (ADR-0006), and the
statusline only reads the number. Prime already computes it; the heartbeat must
learn to, so the count stays fresh across a session in which commits are made.

## Tasks
1. Files: bin/flux-common, bin/flux-prime
   Action: move `collect_drift` (and MAX_DRIFT_SCAN) into flux-common as
   `drift_count <root>`, returning a number and 0 whenever there is no usable
   baseline. Prime keeps printing its sentence from the same value.
   Verify: bash tests/run.sh prime
   Done: prime/drift still passes unchanged
2. Files: bin/flux-common, bin/flux-heartbeat, bin/flux-prime
   Action: add `drift_commits` to SESSION_KEYS as a second numeric field; both
   hooks stamp it. The baseline itself stays untouched — only /sync moves it.
   Verify: bash tests/run.sh heartbeat
   Done: session.json carries a live count after every turn
3. Files: bin/flux-statusline
   Action: render `⚠ N drift` between the branch and the ctx segment when the
   count is above zero, and nothing at all when it is zero or unreadable. Needs
   a numeric read for the no-jq path, where the existing sed_field only matches
   quoted values.
   Verify: bash tests/run.sh statusline
   Done: segment appears only when there is drift, jq or no jq
4. Files: tests/fixtures/{statusline,heartbeat}/
   Action: a statusline case with drift and one proving zero renders nothing; a
   heartbeat case pinning the stamped count against a real baseline.
   Verify: bash tests/run.sh
   Done: all suites green

## Test plan
The zero case matters as much as the non-zero one — a warning segment that is
always present is a warning nobody reads. Every existing statusline fixture is
already a zero case and must render exactly as before.

## Boundaries
No git and no store verb in the statusline (FLX-04). Do not touch
`last_synced_commit` (FLX-14 owns it). Do not change prime's sentence — the
model reads it, and it is the thing /sync will act on.
