#!/usr/bin/env bash
# shellcheck source=/dev/null
. "$TESTS_ROOT/lib.sh"
# shellcheck source=/dev/null
. "$(dirname "$HOOK_SCRIPT")/flux-common"
assert_eq "$(drift_count "$PWD")" 0 "drift_count"
rows=$(drift_list "$PWD" 0)
assert_eq "$?" "$DRIFT_OK" "drift_list state"
assert_eq "$rows" "" "rows"
finish
