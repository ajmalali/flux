#!/usr/bin/env bash
# The other consumer of the id pattern. Without beads, recency comes from git:
# the newest commit message naming a ticket that is done. A generated id has to
# be findable there too — FLX-63o was finished after FLX-05, and file order
# would name the wrong one.
#
# There is no .beads/ here to state a prefix, so this is also the case that
# exercises the fallback pattern rather than a read one.
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
t 05-done  FLX-05   "Finished first"                          done ""
t 06-open  FLX-06   "Still open"                              open ""
t 63o-done FLX-63o  "Finished last, under a generated id"     done ""
git add -A
git commit -q -m "FLX-05: finished first"
git commit -q --allow-empty -m "FLX-63o: finished last, under a generated id"
git commit -q --allow-empty -m "chore: a commit naming no ticket at all"
