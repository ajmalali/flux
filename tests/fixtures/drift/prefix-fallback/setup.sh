#!/usr/bin/env bash
# The same commit in a repo that names no prefix. The fallback pattern is any
# all-caps id, so ADR-0006 reads as linked and the commit is not drift — which
# is why ticket_id_re narrows wherever a repo can say what its own ids look
# like, and why this is only the fallback.
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
mkdir -p .flux
printf '{"last_synced_commit":"%s"}\n' "$base" >.flux/session.json
