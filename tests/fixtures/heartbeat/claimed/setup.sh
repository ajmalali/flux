#!/usr/bin/env bash
# No bd on PATH, so the claim comes from the markdown frontmatter scan.
set -eu
export GIT_AUTHOR_NAME=flux GIT_AUTHOR_EMAIL=flux@example.com
export GIT_COMMITTER_NAME=flux GIT_COMMITTER_EMAIL=flux@example.com
git init -q -b main .
git config commit.gpgsign false
printf '.flux/\n' > .gitignore
mkdir -p specs/harness/tickets
cat > specs/harness/tickets/03-heartbeat.md <<'TICKET'
---
id: FLX-03
title: flux-heartbeat — Stop-hook state stamp
status: claimed
agent: build
effort: medium
blockers: [FLX-01]
checkpoint: none
---
## Context
Fixture ticket.
TICKET
git add -A
git commit -q -m "chore: seed the repo"
