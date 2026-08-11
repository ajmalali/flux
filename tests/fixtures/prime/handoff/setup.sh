#!/usr/bin/env bash
# A claimed ticket plus one unconsumed handoff in .flux/handoffs/.
set -eu
mkdir -p specs/harness/tickets .flux/handoffs
cat > specs/harness/tickets/09-plan-skill.md <<'TICKET'
---
id: FLX-09
title: /plan — grilling interview to approved spec
status: claimed
agent: deep
effort: high
blockers: []
checkpoint: decision
---
## Context
Fixture ticket.
TICKET
cat > .flux/handoffs/2026-08-09-routing.md <<'HANDOFF'
# Routing tiers — deep vs build

Open: does the deep tier justify opus pricing on ticket writing?
HANDOFF
