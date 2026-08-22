# ADR 0001: the execution frontier is a procedure, not a judgment

Date: 2026-08-22
Status: Accepted
Line: opens the v2 ADR line (the v1 line was closed by `.flux/archive/v1/adr/0012-plugin-pivot.md`)

## Decision

`bin/flux` gains a **local execution index** — tasks with blocking edges, statuses, and
declared files — and the verbs to maintain it. `flux task next` computes the next
unblocked task by topological order, in code, with no model in the loop.

Three rules ride with it:

1. **Task size is budget-checked.** `flux task add` estimates the context a task will
   cost and **warns** above `[task].budget_tokens`, recording the estimate.
   *Amended 2026-08-22 — originally "refuses ... exactly as `flux state set` refuses
   an oversized write". The prerequisite measurement came back without a knee, and a
   refusal needs a cliff. See the Prerequisite section.*
2. **Ceremony scales with size.** A single small task runs apply-only. Plan, audit and
   wrap attach to phase and feature boundaries, not to every unit of work.
3. **Done is recorded, not asserted.** `flux task done` requires what verified it;
   `/flux:wrap` reconciles claims against records.

This **reverses `plan.md`'s "ticket store — out of scope"**. See "What changed our
mind" and "Why this is not a tracker" below.

## Context

**The measured problem.** `bench` run `meridian-003`: `flux` delivered 4/4 at
$2.92/task across 4 sessions; `flux-lite` — the same machinery with no lifecycle
ceremony — delivered the same 4/4 at $1.05 in 1 session, and beat `flux` on every
efficiency column. By the falsifiability rule the lifecycle was due for deletion.

**Why that verdict does not mean what it appears to.** Every meridian task fits
comfortably in one session, and every arm scored 82/82 acceptance tests. In that
regime decomposition machinery has nothing to decompose, so it can only show up as
overhead — and a corpus on which everyone is perfect can rank cost and nothing else.
The benchmark measured the regime where flux's thesis is inert and correctly reported
that flux cost more there. It has never measured the regime flux exists for.

**The structural problem, which is separate and real.** `plan.md` already declares the
big-feature path — *"Big-feature altitude: wayfinder → to-spec → to-tickets →
/flux:plan per ticket"* — and the skills implement their halves:

- `plan` sizes work honestly (*"2–3 tasks … work that fits before quality decays"*)
  and, when work is too big, says **split into sequential phase plans and write only
  the first**;
- `wayfinder` charts work "more than one agent session can hold", with tickets "sized
  to one 100K token agent session";
- `to-tickets` writes tickets with blocking edges to local files.

And then the road vanishes. Only the first plan is written; the decomposition of
everything after it lived in the planning session's context, and that session ended.
What crosses the boundary is `state.toml`: five prose fields, 2000-token budget, no
ledger of what is done, no edges, no remainder.

So every cold session **re-derives the frontier by reading** — which is where the
context goes, and which is the exact opposite of deterministic. `bin/flux` cannot read
a single ticket file that `to-tickets` writes.

## Why this shape

Principle 1 says skills hold judgment and never procedures a script could own.
*Deciding what the tasks are* is judgment and stays in `plan` / `to-tickets` /
`wayfinder`. *Deciding which task is next* is a topological sort over a DAG — the most
procedural operation in the entire system, and the one procedure that never moved into
the CLI. Leaving it with the model costs a re-derivation every session and produces a
different answer each time. Both are exactly what flux exists to eliminate.

Task sizing gets a weaker version of the same treatment. `wayfinder` already names a
session-sized budget and nothing checks it; an unchecked budget is a comment.
Principle 2 says budgets are refused rather than aspirational — but a refusal has to
protect a real limit, and the prerequisite measurement (below) found a gradual cost
curve rather than a limit. So this one warns and records instead of refusing, and the
warning is falsifiable on the re-read metric it is meant to move.

## Why this is not a tracker

`plan.md` ruled out a ticket store, and that ruling was right about what it was
refusing: flux should not own the artifact humans plan against, sync to GitHub or
Linear, or grow a parser for another framework's format. None of that changes.

What is being added is narrower and differently shaped:

| ticket store (still out of scope) | execution index (this ADR) |
|---|---|
| the artifact humans read and plan against | an index only the CLI and a cold session read |
| syncs to an external tracker | local, never synced |
| holds discussion, rationale, history | holds id, status, edges, files, verification |
| the model curates it | the CLI owns writes; the model calls verbs |

Tickets for people keep living in the tracker `to-tickets` and `wayfinder` publish to.
This index exists so that `flux prime` can answer "what is next" in one line without
a model, and so `flux task next` returns the same answer twice.

