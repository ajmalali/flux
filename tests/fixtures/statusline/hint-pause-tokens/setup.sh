#!/usr/bin/env bash
# A 1M window only 36% spent, but 361k tokens deep. The share says there is room
# left and the count says the session has been running a long time; the count is
# the one worth acting on, so the two marks are an OR and this one fires.
set -eu
mkdir -p .flux
printf '{\n  "claimed_ticket": "FLX-09"\n}\n' > .flux/session.json
