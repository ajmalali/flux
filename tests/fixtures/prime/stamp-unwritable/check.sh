#!/usr/bin/env bash
# shellcheck source=/dev/null
. "$TESTS_ROOT/lib.sh"

f=.flux/session.json
# Mode 0500 does not stop uid 0, so the untouched-file assertion is only
# meaningful for an ordinary user; the printed block and the exit code are
# asserted by the runner either way.
if [ "$(id -u)" != 0 ]; then
  assert_key "$f" claimed_ticket FLX-01
  assert_glob_count 1 '.flux/session.json*'
fi
assert_json "$f"

chmod 0755 .flux  # the runner has to be able to delete this afterwards
finish
