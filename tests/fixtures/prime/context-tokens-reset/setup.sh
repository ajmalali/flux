#!/usr/bin/env bash
# A window that has just been cleared. session.json still holds the count the
# last session ended on — 412000, well past both budget marks — and the event
# points at a transcript this new window has not written yet.
#
# The count must come back null. Left alone it would be inherited, and the first
# /plan round boundary in a window holding almost nothing would report 412k and
# recommend stopping (FLX-63o). A stale number is worse than no number: nothing
# about it looks wrong.
set -eu
mkdir -p .flux
cat > .flux/session.json <<'JSON'
{
  "last_turn_at": "2026-08-10T12:00:00Z",
  "branch": "main",
  "head_sha": "abc1234",
  "dirty_files": 0,
  "drift_commits": 0,
  "context_tokens": 412000,
  "claimed_ticket": null,
  "last_done_ticket": null,
  "last_synced_commit": "1111111"
}
JSON
