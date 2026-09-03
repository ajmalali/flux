---
phase: 02-status-diet
routing: mechanical
status: done
files:
  - .flux/plans/flux-v2/status.md                 # 111 KB → ≤ 8 KB live state
  - .flux/analysis/2026-09-03-status-history.md    # new: the frozen history cut from status.md
---

## objective
`.flux/plans/flux-v2/status.md` carries only live state — current state, the open task
queue, and the session-close checklist — at ≤ 8 KB, so the once-per-session bootstrap
read (CLAUDE.md step 1) stops costing ~28k tokens; every dated, done, and settled block
moves verbatim to one archive file so nothing is lost.

## context (do not re-derive)
- status.md today is 111 KB / 1423 lines. Section map (line: bytes):
  - header running-log `Updated:`/`Previously` blocks (2–33): 11.4 KB — **history**
  - `## Current state` (34–123): 6.5 KB — **live, but compress**
  - `## Decisions from the check-command review` 2026-08-20 (124–132): 0.5 KB — settled
  - `## Benchmark (bench/)` (133–303): 10.2 KB — mostly history; bench/ code is unaffected
  - `## meridian-003 …` (304–362): 3.8 KB — **history**
  - `## The decay premise, measured` (363–424): 4.1 KB — **history**
  - `## Task queue` (425–1417): 74.4 KB — 26 done `[x]` items + 6 `[ ]`; **the bulk**
  - `## Session-close checklist` (1418–1423): 0.35 KB — **live, keep verbatim**
- **`bin/flux` never reads status.md** (grep confirmed); no hook or test references it.
  prime renders from `state.jsonl`. So this file has exactly two consumers — the model
  reading it at session start, and git. The diet cannot break prime, the CLI, or a test.
