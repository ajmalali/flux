#!/usr/bin/env bash
# shellcheck source=/dev/null
. "$TESTS_ROOT/lib.sh"
f=.flux/session.json
assert_file "$f"
assert_json "$f"
# 8 + 2048 + 51682 + 645, from the last main-thread record. Not 21105 (an
# earlier turn) and not 921034 (the sidechain that follows it).
assert_key "$f" context_tokens 54383
if command -v jq >/dev/null 2>&1; then
  # A number, not a string: the skill compares it against 200k and 350k.
  assert_eq "$(jq -r '.context_tokens | type' "$f")" number "context_tokens type"
fi
finish
