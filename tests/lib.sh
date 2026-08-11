#!/usr/bin/env bash
#
# Assertions for fixture check.sh scripts. Sourced as "$TESTS_ROOT/lib.sh"; the
# runner exports TESTS_ROOT, HOOK_SCRIPT (the script under test) and HOOK_STDIN
# (the rendered stdin file, so a case can drive a second run itself).
#
# Every assertion records the failure and keeps going, so one run reports all
# broken expectations. Call `finish` last; it becomes the check's exit code.

FAILURES=0

fail() { FAILURES=$((FAILURES + 1)); printf 'assert: %s\n' "$1" >&2; }
finish() { [ "$FAILURES" -eq 0 ]; }

# Run the script under test again, same stdin, in the current directory.
rerun() { "$HOOK_SCRIPT" <"$HOOK_STDIN"; }

# jget <file> <key> — top-level value, "" when absent or null.
jget() {
  if command -v jq >/dev/null 2>&1; then
    jq -r --arg k "$2" '.[$k] // empty' "$1" 2>/dev/null
  else
    sed -n "s/.*\"$2\"[[:space:]]*:[[:space:]]*\"\{0,1\}\([^\",}]*\)\"\{0,1\}.*/\1/p" "$1" 2>/dev/null | head -1
  fi
}

assert_file() { [ -f "$1" ] || fail "missing file: $1"; }

# Skipped rather than faked when jq is absent — a hand-rolled parser would only
# assert that our own printf round-trips.
assert_json() {
  command -v jq >/dev/null 2>&1 || return 0
  jq empty "$1" >/dev/null 2>&1 || fail "not valid JSON: $1"
}

assert_eq() { [ "$1" = "$2" ] || fail "${3:-value}: expected '$2', got '$1'"; }
assert_ne() { [ "$1" != "$2" ] || fail "${3:-value}: expected anything but '$2'"; }

assert_key() { assert_eq "$(jget "$1" "$2")" "$3" "$2"; }

# assert_glob_count <count> '<pattern>' — how many paths the pattern matches.
# Quote the pattern at the call site; expansion has to happen in here.
assert_glob_count() {
  local want="$1" pattern="$2"
  local -a hits=()
  shopt -s nullglob
  # shellcheck disable=SC2206  # deliberate: $pattern is a glob, not a filename
  hits=($pattern)
  shopt -u nullglob
  assert_eq "${#hits[@]}" "$want" "matches for $pattern"
}
