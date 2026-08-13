#!/usr/bin/env bash
# The same session with no readable transcript — the event names a path that is
# not there. Real cases: a transcript not yet flushed, or jq missing.
#
# What this pins is that the count comes back null and never 0. They are not the
# same claim: 0 says this session has spent nothing, null says nobody knows, and
# a skill deciding whether to recommend a pause has to be able to tell them
# apart. 0 would read as "plenty of room left" forever (FLX-63o).
set -eu
export GIT_AUTHOR_NAME=flux GIT_AUTHOR_EMAIL=flux@example.com
export GIT_COMMITTER_NAME=flux GIT_COMMITTER_EMAIL=flux@example.com
git init -q -b main .
git config commit.gpgsign false
printf '.flux/\n' > .gitignore
echo seed > log.txt
git add -A
git commit -q -m "chore: seed the repo"
