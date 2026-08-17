#!/usr/bin/env bash
# A repo with history and no .flux/ at all — the state before the first
# heartbeat. Pre-harness history is not drift.
set -eu
export GIT_AUTHOR_NAME=flux GIT_AUTHOR_EMAIL=flux@example.com
export GIT_COMMITTER_NAME=flux GIT_COMMITTER_EMAIL=flux@example.com
git init -q -b main .
git config commit.gpgsign false
c() { echo "$1" >>log.txt; git add -A; git commit -q -m "$1"; }
c "chore: seed the repo"
c "wip: shuffle the layout"
