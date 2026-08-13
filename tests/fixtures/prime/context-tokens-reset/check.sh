#!/usr/bin/env bash
# shellcheck source=/dev/null
. "$TESTS_ROOT/lib.sh"
f=.flux/session.json
assert_file "$f"
assert_json "$f"
if command -v jq >/dev/null 2>&1; then
  # The previous session's 412000 must not survive into this one.
  assert_eq "$(jq -r '.context_tokens | type' "$f")" null "context_tokens type"
fi
# The baseline is still only /sync's to move — clearing the count clears nothing
# else.
assert_key "$f" last_synced_commit 1111111
finish
