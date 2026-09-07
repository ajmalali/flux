# flux-v2 — status & next task

Updated: 2026-09-07 (README rewritten as a concise user guide: install, hooks, commands, skills, per-scenario workflows) — loop phases 01–06 plus **07 (deletions)** shipped, gated, wrapped
(**267 green**); phase 07 closed `.flux/plans/loop/07-deletions.md` (`status: done`) —
`routing` removed everywhere (pack −1 line), the eight zero-use skills deleted (skills dir
14 → 6: `adopt/apply/audit/grill/plan/wrap`), `sync-vendored.sh`/`VENDORED.md`/`README`/
`plan.md`/`CLAUDE.md` made grill-only + four-lifecycle, and the adopt recipe folded inline
(capped) into `flux init` output. `flux run` put on notice, kiosk conflict metric closed —
see the "On notice & closed metrics" block below. Only 08 (optional) remains in the loop.
Next is `/flux:plan` loop phase 08 (gate-bypass nudge + heartbeat, design — user decides if
it's worth building). Where we are: the v1→v2 pivot is done, `bin/flux` is the single-file stdlib CLI,
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
  (claims + cycle line) DONE** (`.flux/plans/loop/05-claims-cycle.md`, `status: done`; 264
  green): `.flux/claims.jsonl` (append-only, `{ts,feature,metric,bar,scope,cycles}`), `flux
  claim add` (rejects unknown metric / bad bar; warns-but-appends on a duplicate open
  feature+metric), `flux ledger --verdict` (scores each claim over post-claim cycles →
  pending/moved/unmoved-N; `_fleet_scan` extracted from `_ledger_fleet` and shared;
  `meta_tax` special-cased as a fleet window ratio, not per-chunk; None/inf → pending;
  minute-normalized eligibility; verdict is the first branch in `cmd_ledger`, `--json`
  ignored), and a flux-repo-only cached prime cycle line (`.flux/cache/cycle.json`,
  `cycle_refresh_hours`=6, own try/except so a bad cache never blanks the pack).
  `FLUX_LEDGER_ALLOW_TMP=1` bypass in `_is_adopting_repo` (test-only, off by default). Five
  claims seeded (02 ctx_p50<75000 repo · 03 help_reads==0 fleet · 04-guard over_cap==0 fleet
  · 04-seal wrap_coverage>=0.8 fleet · 00 meta_tax<0.5 fleet) — all `pending` today, judged 2
  cycles out (unproven → tracked in `open`). **06 (handoff inline) DONE**
  (`.flux/plans/loop/06-handoff-inline.md`, `status: done`; 267 green): `handoff_budget_bytes`
  + `DEFAULT_HANDOFF_BUDGET_TOKENS`=1200 (optional `[state] handoff_budget_tokens` knob), `flux
  handoff` clips to that cap not the state budget, and `_prime_inner` inlines the latest
  handoff under `last handoff (<base>), inlined:` (body clipped to the handoff cap; blanket
  try/except falls back to the old naming line on read-error/empty). Footer survival: reserve
  `len(PACK_FOOTER)+1` before the final body clip, append footer last; degenerate `budget <
  footer` case (only the artificial 10-token budget test) falls back to a whole-string clip so
  the budget invariant always wins. Sixth claim seeded (`06-handoff-inline first_edit <=8`
  fleet) — `pending`. **07 (deletions) DONE** (`.flux/plans/loop/07-deletions.md`, `status: done`; 267 green): `routing` removed (pack -1 line; `STATE_KEY_ORDER` + pack tuple + `[routing]` toml block dropped; `cmd_state set` unchanged so sample-key tests stay green), eight zero-use skills deleted (skills dir 14 to 6), `sync-vendored.sh` wires only `grill`, docs (`VENDORED.md`/`README`/`plan.md`/`CLAUDE.md`) grill-only + four-lifecycle, adopt recipe folded inline (capped) into `flux init`. No new claim (validated structurally + green tests). **Next: `/flux:plan` 08 optional (design)** gate-bypass nudge on `PreToolUse` + session heartbeat; user decides whether to build the loop's last phase. One phase per session; wrap
  every session.
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

## On notice & closed metrics (loop phase 07, 2026-09-07)

- **`flux run` is on notice.** 0 uses in 44 sessions (field read-out item 12). The
  command and its `[run]` config stay for now; **delete next cycle if it is still at 0**.
  No code change this phase — this is the pre-registered kill condition, recorded so a
  later session acts on it rather than re-deriving it.
- **Kiosk conflict metric closed — unmeasurable** (item 13, F12). Only 1 commit touching
  `state.jsonl` and 0 merges since 2026-08-24, so the metric has no denominator; it is
  closed, not failed. The `state.jsonl` union-merge machinery itself (the merge driver +
  `.gitattributes`) stays wired — only the *metric* is closed.
- **Phase 07 deletions shipped:** the `routing` state key/machinery is gone (pack prints
  one fewer line; `STATE_KEY_ORDER`, the pack tuple, and the `[routing]` toml template
  block all dropped), the eight zero-use skills are deleted (skills dir 14 → 6: `adopt,
  apply, audit, grill, plan, wrap`), `sync-vendored.sh`/`VENDORED.md`/`README.md`/`plan.md`/
  `CLAUDE.md` updated so a re-sync resurrects only `grill`, and the adopt recipe is folded
  inline into `flux init` output (capped to the scan budget). No new claim seeded —
  deletions are validated structurally (14 → 6, pack −1 line) and by green tests, not by a
  metric that must move.

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
