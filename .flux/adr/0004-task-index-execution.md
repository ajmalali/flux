# ADR 0004: the task is the unit — a tiered, human-aware execution index

Date: 2026-09-10
Status: Accepted, **unbuilt**. Supersedes ADR 0001 (suspended) and absorbs
`.flux/analysis/2026-08-26-execution-index-revival-design.md`. Line: v2. Glossary:
`CONTEXT.md` at the repo root. Grilled 2026-09-10 in three rounds; every question
below was put to the user and settled.

## Decision

A grilled design is decomposed once into `.flux/tasks.jsonl`, an append-only op-log
replayed like ADR 0002's state. **The task, not the phase, is what a session
executes.** Tasks carry a tier and may wait on a person. Storage, ordering, leases and
the prime line are procedure in `bin/flux`; what the tasks are, and whether to batch
them, is judgment in the skills.

1. **Two tiers, one direction.** `tracer` cuts a thin end-to-end slice, runs in the
   parent session on a frontier model, and earns a full four-line plan spec in a file.
   `fill` widens a proven slice from a one-line intent, specified by the parent at
   pickup and dispatched to a subagent. Tier is a default the executor may raise to
   tracer (`escalate`), never lower. Fills implicitly block on their tracer; explicit
   `blocks` edges sit on top.
2. **A session is one tracer or one batch, never both.** A tracer session gives the
   parent's whole context to judgment. A batch session dispatches runnable fills in
   dependency order and the parent edits nothing. `flux task next --all` lists every
   runnable task; the apply skill decides sequential or parallel, and parallel only on
   disjoint declared files. The CLI holds no scheduler.
3. **Escalation, not retry.** A subagent returning `NEEDS_CONTEXT` or `BLOCKED` gets an
   `escalate` op and the batch moves to the next independent fill. The parent never
   retries a fill itself. After a parallel batch the gate runs once; if red, each
   fill's own `verify` is re-run and the failing one is escalated. Green fills stay.
4. **Awaiting-human is a status.** A task whose verify is a human observation enters
   `await` with the steps recorded; `next` returns it first, prime prints the steps
   clipped to ~300 bytes, the handoff carries them whole, and the session ends there.
   Resolution is `done --by "<what was observed>"` or `reopen`. A verification-only
   task with no files is allowed when one check covers several tasks. No subagent
   ever holds an awaiting-human task.
5. **Leases make worktrees safe; flux never creates one.** `start` writes a lease under
   git's common dir (shared by every worktree on the machine, untracked); `next` skips
   leased tasks; leases die with the session. A second machine is uncoordinated and
   `list` flags a task with two live start records after merge.
6. **Ids are derived, not counted.** `t-` plus four base32 chars from a hash of
   timestamp and title. Add order tiebreaks by timestamp.
7. **Prime derives `next` from the index** whenever it has open tasks; the state key is
   override and fallback. `phase` leaves the pack when an index exists — the current
   tracer is the phase. Done tasks stay in the index as one record each after
   compaction; there is no archive file.
8. **Fill subagents inherit the parent's model** until the escalation rate justifies a
   cheaper default, at which point a `[task] fill_model` knob is added with its own
   claim.
9. **The lifecycle skills are rewritten in place**, roster unchanged: plan decomposes
   into the index and writes tracer specs; apply takes `next` or a batch; wrap marks
   done with evidence and reconciles claims against the tree.

## Why this reverses the 2026-08-26 gate

The design doc forbade building until a live feature logged `[pack-miss]`/`[want]`
against a flat queue. The user chose to build the full surface now, accepting the risk
flux's own scar tissue warns about (two "obviously right" agents deleted at zero use),
because the workflow this enables — autonomous fills, human checkpoints, one task per
session — cannot be dogfooded on a flat queue at all. The claims below are the
replacement for the gate: two cycles unmoved deletes the piece, as everywhere else.

## Claims

| piece | metric | bar | seeded |
|---|---|---|---|
| session rule + index | ctx p50 | < 100k on radiator once adopted (from 170k) | day one |
| fills via subagents | escalation rate | < 0.3 of fills | day one |
| declared files | code-bucket ramp before first edit | shrinks vs no-index sessions | after one cycle |
| verified done | done tasks failing their own verify on replay | ~0 | after one cycle |
| awaiting-human | wrap coverage on sessions ending in `await` | >= 0.8 | after one cycle |

Escalation rate and the replay check are new ledger metrics. ADR 0001's frontier
metric stays spent and is not re-used.

## Dogfood

**broadcast** is the primary repo: greenfield, grilled (4 ADRs), five independent
packages for parallel fills, and a two-phone chirp test that becomes the first
awaiting-human task. **radiator-revivers-landing-page** is the second arm for the
context metric only, adopted after its current feature branch wraps.

## Build order (one phase per session, on flux itself, the old way)

1. Index core: `add/start/done/list/next`, prime line, leases, compaction.
2. Tiers, `escalate`, `await`/`reopen`, and the three skills rewritten.
3. Adopt on broadcast; seed the two day-one claims.

This displaces loop phase 08 (optional) as the next flux work.

## Considered and rejected

- **Agent type per task.** `routing` was deleted in loop phase 07 at zero use in 44
  sessions; a per-task field is metadata nobody consumes.
- **Subagent execution for tracers.** Breaks the execute-report-qualify loop, which
  works because the model that wrote the change re-reads it in the same context.
- **Upfront token estimates per task.** Guesses. The guard nudge and the ledger's
  context p50 are the feedback loop; sizing adjusts at the next plan.
- **A launcher for cross-session autonomy.** A human-launched session is one batch.
  Anything more is the orchestration the v1 pivot retired.
