#!/usr/bin/env bash
# shellcheck source=/dev/null
. "$TESTS_ROOT/lib.sh"
f=.flux/session.json
assert_file "$f"
assert_json "$f"
assert_key "$f" branch main
assert_key "$f" head_sha "$(git rev-parse --short HEAD)"
assert_key "$f" dirty_files 0
assert_eq "$(jget "$f" claimed_ticket)" "" claimed_ticket
# Seeded from HEAD on first sight; only /sync moves it afterwards.
assert_key "$f" last_synced_commit "$(git rev-parse HEAD)"
assert_ne "$(jget "$f" last_turn_at)" "" last_turn_at
assert_glob_count 1 '.flux/session.json*'
finish
