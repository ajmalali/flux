#!/usr/bin/env bash
# Four tickets: one done, one claimed, one blocked by the claimed one, one ready.
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
t 01-scaffold      FLX-01 "Scaffold plugin + self-hosted marketplace skeleton" "done"    chore ""
t 02-flux-prime    FLX-02 "flux-prime — SessionStart state injection"          claimed build "FLX-01"
t 03-heartbeat     FLX-03 "flux-heartbeat — Stop hook session stamp"           open    build "FLX-02"
t 04-statusline    FLX-04 "flux-statusline — worktree-aware status line"       open    chore "FLX-01"
