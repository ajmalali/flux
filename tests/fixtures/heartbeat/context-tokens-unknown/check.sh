#!/usr/bin/env bash
# shellcheck source=/dev/null
. "$TESTS_ROOT/lib.sh"
f=.flux/session.json
assert_file "$f"
assert_json "$f"
if command -v jq >/dev/null 2>&1; then
  # Present and null — not absent, and above all not 0.
  assert_eq "$(jq -r 'has("context_tokens")' "$f")" true "context_tokens present"
  assert_eq "$(jq -r '.context_tokens | type' "$f")" null "context_tokens type"
fi
# The rest of the stamp still lands: an unreadable transcript costs one field,
# never the turn (ADR-0001, fail-open).
assert_key "$f" branch main
assert_ne "$(jget "$f" last_turn_at)" "" last_turn_at
finish
