#!/usr/bin/env bash
# The common case, pinned on purpose: an explicit zero renders no segment at
# all. A warning that is always on the line is a warning nobody reads.
set -eu
mkdir -p .flux
cat > .flux/session.json <<'JSON'
{
  "last_turn_at": "2026-08-10T12:00:00Z",
  "branch": "main",
  "head_sha": "abc1234",
  "dirty_files": 3,
  "drift_commits": 0,
  "claimed_ticket": "FLX-21",
  "last_done_ticket": "FLX-20",
  "last_synced_commit": "abc1234"
}
JSON
