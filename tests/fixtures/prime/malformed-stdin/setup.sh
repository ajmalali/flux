#!/usr/bin/env bash
# Same store as nothing-claimed; stdin is broken JSON, so prime falls back to $PWD.
set -eu
mkdir -p specs/harness/tickets
cat > specs/harness/tickets/02-flux-prime.md <<'TICKET'
---
id: FLX-02
title: flux-prime — SessionStart state injection
status: open
agent: build
effort: medium
blockers: []
checkpoint: none
---
## Context
Fixture ticket.
TICKET
