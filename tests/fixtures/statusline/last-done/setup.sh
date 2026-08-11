#!/usr/bin/env bash
# Nothing claimed, so the line names the last ticket finished. Idle still says
# something true — where the work got to — without asserting what comes next
# (ADR-0006).
set -eu
mkdir -p .flux
cat > .flux/session.json <<'JSON'
{
  "last_turn_at": "2026-08-10T12:00:00Z",
  "branch": "main",
  "head_sha": "abc1234",
  "dirty_files": 0,
  "claimed_ticket": null,
  "last_done_ticket": "FLX-19",
  "last_synced_commit": "abc1234"
}
JSON
