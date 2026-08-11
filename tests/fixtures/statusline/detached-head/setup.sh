#!/usr/bin/env bash
# Detached HEAD — mid-rebase, or a bisect. There is no branch to name, so the
# segment falls back to a short sha rather than going blank.
set -eu
mkdir -p .flux .git
printf '9f3c1a7b2e5d4088c6a1b0e7d3f2c95814a6b7d0\n' > .git/HEAD
printf '{\n  "claimed_ticket": null\n}\n' > .flux/session.json
