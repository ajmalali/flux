# ADR 0001: the execution frontier is a procedure, not a judgment

Date: 2026-08-22
Status: Accepted
Line: opens the v2 ADR line (the v1 line was closed by `.flux/archive/v1/adr/0012-plugin-pivot.md`)

## Decision

`bin/flux` gains a **local execution index** — tasks with blocking edges, statuses, and
declared files — and the verbs to maintain it. `flux task next` computes the next
unblocked task by topological order, in code, with no model in the loop.

Three rules ride with it:

1. **Task size is budget-enforced.** `flux task add` estimates the context a task will
   cost and **refuses** one that exceeds `[task].budget_tokens`, exactly as
   `flux state set` refuses an oversized write today.
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

Task sizing gets the same treatment. `wayfinder` already names a session-sized budget
and nothing checks it; an unenforced budget is a comment. Principle 2 says budgets are
refused, not aspirational.

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
| task-size budget | quality (held-out acceptance pass rate) as a function of context at execution | no decay knee in the data ⇒ the smart-zone premise is wrong; drop the budget |
| size-conditional ceremony | $ and sessions per delivered task on small work | does not converge to `flux-lite` on small tasks ⇒ ceremony still is not earning it |
| verified-done | tasks marked done that fail their own `verify` when replayed | rate already ~0 ⇒ the bookkeeping is theatre |

Two reporting cycles without movement deletes the capability, as with everything else.

## Prerequisite: the premise has not been checked

The size budget assumes quality decays as context grows. That is asserted in
`plan.md`'s targets table and in `plan`'s own wording, and it has never been measured
on this account's data. Before the budget is built, mine the existing transcripts
(~83 in this repo, several hundred across `~/.flux-bench/runs`) for context-at-request
against tool error rate, redundant re-reads, and file churn. Those are proxies, not
quality — but if no relationship appears in them, the budget is being built on a guess
and this ADR's second rule should be reconsidered before any code is written.

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
- `.flux/state.toml` stays as it is. It carries the narrative; the index carries the
  road. Neither grows into the other.
