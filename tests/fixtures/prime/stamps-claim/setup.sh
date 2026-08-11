#!/usr/bin/env bash
# The claim-outside-a-session sequence (FLX-19). The last session ended with
# FLX-02 claimed and a skill's own `status` on it; since then the human closed
# FLX-02 and claimed FLX-03 with no session running, so session.json is a turn
# behind reality and no heartbeat is coming to fix it before the first render.
set -eu
mkdir -p specs/harness/tickets
t() {
  cat > "specs/harness/tickets/$1.md" <<TICKET
---
id: $2
title: $3
status: $4
agent: $5
effort: low
blockers: [$6]
checkpoint: none
---
## Context
Fixture ticket.
TICKET
}
t 01-scaffold   FLX-01 "Scaffold plugin + self-hosted marketplace skeleton" done    chore ""
t 02-flux-prime FLX-02 "flux-prime — SessionStart state injection"          done    build "FLX-01"
t 03-heartbeat  FLX-03 "flux-heartbeat — Stop hook session stamp"           claimed build "FLX-02"
t 04-statusline FLX-04 "flux-statusline — worktree-aware status line"       open    chore "FLX-01"

mkdir -p .flux
cat > .flux/session.json <<'JSON'
{
  "last_turn_at": "2026-08-10T12:00:00Z",
  "branch": "main",
  "head_sha": "abc1234",
  "dirty_files": 0,
  "claimed_ticket": "FLX-02",
  "status": "qualifying",
  "next_ticket": "FLX-06",
  "last_synced_commit": "1111111"
}
JSON
