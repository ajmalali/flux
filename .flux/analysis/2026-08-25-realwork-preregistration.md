# Pre-registration — flux on a live multi-phase project

Date: 2026-08-25
Ledger rule: `plan.md` principle 5 — *each capability names the ledger metric it
must move; two reporting cycles with no movement ⇒ delete it.*
Status of the ceremony question before this note: three benchmark nulls
(meridian-003/004/007) on **briefed** work, one positive real-work datapoint
(kiosk Phase 02) on **incomplete self-authored** work. The two do not contradict;
they measure different cases. This note measures the second case on purpose.

## Why pre-register at all

This project decides by pre-registration: a falsifiable claim is written down, in
a commit, *before* the number is read. Every prior decision here followed it —
the mattpocock retirement, the agent-roster deletion, the api null, all stamped
before the measurement. The open state records the cost of the alternative in one
line: *"when a falsifiable claim was demanded, none survived."* A post-hoc read of
the logs after a project is done would break the method that produced every result
so far. So the questions go here first.

## The trap this is written to avoid

Retrospective logs answer **"how much,"** never **"was it worth it."** A transcript
records that `/flux:apply` ran and that a primed pack was in context. It cannot
record whether the pack *saved* the session or whether the session re-derived the
same facts from `git log` and the pack happened to agree. This is the identical
gap that made the ceremony question un-answerable by the benchmark: value is a
counterfactual, and transcripts hold activity, not counterfactuals.

So the measurement is split. Counts are mined from the logs after the fact.
Value signals are captured **live, one line at a time**, or they are gone.

## What is recoverable retrospectively (mine after; set up nothing)

Read from transcripts + `.flux/` + git once the project is done:

1. **Which lifecycle skills were invoked, how often, in which sessions.**
   `scripts/skill-utilisation.py <prefix>` reads both invocation paths — the
   `Skill` tool-use and the `/flux:x` slash command. This is the denominator work
   the earlier audits established: count both paths, bill only sessions that
   carried the thing.
2. **Whether wrap ran each session.** `.flux/state.jsonl` records every write with
   a timestamp; a session that ended without a state write did not wrap.
3. **Whether plans closed.** git history of `.flux/plans/` — `status: done`
   vs `partial`, and whether each `## outcome` block recorded deviations.
4. **Session count and cost per phase.** From the session records / usage data.
5. **Did the next session do what `next` said?** Compare the `next` string wrap
   wrote against the first action the following session actually took.

## What is NOT recoverable — the field log (`.flux/field-log.md`)

These three vanish at session end. Append **one line** to `.flux/field-log.md`
whenever one occurs — nothing more, or the instrument itself becomes ceremony:

- **`[audit-hit]`** — audit found something real (a false plan premise, a stale
  SHA, a wrong "X already handles Y"). One line: what it caught. This is the
  kiosk-Phase-02 signal; it is the entire case for keeping audit.
- **`[pack-miss]`** — the primed pack was wrong, stale, or ignored, and the
  session re-derived from the tree instead. One line: what was missing or wrong.
  This is the case *against* prime/state, and the only honest source of it.
- **`[want]`** — a moment of wishing flux did something it does not. One line:
  what. This is the entire "what to add" question; it exists nowhere else.

Format, so it is greppable later:
```
2026-08-DD  [audit-hit]  plan claimed CI runs the e2e suite; it does not — apply would have shipped red
2026-08-DD  [pack-miss]  next said "phase 03" but 03 was already half-done in the tree; reconcile caught it
2026-08-DD  [want]        wanted flux to carry the ADR that says "prefer X over Y"; the 2k pack dropped it
```

## The claims, falsifiable, registered now

- **C1 (wrap pays).** In a project spanning ≥3 sessions, sessions that opened on a
  wrapped pack reached their first substantive edit with fewer re-derivation reads
  than the count of `[pack-miss]` lines would imply. *Falsified if* `[pack-miss]`
  is the common case — i.e. the pack is routinely wrong and the tree is read
  anyway. Then prime/state is theatre and wrap's write is the only real part.
- **C2 (audit pays on incomplete plans).** At least one `[audit-hit]` lands on a
  self-authored plan across the project. *Falsified if* audit runs and catches
  nothing across every phase — then the kiosk datapoint was noise and audit joins
  the benchmark nulls.
- **C3 (plan earns its session only when the shape is unsettled).** Phases routed
  `design` produce `[audit-hit]`s or plan revisions; phases routed `mechanical`
  that were planned anyway show the plan restating `next` with no recovered value.
  *Falsified if* mechanical phases also benefit — then plan is worth it always, not
  conditionally, and the "go straight to apply" advice is wrong.
- **C4 (the carrier is the whole story).** Every `[pack-miss]` and `[want]` is a
  fact about *what flux surfaced*, not about how good the model is. *Falsified if*
  a field-log line describes flux improving the code itself rather than the model's
  view of it — which would be the first evidence in the whole corpus that flux
  moves quality, and would reopen everything.

## The read-out

When the project closes: mine the five retrospective counts, tally the field log
by tag, and judge C1–C4 against what was registered here — not against a fresh
rationalisation. Then, and only then, revisit KEEP/REMOVE/ADD for plan/audit/wrap.
The DECIDE item resolved to KEEP *pending this*; this is the bar that could move it
either way.

## Convention decided alongside: grill → plan, not grill *in* plan

Grilling stays a separate skill. Folding a divergent interrogation loop into the
convergent one-file planner would uncap plan's cost (its whole discipline is "read
narrow, write one file, stop") and fork the vendored `grill` away from
`scripts/sync-vendored.sh`. Use them in sequence: when a phase's shape is genuinely
unsettled — for a port, that is the first phase, deciding how to slice it — run
`/flux:grill` first, then `/flux:plan` writes down what survived. Each skill does
one job; the vendored boundary stays intact.
