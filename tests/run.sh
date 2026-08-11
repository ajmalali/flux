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
#   bin/          optional; prepended to PATH so a case can stub a binary
# A case passes when stdout matches, stderr is empty, and the exit code is 0.

set -u

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PASS=0
FAIL=0
TMPROOT=$(mktemp -d "${TMPDIR:-/tmp}/flux-tests.XXXXXX")
trap 'rm -rf "$TMPROOT"' EXIT

ok()   { PASS=$((PASS + 1)); printf '  ok   %s\n' "$1"; }
bad()  { FAIL=$((FAIL + 1)); printf '  FAIL %s\n' "$1"; }
skip() { printf '  skip %s (%s)\n' "$1" "$2"; }

# ------------------------------------------------------------ hook suites ---

run_hook_suite() {
  local suite="$1" script="$2"
  local fixtures="$ROOT/tests/fixtures/$suite"
  printf '%s\n' "$suite"

  if [ ! -d "$fixtures" ]; then
    bad "$suite: no fixtures at tests/fixtures/$suite"
    return
  fi

  local tmp case name work out err code expected path
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

    out="$tmp/$name.out"
    err="$tmp/$name.err"
    # FLUX_BD points at a path that cannot exist so the beads branch is only
    # taken by cases that stub `bd` in their own bin/ directory.
    if [ -f "$case/stdin.json" ]; then
      sed "s|__CWD__|$work|g" "$case/stdin.json"
    else
      printf ''
    fi | (cd "$work" && PATH="$path" FLUX_BD="${case}bin/bd" "$script") >"$out" 2>"$err"
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
    else
      ok "$suite/$name"
    fi
  done
}

suite_prime() { run_hook_suite prime "$ROOT/bin/flux-prime"; }

# ---------------------------------------------------------------- lint -----

suite_shellcheck() {
  printf 'shellcheck\n'
  if ! command -v shellcheck >/dev/null 2>&1; then
    skip "shellcheck" "not installed — brew install shellcheck"
    return
  fi
  local f
  for f in "$ROOT"/bin/* "$ROOT"/tests/run.sh; do
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
[ "${#SUITES[@]}" -gt 0 ] || SUITES=(prime shellcheck)

for s in "${SUITES[@]}"; do
  case "$s" in
    prime) suite_prime ;;
    shellcheck) suite_shellcheck ;;
    *) bad "unknown suite: $s" ;;
  esac
done

printf '\n%s passed, %s failed\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
