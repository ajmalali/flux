#!/usr/bin/env bash
# Session state exists, but no ticket is claimed — the heartbeat writes null.
set -eu
mkdir -p .flux
cat > .flux/session.json <<'JSON'
{
  "last_turn_at": "2026-08-10T12:00:00Z",
  "branch": "main",
  "head_sha": "abc1234",
  "dirty_files": 2,
  "claimed_ticket": null,
  "last_synced_commit": "abc1234"
}
JSON
