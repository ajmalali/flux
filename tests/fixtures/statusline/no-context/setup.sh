#!/usr/bin/env bash
# Before the first API response there is no context_window object at all.
set -eu
mkdir -p .flux
printf '{\n  "claimed_ticket": "FLX-09",\n  "dirty_files": 0\n}\n' > .flux/session.json
