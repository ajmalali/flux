#!/usr/bin/env bash
# shellcheck source=/dev/null
. "$TESTS_ROOT/lib.sh"
f=.flux/session.json
assert_json "$f"
# Both ZAP commits are linked; the one that only cites an ADR and an AC is not.
assert_key "$f" drift_commits 1
finish
