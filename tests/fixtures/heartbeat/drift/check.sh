#!/usr/bin/env bash
# shellcheck source=/dev/null
. "$TESTS_ROOT/lib.sh"
f=.flux/session.json
assert_json "$f"
assert_key "$f" drift_commits 2
# Counting drift must not move the baseline it counts from — /sync owns that.
assert_key "$f" last_synced_commit "$(cat .flux/baseline)"
# A ticket commit lands: the count drops on the next turn without anything else
# changing, which is the property the statusline is relying on.
git commit -q --allow-empty -m "FLX-01: another attributed commit"
rerun
assert_key "$f" drift_commits 2
git commit -q --allow-empty -m "wip: one more unattributed"
rerun
assert_key "$f" drift_commits 3
finish
