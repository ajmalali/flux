#!/usr/bin/env bash
# Past 100k the decimal stops earning its width, so the count rounds to whole k.
# No .git here: this case is about the token segment, and the branch falling
# back to the directory name keeps the expectation stable.
set -eu
mkdir -p .flux
printf '{\n  "claimed_ticket": "FLX-09"\n}\n' > .flux/session.json