## What changed our mind

`plan.md` excluded a ticket store when flux's target was one phase at a time, where
`state.toml`'s prose fields carry enough. The stated goal has since widened to long
projects with many features spanning many sessions, and at that altitude prose does not
survive: a sentence cannot express thirty tasks, their edges, and which nine are done.
The exclusion was correct for the old scope and is wrong for the new one.

## Ledger metrics (falsifiability, per principle 5)

| capability | metric it must move | falsifier |
|---|---|---|
| execution index + `task next` | cold-start ramp — tokens and tool calls before the first `Edit`/`Write` of a session | ramp does not shrink ⇒ the frontier was not where context went; delete it |
| task-size budget | re-read rate above the threshold (`./bench/run.py decay`) — *amended 2026-08-22 from "quality (held-out acceptance pass rate)", which the corpus cannot measure* | sizing tasks under the budget does not lower the re-read rate ⇒ drop the budget |
| size-conditional ceremony | $ and sessions per delivered task on small work | does not converge to `flux-lite` on small tasks ⇒ ceremony still is not earning it |
| verified-done | tasks marked done that fail their own `verify` when replayed | rate already ~0 ⇒ the bookkeeping is theatre |

Two reporting cycles without movement deletes the capability, as with everything else.

## Prerequisite: checked, 2026-08-22 — the premise did not survive

Full method and figures: `.flux/analysis/2026-08-22-context-decay.md`. Re-runnable as
`./bench/run.py decay` (code in `bench/fluxbench/decay.py`, 15 tests).

414 transcripts, 16,909 main-chain tool calls, 344 sessions. **There is no knee.**

- **Correctness is flat.** Edit/Write failing on a stale string or an unread file —
  the only proxy that is about the model's picture of the code being wrong — runs
  0.91% / 0.89% / 0.73% / 0.85% / 1.37% across the 75k → 300k+ bins within one model
  family. The pooled all-model version *does* show 2.92x at p=0.0038, and that is
  Simpson's paradox: sonnet and haiku sessions never exceed 200k and sit near zero.
- **Re-orientation cost rises, with a step at ~100k — not at 200k.** Reading a file
  already among the last five files read: 10.7% / 9.2% below 100k, then 26.6% / 28.9%
  / 32.6% above. Within-session, same direction at every cut, sign-test p=0.09 at
  200k, p=0.22 at 100k. Suggestive, not proven.
- **Churn does not rise.** The naive version (re-touching any already-touched file)
  climbs 26% → 76%, but that is arithmetic — the touched set only grows. Normalised
  to a fixed window it is flat, and within-session it *falls*.
- **57% of raw tool errors are permission friction**, which clusters at session start.
  Counted naively the tool-error rate falls fivefold with context and reads as proof
  that context helps. (This is also a live defect in `bench`'s reported
  `tool_error_rate` — a follow-up task.)

**What this changes.** Rule 2 loses its refusal, above. What a long context is shown
to cost here is *re-reading* — dollars and wall-clock — not correctness, which is
consistent with `meridian-003`, where every arm scored 82/82 and only cost separated
them. The threshold, if one is set, is ~100k.

**What it does not settle.** Detecting the observed correctness difference at 80%
power needs ~18,700 Edit calls per side; there are ~1,300 — underpowered by 14x. So
"flat" means *an effect large enough to justify refusing work is absent*, not *there
is no effect*. Only 65 sessions on this account ever pass 200k, so more mining will
not close that gap. The correctness claim is **deferred to a designed run** — the same
task executed at deliberately different context loads and graded on acceptance — and
must not be asserted in `plan.md`'s targets table until one exists.

## What is explicitly not built

No tracker sync. No parser for PAUL / agent-os / Linear formats — that remains the
per-project fork `plan.md` rules out. No automatic decomposition: the CLI stores and
orders tasks, it never invents them. No scheduler, no parallel execution, no
auto-advance to the next task without a session boundary.

## Consequences

- `plan.md` gains the amendment recorded alongside this ADR; "ticket store" in Out of
  scope is qualified rather than deleted.
- `bench` must change shape to test any of this: hand the corpus over whole, let each
  arm decompose it, and grade continuously. A pre-decomposed corpus tests decomposition
  machinery not at all — the flaw that made `meridian-003` unable to speak to it.
- `plan.md`'s targets table must stop asserting that quality decays with context
  until a designed run establishes it (added 2026-08-22).
- `.flux/state.toml` stays as it is. It carries the narrative; the index carries the
  road. Neither grows into the other.
