#!/usr/bin/env bash
# shellcheck source=/dev/null
. "$TESTS_ROOT/lib.sh"
# shellcheck source=/dev/null
. "$(dirname "$HOOK_SCRIPT")/flux-common"
assert_eq "$(drift_count "$PWD")" 1 "drift_count"
finish
