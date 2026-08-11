#!/usr/bin/env bash
# Markdown tickets exist, but bd is installed — the beads answer must win.
set -eu
mkdir -p specs/harness/tickets
cat > specs/harness/tickets/01-ignored.md <<'TICKET'
---
id: FLX-99
title: Markdown fallback must not be used here
status: open
agent: build
effort: low
blockers: []
checkpoint: none
---
## Context
Fixture ticket.
TICKET
