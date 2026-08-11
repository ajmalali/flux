#!/usr/bin/env bash
# Inside a linked worktree the name comes from workspace.git_worktree, not the
# directory, so parallel worktrees are told apart at a glance.
set -eu
mkdir -p .flux
printf '{\n  "claimed_ticket": "FLX-12",\n  "dirty_files": 3\n}\n' > .flux/session.json
