#!/usr/bin/env bash
# Garbage on stdin: the line still renders, from $PWD and session.json.
set -eu
mkdir -p .flux
printf '{\n  "claimed_ticket": "FLX-11",\n  "dirty_files": 0\n}\n' > .flux/session.json
