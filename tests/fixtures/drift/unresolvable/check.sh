#!/usr/bin/env bash
# shellcheck source=/dev/null
. "$TESTS_ROOT/lib.sh"
# shellcheck source=/dev/null
. "$(dirname "$HOOK_SCRIPT")/flux-common"
# One drifted commit is sitting here unreported: that is the failure the state
# exists to make visible, not a number to be fixed.
assert_eq "$(drift_count "$PWD")" 0 "drift_count"
drift_list "$PWD" 0 >/dev/null
assert_eq "$?" "$DRIFT_LOST" "drift_list state"
# The line names the sha it could not find, so /sync can say what was lost.
assert_ne "$(jget .flux/session.json last_synced_commit)" "" "baseline recorded"
finish
