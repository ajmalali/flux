#!/usr/bin/env bash
# shellcheck source=/dev/null
. "$TESTS_ROOT/lib.sh"
f=.flux/session.json
assert_json "$f"
assert_key "$f" branch detached
assert_key "$f" head_sha "$(git rev-parse --short HEAD)"
finish
