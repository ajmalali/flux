#!/usr/bin/env bash
# In a linked worktree .git is a FILE holding "gitdir: <path>", and HEAD lives
# at that path. The branch still wins over workspace.git_worktree, which the
# stdin.json also supplies — a worktree's whole point is the branch it holds.
set -eu
mkdir -p .flux realgit
printf 'gitdir: %s/realgit\n' "$PWD" > .git
printf 'ref: refs/heads/flux-show-work\n' > realgit/HEAD
printf '{\n  "claimed_ticket": "FLX-12",\n  "dirty_files": 3\n}\n' > .flux/session.json
