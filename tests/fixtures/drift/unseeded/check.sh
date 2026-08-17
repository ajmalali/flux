#!/usr/bin/env bash
# shellcheck source=/dev/null
. "$TESTS_ROOT/lib.sh"
# shellcheck source=/dev/null
. "$(dirname "$HOOK_SCRIPT")/flux-common"
# 0 is the honest count here, and the state is what makes it distinguishable
# from a clean tree — the whole reason the two are separate answers.
assert_eq "$(drift_count "$PWD")" 0 "drift_count"
drift_list "$PWD" 0 >/dev/null
assert_eq "$?" "$DRIFT_UNSEEDED" "drift_list state"
finish
