#!/usr/bin/env bash
# A session with a transcript to read. The count is not in the Stop event, so it
# is summed off the transcript the event points at (FLX-63o) — which makes the
# shape of that file, not the shape of the event, the thing worth pinning.
#
# Four records, in this order, and each is here to defeat a different wrong read:
#   1. a line that is not JSON at all — what a `tail -c` cut leaves behind when
#      it lands mid-record, so the reader has to skip it rather than fail
#   2. an earlier assistant turn — taking the first match would return 21105
#   3. the turn we want: 8 + 2048 + 51682 + 645 = 54383
#   4. a sidechain turn with a huge window — a scout's context, not the user's.
#      It is deliberately last, so a reader that only takes the final record
#      returns 921034 and the case fails loudly.
set -eu
export GIT_AUTHOR_NAME=flux GIT_AUTHOR_EMAIL=flux@example.com
export GIT_COMMITTER_NAME=flux GIT_COMMITTER_EMAIL=flux@example.com
git init -q -b main .
git config commit.gpgsign false
printf '.flux/\n' > .gitignore
echo seed > log.txt
git add -A
git commit -q -m "chore: seed the repo"

{
  printf '%s\n' '_tokens":{"cache_read_input_tokens":999999}}}'
  printf '%s\n' '{"type":"assistant","message":{"role":"assistant","usage":{"input_tokens":5,"cache_creation_input_tokens":1000,"cache_read_input_tokens":20000,"output_tokens":100}}}'
  printf '%s\n' '{"type":"user","message":{"role":"user","content":"carry on"}}'
  printf '%s\n' '{"type":"assistant","message":{"role":"assistant","usage":{"input_tokens":8,"cache_creation_input_tokens":2048,"cache_read_input_tokens":51682,"output_tokens":645}}}'
  printf '%s\n' '{"type":"assistant","isSidechain":true,"message":{"role":"assistant","usage":{"input_tokens":34,"cache_creation_input_tokens":1000,"cache_read_input_tokens":900000,"output_tokens":20000}}}'
} > transcript.jsonl
