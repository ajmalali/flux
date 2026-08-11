#!/usr/bin/env bash
# Work happened outside the harness. The count is already resolved — the hooks
# did the git walk — so the line only has to render it, between the branch and
# the context segment (FLX-21).
set -eu
mkdir -p .flux
cat > .flux/session.json <<'JSON'
{
  "last_turn_at": "2026-08-10T12:00:00Z",
  "branch": "main",
  "head_sha": "abc1234",
  "dirty_files": 0,
  "drift_commits": 2,
  "claimed_ticket": null,
  "last_done_ticket": "FLX-19",
  "last_synced_commit": "abc1234"
}
JSON
