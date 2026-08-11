#!/usr/bin/env bash
# A ticket whose frontmatter has no `agent`: the routing tier is empty, and the
# row must still split into id / tier / title rather than shifting one left.
set -eu
mkdir -p specs/harness/tickets
cat > specs/harness/tickets/01-untiered.md <<'TICKET'
---
id: FLX-01
title: Ticket with no agent field
status: open
effort: low
blockers: []
checkpoint: none
---
## Context
Fixture ticket.
TICKET
cat > specs/harness/tickets/02-routed.md <<'TICKET'
---
id: FLX-02
title: Ticket with an agent
status: open
agent: build
effort: low
blockers: []
checkpoint: none
---
## Context
Fixture ticket.
TICKET
