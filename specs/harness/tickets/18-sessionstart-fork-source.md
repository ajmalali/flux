---
id: FLX-18
title: SessionStart matcher misses the `fork` source — prime never fires
status: done
agent: chore
effort: low
blockers: []
checkpoint: none
---
Spec: specs/harness/spec.md (AC-1).

## Context
Found while verifying the `/clear` check during the FLX-05 checkpoint. The
matcher in `hooks/hooks.json` is:

    "matcher": "startup|resume|clear|compact"

The current hooks documentation lists a fifth SessionStart source, `fork`, fired
when a session is forked with `--fork-session`. A forked session therefore starts
with no primed context at all — no claimed ticket, no frontier, no drift — which
is exactly the failure the prime hook exists to prevent, and it fails silently:
there is no error, just an unprimed session that looks normal.

`flux-prime` itself needs no change. It never reads `.source`, and running it
against all five values produces byte-identical output. This is a one-token fix
in the matcher plus a regression test that pins the source list.

## Tasks
1. Files: hooks/hooks.json
   Action: add `fork` to the SessionStart matcher.
   Verify: claude plugin validate . --strict
   Done: matcher reads `startup|resume|clear|compact|fork`
2. Files: tests/ (new case)
   Action: pin the matcher against the documented source list, so a future
   source added upstream fails a test rather than silently skipping prime.
   Verify: bash tests/run.sh
   Done: the test fails when a source is removed from the matcher

## Test plan
The hook script is source-agnostic, so the only thing worth testing is the
matcher string itself — a fixture that asserts the set, not the behaviour.

## Boundaries
Matcher and test only. Do not change flux-prime; it is already correct for every
source. Re-fetch the source list from https://code.claude.com/docs/en/hooks
before writing the test rather than copying it from this ticket — the list is
what changed, and it may have changed again.
