#!/usr/bin/env bash
#
# flux test runner — plain bash, no framework.
#
#   bash tests/run.sh              # every suite
#   bash tests/run.sh prime        # one suite
#   bash tests/run.sh shellcheck
#
# Hook-script suites are table-driven: every directory under
# tests/fixtures/<suite>/ is one case, containing
#   setup.sh      builds the fixture repo in $PWD (the case work dir)
#   stdin.json    hook input; the token __CWD__ is replaced with the work dir
#   expected.txt  exact expected stdout (absent means "expect empty stdout")
#   check.sh      optional; assertions about side effects, run in the work dir
#                 after the hook, with tests/lib.sh available at $TESTS_ROOT
#   bin/          optional; prepended to PATH so a case can stub a binary
# A case passes when stdout matches, stderr is empty, the exit code is 0, and
# check.sh (if present) exits 0.
#
# The `hooks` suite has no fixtures: it asserts on hooks/hooks.json itself,
# where the thing worth pinning is the manifest, not any observable output.

set -u

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
TESTS_ROOT="$ROOT/tests"
PASS=0
FAIL=0
TMPROOT=$(mktemp -d "${TMPDIR:-/tmp}/flux-tests.XXXXXX")
trap 'rm -rf "$TMPROOT"' EXIT

ok()   { PASS=$((PASS + 1)); printf '  ok   %s\n' "$1"; }
bad()  { FAIL=$((FAIL + 1)); printf '  FAIL %s\n' "$1"; }
skip() { printf '  skip %s (%s)\n' "$1" "$2"; }

# ------------------------------------------------------------ hook suites ---

# Side-effect assertions for one case. No check.sh means nothing to assert.
run_case_check() {
  local case="$1" work="$2" path="$3" script="$4" in="$5" log="$6"
  : >"$log"
  [ -f "$case/check.sh" ] || return 0
  (cd "$work" && PATH="$path" FLUX_BD="${case}bin/bd" TESTS_ROOT="$TESTS_ROOT" \
    HOOK_SCRIPT="$script" HOOK_STDIN="$in" bash "$case/check.sh") >"$log" 2>&1
}

