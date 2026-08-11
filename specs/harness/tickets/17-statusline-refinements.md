---
id: FLX-17
title: Statusline refinements — branch, merged ticket state, token count
status: done
agent: build
effort: low
blockers: [FLX-04]
checkpoint: none
---
Spec: specs/harness/spec.md (AC-4, refining the format FLX-04 shipped).

## Context
Raised by the human during the FLX-05 checkpoint, from looking at the real line
rather than the fixtures. Three complaints, all about what the line spends its
width on:

- the worktree/repo name never changes, so it earns nothing — the branch does
- `—` said nothing, and `idle` repeated what an empty ticket segment already said
- a bare percentage does not say how much room is left in absolute terms

New format — the state word folds into the ticket segment, so one segment carries
both the ticket and what is happening to it:

    FLX-04-claimed    · main · ctx 41% · 83.6k
    FLX-11-qualifying · main · ctx 41% · 83.6k   (verb-supplied status)
    FLX-06-unclaimed  · main · ctx 41% · 83.6k   (nothing claimed, frontier head)
    no tickets        · main · ctx 41% · 83.6k   (store has neither)

The interesting constraint is `FLX-06-unclaimed`: naming the frontier head means
knowing the frontier, and FLX-04's boundary forbids the statusline from touching
the store. Resolved by moving the work, not the boundary — the heartbeat already
calls `store_claimed` inside a 500ms budget, so it also caches `next_ticket` into
`.flux/session.json` and the statusline reads it from there. The statusline still
makes no store call and no `git` fork.

## Tasks
1. Files: bin/flux-heartbeat
   Action: cache the frontier head as `next_ticket` in .flux/session.json, via
   `store_ready` (ADR-0002 — never the markdown scan directly).
   Verify: bash tests/run.sh heartbeat
   Done: fixture with a done blocker, a ready ticket and a blocked ticket writes
   `next_ticket: FLX-06`; measured 82ms against the 500ms budget
2. Files: bin/flux-statusline
   Action: branch from .git/HEAD by builtin read (no `git` fork — handles the
   linked-worktree `gitdir:` file, strips refs/heads/, short sha when detached,
   falls back to worktree then directory name); merge status into the ticket
   segment; append `total_input_tokens + total_output_tokens`, formatted 83.6k
   under 100k and 817k above, omitted entirely while zero.
   Verify: bash tests/run.sh statusline shellcheck
   Done: 12 fixtures pass, including branch, detached-head, worktree-branch,
   next-unclaimed and tokens-large; measured 20ms against the 100ms budget
3. Files: README.md
   Action: document the four first-segment forms and why the frontier head is
   the heartbeat's job rather than the statusline's.
   Verify: read it against the four fixture expectations
   Done: the documented strings match the fixtures exactly

## Test plan
Five new fixtures (four statusline, one heartbeat) plus every existing statusline
expectation rewritten for the merged label. Both the claimed and unclaimed paths
are covered, as is the no-store case.

## Boundaries
FLX-04's boundary holds and is the reason this ticket is shaped the way it is:
the statusline stays read-only, store-free and fork-free. Anything needing the
ticket store goes in the heartbeat.

## Notes
Done outside the one-ticket-per-session rule (ADR-0003) — written during the
FLX-05 checkpoint session at the human's direction, and recorded here after the
fact so ticket frontmatter stays the only record of progress.

`shellcheck` caught a real bug during the work: `local root="$1" gitdir="$root/.git"`
reads the *caller's* `root`, not the parameter (SC2318). It passed the tests only
because both held the same value.
