#!/usr/bin/env bash
# shellcheck source=/dev/null
. "$TESTS_ROOT/lib.sh"
f=.flux/session.json
assert_file "$f"
assert_json "$f"
assert_key "$f" branch main
finish
