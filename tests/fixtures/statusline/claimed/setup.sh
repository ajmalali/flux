#!/usr/bin/env bash
# A heartbeat-shaped session.json with a ticket claimed.
set -eu
mkdir -p .flux
cat > .flux/session.json <<'JSON'
{
  "last_turn_at": "2026-08-10T12:00:00Z",
  "branch": "main",
  "head_sha": "abc1234",
  "dirty_files": 0,
  "claimed_ticket": "FLX-04",
  "last_synced_commit": "abc1234"
}
JSON
