#!/usr/bin/env bash
# shellcheck source=/dev/null
. "$TESTS_ROOT/lib.sh"
f=.flux/session.json
assert_file "$f"
assert_json "$f"
assert_eq "$(jget "$f" branch)" "" branch
assert_eq "$(jget "$f" head_sha)" "" head_sha
assert_key "$f" dirty_files 0
assert_eq "$(jget "$f" last_synced_commit)" "" last_synced_commit
finish
