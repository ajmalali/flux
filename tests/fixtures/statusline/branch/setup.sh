#!/usr/bin/env bash
# The ordinary case: a checkout on a named branch. .git/HEAD is written by hand
# rather than by `git init` so the fixture is hermetic and costs no process.
# A slash in the branch name proves only the refs/heads/ prefix is stripped.
set -eu
mkdir -p .flux .git
printf 'ref: refs/heads/feature/statusline\n' > .git/HEAD
printf '{\n  "claimed_ticket": "FLX-04",\n  "dirty_files": 0\n}\n' > .flux/session.json
