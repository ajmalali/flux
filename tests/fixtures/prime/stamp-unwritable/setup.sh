#!/usr/bin/env bash
# A .flux/ prime cannot write into. The stamp is a courtesy, not the job: the
# block still prints, the exit is still 0 (ADR-0001), and the stale session.json
# is left exactly as it was rather than half-written.
set -eu
mkdir -p specs/harness/tickets
cat > specs/harness/tickets/02-flux-prime.md <<'TICKET'
---
id: FLX-02
title: flux-prime — SessionStart state injection
status: claimed
agent: build
effort: low
blockers: []
checkpoint: none
---
## Context
Fixture ticket.
TICKET

mkdir -p .flux
cat > .flux/session.json <<'JSON'
{
  "last_turn_at": "2026-08-10T12:00:00Z",
  "claimed_ticket": "FLX-01",
  "next_ticket": null,
  "last_synced_commit": "1111111"
}
JSON
chmod 0500 .flux