run_hook_suite() {
  local suite="$1" script="$2"
  local fixtures="$ROOT/tests/fixtures/$suite"
  printf '%s\n' "$suite"

  if [ ! -d "$fixtures" ]; then
    bad "$suite: no fixtures at tests/fixtures/$suite"
    return
  fi

  local tmp case name work in out err code expected path
  tmp="$TMPROOT/$suite"
  mkdir -p "$tmp" || { bad "$suite: mkdir $tmp"; return; }

  for case in "$fixtures"/*/; do
    [ -d "$case" ] || continue
    name=$(basename "$case")
    work="$tmp/$name"
    mkdir -p "$work"

    if [ -f "$case/setup.sh" ]; then
      if ! (cd "$work" && bash "$case/setup.sh" >/dev/null 2>&1); then
        bad "$suite/$name: setup.sh failed"
        continue
      fi
    fi

    path="$PATH"
    [ -d "$case/bin" ] && path="$case/bin:$PATH"

    in="$tmp/$name.in"
    out="$tmp/$name.out"
    err="$tmp/$name.err"
    if [ -f "$case/stdin.json" ]; then
      sed "s|__CWD__|$work|g" "$case/stdin.json" >"$in"
    else
      : >"$in"
    fi
    # FLUX_BD points at a path that cannot exist so the beads branch is only
    # taken by cases that stub `bd` in their own bin/ directory.
    (cd "$work" && PATH="$path" FLUX_BD="${case}bin/bd" "$script" <"$in") >"$out" 2>"$err"
    code=$?

    expected="$case/expected.txt"
    if [ ! -f "$expected" ]; then
      expected="$tmp/$name.empty"
      : >"$expected"
    fi

    if [ "$code" -ne 0 ]; then
      bad "$suite/$name: exit $code (must always be 0)"
    elif [ -s "$err" ]; then
      bad "$suite/$name: wrote to stderr"
      sed 's/^/       /' "$err"
    elif ! diff -u "$expected" "$out" >"$tmp/$name.diff" 2>&1; then
      bad "$suite/$name: stdout mismatch"
      sed 's/^/       /' "$tmp/$name.diff"
    elif ! run_case_check "$case" "$work" "$path" "$script" "$in" "$tmp/$name.check"; then
      bad "$suite/$name: check.sh failed"
      sed 's/^/       /' "$tmp/$name.check"
    else
      ok "$suite/$name"
    fi
  done
}

suite_prime() { run_hook_suite prime "$ROOT/bin/flux-prime"; }
suite_heartbeat() { run_hook_suite heartbeat "$ROOT/bin/flux-heartbeat"; }
suite_statusline() { run_hook_suite statusline "$ROOT/bin/flux-statusline"; }

# ------------------------------------------------------------- manifest ----

# Every SessionStart source listed at https://code.claude.com/docs/en/hooks
# (re-read 2026-08-11). prime has to fire for all of them: a source the matcher
# misses is not an error, it is a session that silently starts unprimed. When
# the docs grow a source, add it here — the test then tells you the matcher
# needs it too.
SESSION_START_SOURCES=(clear compact fork resume startup)

suite_hooks() {
  printf 'hooks\n'
  local file="$ROOT/hooks/hooks.json"

  if [ ! -f "$file" ]; then
    bad "hooks: no manifest at hooks/hooks.json"
    return
  fi
  if ! command -v jq >/dev/null 2>&1; then
    skip "hooks/prime-sources" "jq not installed"
    return
  fi

  # Matchers of every SessionStart entry that runs flux-prime, joined — the hook
  # may be split across entries; what matters is the union they cover. An entry
  # with no matcher at all already runs for every source (the Stop hook does
  # this), so it is reported as * rather than as an empty alternation.
  local matcher
  matcher=$(jq -r '
    (.hooks.SessionStart // [])
    | map(select(any(.hooks[]?.command; test("flux-prime"))))
    | map(if has("matcher") then .matcher else "*" end)
    | join("|")
  ' "$file" 2>/dev/null)

  local want got=""
  want=$(printf '%s\n' "${SESSION_START_SOURCES[@]}" | sort | tr '\n' ' ')
  if [ -n "$matcher" ]; then
    local -a covered=()
    IFS='|' read -r -a covered <<<"$matcher"
    got=$(printf '%s\n' "${covered[@]}" | sort -u | tr '\n' ' ')
  fi

  if [ "$got" = "$want" ] || [ "$matcher" = "*" ]; then
    ok "hooks/prime-sources: $matcher"
  else
    bad "hooks/prime-sources: SessionStart matcher must cover every documented source"
    printf '       want: %s\n       got:  %s\n' "$want" "$got"
  fi
}

# ---------------------------------------------------------------- lint -----

suite_shellcheck() {
  printf 'shellcheck\n'
  if ! command -v shellcheck >/dev/null 2>&1; then
    skip "shellcheck" "not installed — brew install shellcheck"
    return
  fi
  local f
  # .claude/hooks/* is not shipped with the plugin, but it runs on every Stop in
  # this repo and the shell contract applies to it just the same.
  for f in "$ROOT"/bin/* "$ROOT"/.claude/hooks/* "$ROOT"/tests/run.sh "$ROOT"/tests/lib.sh; do
    [ -f "$f" ] || continue
    case "$f" in *.gitkeep | *.md) continue ;; esac
    if shellcheck -s bash "$f" >"$f.shellcheck.log" 2>&1; then
      ok "shellcheck ${f#"$ROOT"/}"
    else
      bad "shellcheck ${f#"$ROOT"/}"
      sed 's/^/       /' "$f.shellcheck.log"
    fi
    rm -f "$f.shellcheck.log"
  done
}

# ---------------------------------------------------------------- driver ---

SUITES=("$@")
[ "${#SUITES[@]}" -gt 0 ] || SUITES=(prime heartbeat statusline hooks shellcheck)

for s in "${SUITES[@]}"; do
  case "$s" in
    prime) suite_prime ;;
    heartbeat) suite_heartbeat ;;
    statusline) suite_statusline ;;
    hooks) suite_hooks ;;
    shellcheck) suite_shellcheck ;;
    *) bad "unknown suite: $s" ;;
  esac
done

printf '\n%s passed, %s failed\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
