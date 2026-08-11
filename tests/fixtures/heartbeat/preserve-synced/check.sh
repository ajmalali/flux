#!/usr/bin/env bash
# shellcheck source=/dev/null
. "$TESTS_ROOT/lib.sh"
f=.flux/session.json
base=$(cat .flux/baseline)
assert_json "$f"
assert_key "$f" last_synced_commit "$base"
assert_ne "$base" "$(git rev-parse HEAD)" "baseline should be behind HEAD"
# Two consecutive runs: still valid JSON, baseline still untouched.
rerun
assert_json "$f"
assert_key "$f" last_synced_commit "$base"
assert_key "$f" head_sha "$(git rev-parse --short HEAD)"
assert_glob_count 1 '.flux/session.json*'
finish
