#!/usr/bin/env bash
# The regression is a sequence, not one invocation: claim → prime → statusline,
# with no heartbeat in between. The assertion that matters is the last line —
# what the statusline renders from the session.json prime left behind.
# shellcheck source=/dev/null
. "$TESTS_ROOT/lib.sh"

f=.flux/session.json
assert_json "$f"
assert_key "$f" claimed_ticket FLX-03
assert_key "$f" next_ticket FLX-04
assert_key "$f" last_synced_commit 1111111
# The claim moved, so the status that described the old one goes with it.
assert_key "$f" status ""
# Fields prime does not own keep the previous session's values rather than
# being clobbered to null — only the heartbeat has fresh ones.
assert_key "$f" branch main
assert_key "$f" head_sha abc1234
assert_glob_count 1 '.flux/session.json*'

line=$("$TESTS_ROOT/../bin/flux-statusline" <<JSON
{"session_id":"abc123","cwd":"$PWD","workspace":{"current_dir":"$PWD","project_dir":"$PWD","added_dirs":[]},"context_window":{"total_input_tokens":21000,"total_output_tokens":450,"context_window_size":200000,"used_percentage":10.7,"remaining_percentage":89.3}}
JSON
)
assert_eq "$line" "FLX-03-claimed · stamps-claim · ctx 10% · 21.5k" "statusline first render"

finish
