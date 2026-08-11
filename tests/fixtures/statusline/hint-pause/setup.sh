#!/usr/bin/env bash
# A window at 78% with drift on top: one hint at a time, and the one that names
# the costlier inaction. Losing the session beats losing the attribution.
set -eu
mkdir -p .flux
cat > .flux/session.json <<'JSON'
{
  "last_turn_at": "2026-08-10T12:00:00Z",
  "branch": "main",
  "head_sha": "abc1234",
  "dirty_files": 0,
  "drift_commits": 2,
  "claimed_ticket": "FLX-06",
  "last_done_ticket": "FLX-05",
  "last_synced_commit": "abc1234"
}
JSON
