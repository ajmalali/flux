---
phase: task-index-03-escalation-metric
status: done
files: [bin/flux, tests/test_flux_cli.py]
---

## objective
`escalation_rate` is a claimable ledger metric derived from the task log, so ADR 0004's
day-one claim "fills via subagents — escalation rate < 0.3 of fills" can be seeded and
scored by `flux ledger --verdict` instead of counted by hand off `flux task list`.

Contract source: `.flux/adr/0004-task-index-execution.md` — the Claims table (row 2) and
build step 3. Phase 1 and 2's settled shapes (`01-index-core.md`, `02-tiers-await-skills.md`)
still bind; this file only adds to them.

## settled shapes

**It is a window ratio, not a per-cycle metric.** Every existing claim metric comes out of
`_aggregate` over a chunk of *sessions*; escalation rate comes out of *tasks*, which carry
no session. It therefore follows `meta_tax`'s precedent exactly — a ratio summed over the
whole eligible window, with the divergence stated in the verdict line so it is never read
as a bug — and gets its own `_verdict_*` branch in `_verdict_line`, ahead of
`_verdict_general`. `_chunk_metric` is not touched.

**Numerator / denominator.** Over tasks whose `add` ts is strictly after the claim ts
(minute-normalized, the same `[:16]` slice the other verdict paths use):

- denominator = tasks that were *added as fills* = `tier == "fill"` **or** `escalate_ts`
  truthy. The second disjunct is what makes it compaction-safe: compaction rewrites an
  escalated fill's tier to `tracer` and leaves `escalated`/`escalate_ts` as the only trace
  of its fill-ness, and `flux task escalate` refuses a task that is already a tracer, so
  `escalate_ts` present ⇒ it was a fill.
- numerator = those with `escalate_ts` truthy.

**Scope resolves to a repo path, then to its task log.** `repo` ⇒ `root`; a bare name ⇒
the `_fleet_scan` entry whose basename matches; `fleet` ⇒ every adopting repo's task log
pooled (numerators and denominators summed, one ratio). Task logs are read with
`read_task_log` + `replay_tasks` — never a second parser, never a re-derivation of tier.

**Eligibility and patience** mirror `_verdict_meta_tax`: eligible sessions in scope are
counted for the cycle clock (`< LEDGER_CYCLE` ⇒ pending with the count), and a missed bar
scores `unmoved N` where N is the claim's patience once the window spans
`cycles × LEDGER_CYCLE` eligible sessions, else 1.

**An empty denominator is pending, never `moved`.** Zero post-claim fills means no signal;
`0.0 < 0.3` would score a bar nothing was measured against.

**Vocabulary.** `escalation_rate` joins `_CLAIM_METRICS`. The comment above that set says
it is "every raw key `_aggregate` produces plus two derived ratios" — amend it, since this
is the first metric from a different source.

## task
files: bin/flux, tests/test_flux_cli.py
do: add `escalation_rate` to `_CLAIM_METRICS`; add `_verdict_escalation(root, since, claim,
  op, threshold)` implementing the shapes above; branch to it in `_verdict_line` next to the
  `meta_tax` branch; add a `_task_log_for_scope` helper that maps a claim scope to the task
  log paths it covers. Update the `_CLAIM_METRICS` comment and `flux task`'s
  `task_counts` docstring (it says the escalation rate is "read by hand until the ledger
  metric lands" — it has landed).
verify: `flux check`
done: AC-1..AC-4 all green in `tests/test_flux_cli.py`

## acceptance criteria
AC-1 — Given a claim `escalation_rate <0.3` whose scope has ≥ `LEDGER_CYCLE` eligible
sessions and, after the claim ts, 5 added fills of which 1 carries `escalate_ts`, when
`flux ledger --verdict` runs, then the line reads `moved`, shows `ratio=0.20`, and says the
figure is a window ratio, not per-cycle.
AC-2 — Given the same log but 2 of 5 escalated, then the line reads `unmoved 1` (or
`unmoved 2` once the window spans two cycles) with `ratio=0.40`.
AC-3 — Given fewer than `LEDGER_CYCLE` eligible sessions, then the line reads `pending`
with the eligible-session count and no ratio.
AC-4 — Given zero fills added after the claim ts, then the line reads `pending (n/a — no
fills)`; it never reads `moved`.
AC-5 — Given a log compacted after a fill was escalated, when the verdict is recomputed,
then the ratio is unchanged (the folded record still counts in both numerator and
denominator).

## boundaries
do not change: `_chunk_metric`, `_aggregate`, `_verdict_general`, or `_verdict_meta_tax` —
the tempting refactor is a shared "ratio verdict" helper; three call sites with different
eligibility rules is not yet a pattern, and touching the two scored today would re-open
claims already accruing cycles.
do not change: the `escalate` guard that refuses a tracer — the denominator depends on it.
out of scope: the replay-check metric (done tasks failing their own verify), which ADR 0004
seeds *after one cycle*, not day one; `[task] fill_model`; any new `flux task` verb.

## verification
`flux check` green, plus: `./bin/flux ledger --verdict` run in this repo still prints every
existing claim line unchanged (the six loop claims), and `./bin/flux claim add x foo "<1"`
still rejects an unknown metric while `escalation_rate` is accepted.

## outcome — 2026-09-11
shipped: `escalation_rate` is a claimable metric. `_CLAIM_METRICS` carries it (comment
  amended: first metric sourced from the task log, not `_aggregate`);
  `_task_log_for_scope(root, since, scope)` maps repo/fleet/name to the `.flux/tasks.jsonl`
  paths it covers, through `_fleet_scan` so the fleet keeps one definition;
  `_escalation_counts(paths, claim_ts)` counts fills (`tier == "fill"` **or** truthy
  `escalate_ts`) and escalations over `read_task_log` + `replay_tasks` only;
  `_verdict_escalation` scores the window ratio with meta_tax's eligibility, patience and
  stated divergence, pending under one cycle and pending on an empty denominator;
  `_verdict_line` branches to it beside `meta_tax`, ahead of `_verdict_general`.
  `task_counts`' docstring now points at the landed metric instead of "read by hand".
  AC-1..AC-5 green as `TestVerdictEscalation` (9 tests) in tests/test_flux_cli.py:
  moved/ratio=0.20, unmoved 1 and unmoved 2 at ratio=0.40, pending-with-count and no
  ratio, `pending (n/a — no fills)` never moved, and a ratio unchanged across
  `flux task compact` (the test first asserts the folded record really did get
  `tier: tracer`, so AC-5 cannot pass vacuously). Two tests beyond the ACs: pre-claim
  fills excluded, post-claim tracers kept out of the denominator.
  Gate: 336 tests green (327 before). `./bin/flux ledger --verdict` prints the six
  existing claim lines unchanged; `claim add x foo "<1"` still exits 2 while
  `escalation_rate` is accepted (checked in a scratch repo so .flux/claims.jsonl stays
  clean for t-g5ub to seed).
deviated: one docstring inside `_verdict_general`, which boundaries listed as
  do-not-change — its first line claimed "every metric but meta_tax", which the new
  branch makes false. Text only; no behavior, no claim clock touched.
deferred: nothing from this spec. The replay-check metric, `[task] fill_model` and any
  new `flux task` verb were out of scope and stay out; replay-check is seeded after one
  cycle per ADR 0004.
