#!/usr/bin/env bash
# A claimed ticket plus one handoff whose subject is not the pause skill — the
# case the citation exists for. A handoff about handoffs points at the
# obligation in its own Deposited section and so proves nothing; this one is
# about payments and points at nothing, which is every other handoff there will
# ever be. The claim is here so that removing the handoff still leaves a block
# to inspect.
set -eu
mkdir -p specs/harness/tickets .flux/handoffs
cat > specs/harness/tickets/20-sync-skill.md <<'TICKET'
---
id: FLX-20
title: /sync — reconcile off-harness work
status: claimed
agent: build
effort: medium
blockers: []
---
## Context
Fixture ticket.
TICKET
cat > .flux/handoffs/2026-08-14-payments.md <<'HANDOFF'
# Payment retry policy

Open: does a failed capture retry on the same idempotency key?
HANDOFF
