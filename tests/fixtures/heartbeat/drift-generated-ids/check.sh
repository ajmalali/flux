#!/usr/bin/env bash
# shellcheck source=/dev/null
. "$TESTS_ROOT/lib.sh"
f=.flux/session.json
assert_json "$f"
# Three of the five commits name a ticket. The bare "FLX-" is not an id and the
# ADR reference is not this repo's prefix, so both of those still count.
assert_key "$f" drift_commits 2
# The property the ticket turns on: one more commit under a generated id leaves
# the count alone.
git commit -q --allow-empty -m "FLX-qk4: another generated id"
rerun
assert_key "$f" drift_commits 2
finish
