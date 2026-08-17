#!/usr/bin/env bash
# The baseline commit is amended after being recorded. Its object is still in
# the database — an amend deletes nothing — but it is no longer in this line of
# history, which is the state that matters and the one an existence check
# misses. Drift detection is off here until something re-anchors it.
set -eu
export GIT_AUTHOR_NAME=flux GIT_AUTHOR_EMAIL=flux@example.com
export GIT_COMMITTER_NAME=flux GIT_COMMITTER_EMAIL=flux@example.com
git init -q -b main .
git config commit.gpgsign false
c() { echo "$1" >>log.txt; git add -A; git commit -q -m "$1"; }
c "chore: seed the repo"
base=$(git rev-parse HEAD)
mkdir -p .flux
printf '{"last_synced_commit":"%s"}\n' "$base" >.flux/session.json
echo more >>log.txt
git add log.txt
git commit -q --amend -m "chore: seed the repo, with the file it forgot"
c "wip: shuffle the layout"
