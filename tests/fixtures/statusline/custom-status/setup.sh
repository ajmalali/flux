#!/usr/bin/env bash
# An optional `status` field wins over the default "claimed", so a verb can
# show what it is doing without touching this script.
set -eu
mkdir -p .flux
printf '{\n  "claimed_ticket": "FLX-11",\n  "status": "qualifying"\n}\n' > .flux/session.json
