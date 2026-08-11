#!/usr/bin/env bash
# shellcheck source=/dev/null
. "$TESTS_ROOT/lib.sh"
f=.flux/session.json
assert_json "$f"
assert_eq "$(jget "$f" claimed_ticket)" "" claimed_ticket
# FLX-13, not FLX-05 (older) and not FLX-06 (the frontier head, which this no
# longer records at all). The intervening chore commit names no ticket and must
# not stop the scan.
assert_key "$f" last_done_ticket FLX-13
assert_eq "$(jget "$f" next_ticket)" "" next_ticket
finish
