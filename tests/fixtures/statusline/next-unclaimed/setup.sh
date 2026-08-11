#!/usr/bin/env bash
# Nothing claimed, but the heartbeat cached a frontier head. The line names the
# ticket that is next up rather than going blank — idle still points at work.
set -eu
mkdir -p .flux
cat > .flux/session.json <<'JSON'
{
  "last_turn_at": "2026-08-10T12:00:00Z",
  "branch": "main",
  "head_sha": "abc1234",
  "dirty_files": 0,
  "claimed_ticket": null,
  "next_ticket": "FLX-06",
  "last_synced_commit": "abc1234"
}
JSON
