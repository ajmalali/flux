#!/usr/bin/env bash
# Five drifted commits. flux-drift is unbounded and prints all five; the cap is
# the hooks' budget, exercised in check.sh where a caller sets it.
set -eu
export GIT_AUTHOR_NAME=flux GIT_AUTHOR_EMAIL=flux@example.com
export GIT_COMMITTER_NAME=flux GIT_COMMITTER_EMAIL=flux@example.com
git init -q -b main .
git config commit.gpgsign false
c() { echo "$1" >>log.txt; git add -A; git commit -q -m "$1"; }
c "chore: seed the repo"
base=$(git rev-parse HEAD)
for n in 1 2 3 4 5; do c "raw edit $n"; done
mkdir -p .flux
printf '{"last_synced_commit":"%s"}\n' "$base" >.flux/session.json
