#!/usr/bin/env bash
# Nothing claimed. The heartbeat caches the last *completed* ticket so the
# statusline can name it without touching the store — and the interesting case
# is that it is not the highest-numbered done ticket: FLX-13 was finished after
# FLX-05, so recency has to come from git history rather than from file order.
set -eu
export GIT_AUTHOR_NAME=flux GIT_AUTHOR_EMAIL=flux@example.com
export GIT_COMMITTER_NAME=flux GIT_COMMITTER_EMAIL=flux@example.com
git init -q -b main .
git config commit.gpgsign false
printf '.flux/\n' > .gitignore
mkdir -p specs/harness/tickets
t() {
  cat > "specs/harness/tickets/$1.md" <<TICKET
---
id: $2
title: $3
status: $4
agent: build
blockers: [$5]
---
TICKET
}
t 05-done    FLX-05 "Finished first"                       done ""
t 06-ready   FLX-06 "Ready — its only blocker is done"     open "FLX-05"
t 07-blocked FLX-07 "Blocked behind an open ticket"        open "FLX-06"
t 13-done    FLX-13 "Finished last, out of numeric order"  done ""
git add -A
git commit -q -m "FLX-05: finished first"
git commit -q --allow-empty -m "FLX-13: finished last, out of numeric order"
git commit -q --allow-empty -m "chore: a commit naming no ticket at all"