- The 6 open `[ ]` items and their disposition (settled here so apply doesn't guess):
  - 427 loop build — **STAY** (active work).
  - 436 "Field read-out actions" — **COLLAPSE to one line**: it says of itself
    "superseded by the loop roadmap above; kept as the evidence index," and
    `.flux/plans/loop/00-roadmap.md` now maps all 13 actions to phases. Replace with a
    pointer to the roadmap + `.flux/analysis/2026-09-03-field-readout.md §5`.
  - 463 execution-index (ADR 0001) revival — **STAY** (design filed, gated, unbuilt).
  - 692 "do not adopt beads" — **ARCHIVE** (settled decision, not open work).
  - 705 whether `bench/realworld/` runs — **STAY** (open decision).
  - 1043 Phase-03 kiosk ledger before/after — **STAY**, but note it may be subsumed by
    the phase-01 `flux ledger` that now exists; leave the close call to apply/user.
- History destination is `.flux/analysis/` per the roadmap. Use ONE new file (below);
  do not scatter. The ledger scans transcripts, not `.flux/analysis/`, so a large frozen
  file there is inert — no metric moves because of where it sits.

## acceptance criteria
AC-1 — Given the rewritten status.md, when `wc -c` runs on it, then it is ≤ 8192 bytes,
and it still contains: the title, a Current-state summary, the substance of every STAY
open item (loop build, exec-index revival, bench/realworld decision, kiosk ledger
before/after), and the `## Session-close checklist` section byte-for-byte unchanged.
AC-2 — Given the new archive file, when you compare it against the pre-diet status.md,
then every block cut from status.md (the running-log, the three dated analysis sections,
the check-command decisions, the Benchmark writeup, all 26 done `[x]` items, and the
beads decision) is present in the archive verbatim — no cut content survives only in git.
AC-3 — Given the changes, when `flux check` runs, then it is green (207 tests), and
`./bin/flux prime` in this repo still renders its normal pack — the CLI never touched
status.md, and this AC guards that nothing else did either.

## tasks
### T1 — Extract the frozen history into one archive file
files: .flux/analysis/2026-09-03-status-history.md
do: create the archive with a one-paragraph header ("Frozen history cut from
`.flux/plans/flux-v2/status.md` on 2026-09-03 by loop phase 02; live state stayed in
status.md. Read-only record."), then append, under clearly labelled sub-headings and in
original order, the exact text of: the `Updated:`/`Previously` running-log (lines 2–33),
`## Decisions from the check-command review` (124–132), `## Benchmark (bench/)` (133–303),
`## meridian-003 …` (304–362), `## The decay premise, measured` (363–424), every done
`[x]` task-queue item, and the `[ ]` beads decision (692). Copy verbatim — do not
summarize; summarizing is what loses the rationale.
verify: `wc -c .flux/analysis/2026-09-03-status-history.md` is within a few hundred bytes
of the summed section sizes above (~95 KB); `grep -c '^\- \[x\]'` on it returns 26.
done: AC-2 when a spot-diff of three cut blocks (running-log head, the beads item, one
done item) finds them verbatim in the archive.

### T2 — Rewrite status.md to the ≤ 8 KB live skeleton
files: .flux/plans/flux-v2/status.md
do: replace the file with, in order: (1) the `# flux-v2 — status & next task` title +
one dated line and a ≤ 3-sentence "where we are now" summary (loop phase 01 ledger
shipped; phase 02 status diet in progress; 207 green) — not the 11 KB running-log;
(2) a compressed `## Current state` (≤ 2.5 KB: the pivot is done, `bin/flux` is the
single-file stdlib CLI, phase 01 ledger exists — keep the load-bearing facts, drop the
prose); (3) `## Task queue` holding only the STAY open items (loop build, exec-index
revival, bench/realworld decision, kiosk ledger before/after) tightened, plus the one
collapsed pointer line replacing the field-read-out block; (4) `## History` — three
pointer lines to `.flux/analysis/2026-09-03-status-history.md`, the dated
`.flux/analysis/*.md` studies, and `.flux/plans/loop/`; (5) the `## Session-close
checklist` section pasted verbatim from the old file. Keep total ≤ 8192 B (headroom
target ~6 KB).
verify: `wc -c .flux/plans/flux-v2/status.md` ≤ 8192; `diff <(sed -n '/## Session-close/,$p'
old) <(sed -n '/## Session-close/,$p' new)` is empty (old = `git show HEAD:.flux/plans/flux-v2/status.md`).
done: AC-1 when the byte count and the four required contents are present.

## boundaries
do not change: `bin/flux`, any hook, `plan.md`, `state.jsonl`, or the tests — this is a
docs move only. Do not rewrite `00-roadmap.md` or `01-flux-ledger*.md`. Do not delete
any open item's substance (only the field-read-out block collapses, because the roadmap
already carries it). Keep the `## Session-close checklist` text identical — CLAUDE.md
binds sessions to execute it.
out of scope: the read-out actions themselves (items 1–13 are phases 03–08, not this
one); trimming the roadmap or the ledger docs; applying the same diet to any adopting
repo's status.md (radiator/kiosk) — this phase is the flux repo only.

## verification
`flux check` green (207), plus: `wc -c` on status.md ≤ 8192; the Session-close section
diffs clean against `git show HEAD`; the archive holds the 26 done items. The phase's
**claim** — flux-repo ctx p50 94k → < 75k — is not falsifiable at apply time; it is read
next cycle by `flux ledger --since <today>` in this repo and recorded then (phase 05).
Note that in the phase `## outcome` for the wrap.

## coherence
Checked against `00-roadmap.md` (this is its phase 02, mechanical, claim matches),
CLAUDE.md (Current state, task queue, and Session-close checklist all survive, so
bootstrap step 1 and the session-close binding still hold), and `open` (no live item is
dropped; the kiosk conflict metric and ADR-0001-gated notes move to archive intact). No
contradiction found. One call made explicit above rather than left to apply: the
field-read-out block collapses to a roadmap pointer because it declares itself superseded.

## outcome — 2026-09-03
shipped: status.md cut 111 KB/1423 lines → 5,140 B/74 lines — title + dated summary,
compressed Current state, the four STAY open items, one collapsed field-read-out
pointer, a History section, and the Session-close checklist byte-for-byte unchanged
(diff vs HEAD empty). Frozen history moved verbatim to
`.flux/analysis/2026-09-03-status-history.md` (99.5 KB): running-log, check-command
decisions, Benchmark write-up, meridian-003, decay premise, all 26 done `[x]` items,
and the beads decision. AC-1/2/3 all met; `flux check` green (207).
deviated: archive is 99.5 KB vs the plan's approximate ~95 KB estimate — the delta is
the added header + sub-headings + block separators, not extra content; verbatim
spot-diffs (running-log head, beads, meridian-007) and the 26-item count hold, so
substance is exact. No boundary crossed: only status.md + the new archive were written.
deferred: the phase **claim** (flux-repo ctx p50 94k → <75k) is not falsifiable at
apply time — it is read next cycle by `flux ledger --since 2026-09-03` in this repo and
recorded in phase 05. The kiosk-ledger-subsumption call was left open in the queue
rather than closed here, for a session that actually re-reads the ledger.
