#!/usr/bin/env bash
# A sync baseline two commits behind HEAD. Heartbeat must never advance it.
set -eu
export GIT_AUTHOR_NAME=flux GIT_AUTHOR_EMAIL=flux@example.com
export GIT_COMMITTER_NAME=flux GIT_COMMITTER_EMAIL=flux@example.com
git init -q -b main .
git config commit.gpgsign false
printf '.flux/\n' > .gitignore
c() { echo "$1" >> log.txt; git add -A; git commit -q -m "$1"; }
c "chore: seed the repo"
base=$(git rev-parse HEAD)
c "FLX-01: scaffold"
c "FLX-02: prime"
mkdir -p .flux
printf '{"last_synced_commit":"%s"}\n' "$base" > .flux/session.json
printf '%s\n' "$base" > .flux/baseline
