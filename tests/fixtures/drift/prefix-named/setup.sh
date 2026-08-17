#!/usr/bin/env bash
# A repo that names its own prefix, and a commit whose body cites an ADR and an
# acceptance criterion but no ticket. It is drift: FLX-<id> is what counts here,
# and ADR-0006 is not one.
set -eu
export GIT_AUTHOR_NAME=flux GIT_AUTHOR_EMAIL=flux@example.com
export GIT_COMMITTER_NAME=flux GIT_COMMITTER_EMAIL=flux@example.com
git init -q -b main .
git config commit.gpgsign false
echo seed >>log.txt
git add -A
git commit -q -m "chore: seed the repo"
base=$(git rev-parse HEAD)
echo more >>log.txt
git add -A
git commit -q -F - <<'MSG'
tighten the statusline

Satisfies AC-11 and keeps ADR-0006 intact.
MSG
mkdir -p .flux .beads
printf 'issue-prefix: FLX\n' >.beads/config.yaml
printf '{"last_synced_commit":"%s"}\n' "$base" >.flux/session.json
