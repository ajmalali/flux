#!/usr/bin/env bash
# Nothing claimed, two open tickets, one still blocked. The heartbeat caches the
# frontier head so the statusline can name it without touching the store. FLX-07
# is blocked by an open ticket, so the head must be FLX-06, not just the first
# open file in name order.
set -eu
export GIT_AUTHOR_NAME=flux GIT_AUTHOR_EMAIL=flux@example.com
export GIT_COMMITTER_NAME=flux GIT_COMMITTER_EMAIL=flux@example.com
git init -q -b main .
git config commit.gpgsign false
printf '.flux/\n' > .gitignore
mkdir -p specs/harness/tickets
cat > specs/harness/tickets/05-done.md <<'TICKET'
---
id: FLX-05
title: Already finished
status: done
agent: build
blockers: []
---
TICKET
cat > specs/harness/tickets/06-ready.md <<'TICKET'
---
id: FLX-06
title: Ready — its only blocker is done
status: open
agent: chore
blockers: [FLX-05]
---
TICKET
cat > specs/harness/tickets/07-blocked.md <<'TICKET'
---
id: FLX-07
title: Blocked behind an open ticket
status: open
agent: build
blockers: [FLX-06]
---
TICKET
git add -A
git commit -q -m "chore: seed the repo"
