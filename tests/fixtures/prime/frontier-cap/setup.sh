#!/usr/bin/env bash
# Seven ready tickets: prime lists five and summarises the rest.
set -eu
mkdir -p specs/harness/tickets
for n in 1 2 3 4 5 6 7; do
  cat > "specs/harness/tickets/0$n-fixture.md" <<TICKET
---
id: FLX-0$n
title: Fixture ticket $n
status: open
agent: chore
effort: low
blockers: []
checkpoint: none
---
## Context
Fixture ticket.
TICKET
done
