#!/usr/bin/env bash
# Normalized stdout can only prove the shape of a sha. This proves the value:
# the first row is the oldest drifted commit, and the count prime prints is the
# same set counted rather than a second walk.
# shellcheck source=/dev/null
. "$TESTS_ROOT/lib.sh"
# shellcheck source=/dev/null
. "$(dirname "$HOOK_SCRIPT")/flux-common"

assert_eq "$(drift_count "$PWD")" 2 "drift_count"

rows=$(drift_list "$PWD" 0)
assert_eq "$?" "$DRIFT_OK" "drift_list state"

first=${rows%%$'\n'*}
assert_eq "$(git log -1 --format=%s "${first%%$'\t'*}" 2>/dev/null)" \
  "wip: shuffle the layout" "first row is the oldest drifted commit"

finish
