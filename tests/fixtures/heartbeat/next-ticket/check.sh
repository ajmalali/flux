#!/usr/bin/env bash
# shellcheck source=/dev/null
. "$TESTS_ROOT/lib.sh"
f=.flux/session.json
assert_json "$f"
assert_eq "$(jget "$f" claimed_ticket)" "" claimed_ticket
assert_key "$f" next_ticket FLX-06
finish
