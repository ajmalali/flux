#!/usr/bin/env bash
# shellcheck source=/dev/null
. "$TESTS_ROOT/lib.sh"
f=.flux/session.json
assert_json "$f"
# FLX-63o, not FLX-05: the scan has to match the generated id, and the commit
# naming no ticket must not stop it.
assert_key "$f" last_done_ticket FLX-63o
finish
