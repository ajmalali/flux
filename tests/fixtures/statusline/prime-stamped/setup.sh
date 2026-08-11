#!/usr/bin/env bash
# session.json as prime writes it in a repo that has never seen a heartbeat:
# the claim and the last completion are real, every field only the heartbeat can
# fill is null. The line still renders — the ticket segment is the point, and
# the branch comes off disk, not out of this file.
set -eu
mkdir -p .flux
cat > .flux/session.json <<'JSON'
{
  "last_turn_at": null,
  "branch": null,
  "head_sha": null,
  "dirty_files": 0,
  "claimed_ticket": "FLX-19",
  "last_done_ticket": "FLX-18",
  "last_synced_commit": null
}
JSON
