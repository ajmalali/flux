#!/usr/bin/env bash
# One modified tracked file and one untracked file: dirty_files must count both.
set -eu
export GIT_AUTHOR_NAME=flux GIT_AUTHOR_EMAIL=flux@example.com
export GIT_COMMITTER_NAME=flux GIT_COMMITTER_EMAIL=flux@example.com
git init -q -b main .
git config commit.gpgsign false
printf '.flux/\n' > .gitignore
echo seed > log.txt
git add -A
git commit -q -m "chore: seed the repo"
echo changed >> log.txt
echo new > untracked.txt
