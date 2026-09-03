# flux-v2 — status & next task

Updated: 2026-09-03 — loop phases 01 (`flux ledger`), 02 (status diet), 03 (`flux log`
+ pack footer), and 04 (guard/age/seal hooks) shipped, gated, wrapped (238 green); phase 05
(claims + cycle line) is **planned** (`.flux/plans/loop/05-claims-cycle.md`, design, 4
tasks, unbuilt) — next is `/flux:apply` it (audit recommended first). Where we are: the v1→v2 pivot is done, `bin/flux` is the single-file stdlib CLI,
phase 01's `flux ledger` mines transcripts into the field read-out's targets table, and
phase 03 added `flux log <tag> "…"` → `.flux/field-log.md` plus a prime pack footer naming
the four session verbs. History moved to `.flux/analysis/2026-09-03-status-history.md`;
this file is live state only.

## Current state

- **Pivot executed.** v1 orchestration harness is archived (tag `v1-final`,
  `.flux/archive/v1/`, rationale ADR 0012 there). This repo is the flux v2 plugin +
  self-marketplace described in `plan.md`.
- **`bin/flux`** — single-file stdlib CLI (Python ≥3.9, tomllib fallback):
  init/prime/state/check/handoff/run/**ledger**/**log**/**guard**/**seal**, byte-budgets enforced (tokens ≈
  bytes/4), prime hook-safe (never fails, silent no-op without `.flux/`). `flux check` is
  the fixed gate — no args, no narrowing; scoped runs go through `flux run --filter`. Prime
  ends with a pack footer naming the verbs (gate/subset/close/log, 143 B). `flux log <tag>
  "…"` appends budget-clipped entries to `.flux/field-log.md` (created by `flux init`).
- **Phase 01 ledger is in and green.** `flux ledger [--since] [--fleet] [--json]` mines
  on-disk transcripts into the targets table per cycle, budget-clipped, with a fleet view +
  `meta-tax` line; 23 tests + a checked-in golden fixture, **207 green**. Reproduces the
  field read-out (rpi TOTAL: 16 substantive sessions, ctx p50 87k, 0 sessions >150 req,
  11/16 wrapped, $193). Evidence: `.flux/plans/loop/01-flux-ledger.status.md`.
- **Plugin** installs from directory source `~/Dev/flux` (marketplace `flux@marketplace`);
  `claude plugin update flux@marketplace` needs the `@marketplace` suffix and only takes
  after a `plugin.json` version bump. `plugin.json` must NOT name `hooks/hooks.json` (it is
  auto-loaded; naming it disables the plugin silently). flux now injects nothing
  model-visible but `prime` — 0 skills listed, 0 agents (both retired on the utilisation
  bar; the history file carries the reasoning).
- **Phase 01 is closed; nothing open in it.**

## Task queue

- [ ] **Build the loop — `.flux/plans/loop/` (ADR 0003, accepted 2026-09-03).** Roadmap
  `00-roadmap.md` maps every field-read-out action to eight phases, each with the claim it is
  judged on. 01 ledger + 02 status diet + 03 `flux log`/footer + **04 guard/age/seal DONE**
  (`.flux/plans/loop/04-guard-age-seal.md`, `status: done`; 238 green, plugin.json 2.11.0).
  04 shipped: `flux guard` on UserPromptSubmit reuses `_scan_session[requests]` and *nudges*
  (never exit-2) past `warn_requests`=120 (anti-nag via `cache/guard.json`); prime suffixes
  stale keys ` [Nd]` from the state-log ts and warns after an unwrapped session; `flux seal`
  on SessionEnd is transcript-free — reads `cache/last-wrap` (dropped by `_touch_wrap` on
  every `state set`/`handoff`) vs `cache/last-prime` mtime to log `unwrapped` + set the seal
  marker. Adopting repos get the two new hooks on their next session (plugin update). **05
  (claims + cycle line) PLANNED** (`.flux/plans/loop/05-claims-cycle.md`, design, 4 tasks):
  `.flux/claims.jsonl` (append-only, `{ts,feature,metric,bar,scope,cycles}`), `flux claim
  add`, `flux ledger --verdict` (scores each claim over post-claim cycles →
  pending/moved/unmoved-N, reusing the ledger's own chunking + meta-tax, never a second
  definition), and a flux-repo-only cached prime cycle line. T4 seeds this cycle's real
  claims (02 ctx_p50, 03 help_reads, 04 over_cap + wrap_coverage, 00 meta_tax) — they read
  `pending` at apply, judged 2 cycles out. **Next: `/flux:apply` (audit recommended first —
  verdict chunking + prime cache have trap surface).** Then 06 handoff inline, 07 deletions
  (user decides), 08 optional. One phase per session; wrap every session.
- [ ] **Execution index (ADR 0001) revival — design filed, nothing built.** Design doc
  `.flux/analysis/2026-08-26-execution-index-revival-design.md`. Revive the suspended ADR 0001
  as `flux task add|start|done|block|next|list` over a `tasks.jsonl` op-log (ADR 0002's
  union-merge reused; `blocked` computed on read). Division of labor: mattpocock plans; flux
  decomposes **once** + executes, carrying `routing`+`files` the tickets have no slot for.
  ADR 0001's frontier justification is *spent* (prime already eats the ramp) and may not be
  re-used — the revival rests on declared-files + per-task routing instead. **Gated** behind
  the real-work pre-registration: build only if a live multi-phase feature logs
  `[pack-miss]`/`[want]` and `./bench/run.py ramp` shows a code-bucket worth attacking. Two
  user decisions left in the doc: canonical store, id assignment across parallel branches.
- [ ] **Decide whether `bench/realworld/` runs at all, and in which shape.** Cheapest useful
  version: a one-milestone pilot on three arms (vanilla, flux, flux-lite), ~6 sessions, to
  check the corpus has teeth and the analyser works before committing 25–50 operator hours.
- [ ] **First `flux ledger` before/after in kiosk** (Phase 03 remnant; may now be subsumed by
  the phase-01 ledger — leave the close call to a session that reads it). The after-side is
  n=1 and accrues one datapoint per real interactive kiosk session; the before-corpus erodes
  under the CLI's 30-day transcript cleanup. Re-read `ramp`/`ledger` once a handful more kiosk
  sessions have landed, rather than treating this as an on-demand action.
- The 2026-09-03 field-read-out actions are the loop's phases 03–08 — the 13-action evidence
  index lives in `.flux/plans/loop/00-roadmap.md` and
  `.flux/analysis/2026-09-03-field-readout.md` §5, not re-listed here.

## History

- `.flux/analysis/2026-09-03-status-history.md` — this file's frozen running-log, the
  benchmark write-up, the meridian-003/decay analyses, the check-command decisions, the beads
  decision, and all 26 completed task-queue items (verbatim).
- `.flux/analysis/*.md` — dated field studies (2026-09-03 field read-out, the ceremony
  cycles, mattpocock utilisation bar, execution-index revival design, …).
- `.flux/plans/loop/` — the loop roadmap and its per-phase plans and status files.

## Session-close checklist (execute at the end of EVERY working session)

1. `flux check` green (or the failure documented here).
2. `flux state set` — phase/position/next reflect reality.
3. Update this file: current state, queue, anything a fresh session must not re-derive.
4. Commit (docs included). Never leave the repo dirty across sessions.
