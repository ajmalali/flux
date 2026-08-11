#!/usr/bin/env bash
# Clean repo on main, no .flux yet — the first heartbeat this repo has ever seen.
set -eu
export GIT_AUTHOR_NAME=flux GIT_AUTHOR_EMAIL=flux@example.com
export GIT_COMMITTER_NAME=flux GIT_COMMITTER_EMAIL=flux@example.com
git init -q -b main .
git config commit.gpgsign false
printf '.flux/\n' > .gitignore
echo seed > log.txt
git add -A
git commit -q -m "chore: seed the repo"
