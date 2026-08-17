#!/usr/bin/env bash
# The cap is a budget, not part of the definition of drift: it changes how many
# rows a caller gets and says so, and never which commits qualify.
# shellcheck source=/dev/null
. "$TESTS_ROOT/lib.sh"
# shellcheck source=/dev/null
. "$(dirname "$HOOK_SCRIPT")/flux-common"

count_rows() {
  local rows="$1" n=0
  while [ -n "$rows" ]; do
    n=$((n + 1))
    case "$rows" in
      *$'\n'*) rows="${rows#*$'\n'}" ;;
      *) rows="" ;;
    esac
  done
  printf '%s' "$n"
}

rows=$(drift_list "$PWD" 3)
assert_eq "$?" "$DRIFT_CAPPED" "capped state"
assert_eq "$(count_rows "$rows")" 3 "rows under a cap of 3"
# Newest three, so the number a hook prints is a floor on a window that reaches
# back from HEAD rather than a random slice.
assert_eq "${rows##*$'\t'}" "raw edit 5" "newest row kept"

rows=$(drift_list "$PWD" 0)
assert_eq "$?" "$DRIFT_OK" "unbounded state"
assert_eq "$(count_rows "$rows")" 5 "rows unbounded"

# The hooks' default cap is far above five, so prime sees the whole set here.
assert_eq "$(drift_count "$PWD")" 5 "drift_count"
finish
