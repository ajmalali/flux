#!/usr/bin/env bash
# One drifted commit: the noun has to agree with the count (FLX-22). The plural
# case passes by accident, so this is the one worth pinning.
set -eu
mkdir -p .flux
cat > .flux/session.json <<'JSON'
{
  "last_turn_at": "2026-08-10T12:00:00Z",
  "branch": "main",
  "head_sha": "abc1234",
  "dirty_files": 0,
  "drift_commits": 1,
  "claimed_ticket": null,
  "last_done_ticket": "FLX-19",
  "last_synced_commit": "abc1234"
}
JSON
