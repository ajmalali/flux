#!/usr/bin/env bash
# shellcheck source=/dev/null
. "$TESTS_ROOT/lib.sh"
f=.flux/session.json
assert_json "$f"
assert_key "$f" claimed_ticket FLX-03
assert_key "$f" dirty_files 0
finish
