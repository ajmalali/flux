# Design: reviving the execution index (ADR 0001), on declared-files and routing

Date: 2026-08-26
Status: **DRAFT — design only, nothing built.** A proposal to revive
`.flux/adr/0001-execution-frontier.md` (Accepted, then suspended 2026-08-22). It does
not un-suspend that ADR; it specifies what a revival would be so the first real-work
feature can be run *against* it. Building is gated behind the real-work pre-registration
(`.flux/analysis/2026-08-25-realwork-preregistration.md`) — see "The validation gate".
Line: v2. Builds on ADR 0002 (append-only state), reuses its mechanism verbatim.

## Why this exists

The big-feature path in `plan.md` still has no spine: a discussion produces many
phases, `/flux:plan` writes only the first, and the decomposition of everything after it
dies with the planning session's context. Every cold session re-derives the frontier by
reading. ADR 0001 designed the fix — a local execution index the CLI orders — then
suspended it when the cold-start-ramp measurement showed the frontier is only ~5.7% of
ramp context and `flux prime` already removes most of that.

This revival is what remains **after** that measurement, and it must obey the ruling the
measurement made.

## The one binding constraint from ADR 0001

> This measurement bounds what an index could save by *removing frontier reads*. It
> cannot see the second mechanism: the index stores **declared files per task**, so a
> session that starts knowing which four files its task touches might read four instead
> of fifteen — an effect on the 60% [source-reading] bucket no transcript can reveal…
> **If this ADR is revived, it must be revived on that mechanism, with code-bucket ramp
> as its ledger metric. The frontier justification is spent and may not be re-used.**

So this design is **forbidden from claiming** it saves context by avoiding frontier
re-derivation. It rests on two live mechanisms instead:

1. **Declared files per task** — a session reads the task's files, not the whole area.
   Attacks the 60%-of-ramp source-reading bucket, which the ramp study could not see.
2. **Routing per task** — the user's motivation, and a real gap: `to-tickets`/`wayfinder`
   tickets carry no `routing`, and `state.jsonl` carries one project-wide routing at a
   time. A per-task `routing` field lets `flux prime` route the model correctly at each
   session boundary without the model re-deriving design-vs-mechanical.

A third justification survives untouched because it is structural, not context-cost:
**a sentence cannot hold thirty tasks, their edges, and which nine are done.** Prose
loses the DAG; that was true before the ramp study and is unaffected by it.

## The division of labor (this is Principle 1)

Confirmed with the user, 2026-08-26. It is flux's own Principle 1 restated:

- **mattpocock skills = planning.** `grill` (single-session shape) or `wayfinder`
  (cross-session map, which *invokes* grilling — they are not chained) run the
  discussion. `to-spec` optionally synthesizes it into one spec on the tracker.
- **flux = decomposition + execution.** flux takes the spec (or the raw discussion) and
  breaks it into the task DAG — *once* — carrying `routing` and `files` that mattpocock
  has no slot for, then executes it.

**Consequence: `to-tickets` leaves the execution path.** You decompose once, in flux,
not twice. `to-tickets` stays vendored for publishing *human-facing* tickets to a
tracker people plan against; that is a different artifact from the machine execution
index and must not be treated as its source of truth (see Risks: two sources of truth).

*What the tasks are* stays judgment (a skill decomposes). *Which task is next* is a
topological sort — the procedure that belongs in the CLI.

## Storage: reuse ADR 0002 exactly

`.flux/tasks.jsonl` — **one JSON record per task-event, appended, never rewritten** —
the identical shape ADR 0002 proved for state. `flux init` adds `tasks.jsonl merge=union`
to `.flux/.gitattributes`; concurrent branches both keep their appends; `flux task`
resolves current state by **replay** (last op per id wins), so git never decides.

Record shapes (op-log):

```json
{"ts":"2026-08-26T09:14:03.221Z","id":"t3","op":"add","title":"reject conflicting confirm","routing":"mechanical","files":["meridian/domain/hold.py","tests/test_hold.py"],"blocks":["t1"],"verify":"flux check","ref":".flux/plans/booking/spec.md#slice-3"}
{"ts":"2026-08-26T10:02:51.008Z","id":"t3","op":"start"}
{"ts":"2026-08-26T11:20:12.664Z","id":"t3","op":"done","by":"flux check green + 3 new tests in test_hold.py"}
```

Rules that ride the format:

1. **`blocked` is computed on read, never stored.** `blocked(id) = any(b not done for b in
   blocks)`. This is beads' second good idea (`bd recompute-blocked` exists because
   stored blocked-flags go stale after a pull), stolen without the dependency —
   ADR 0002 explicitly parked it here.
2. **`flux task next`** = the first task whose status is `open` and whose blockers are
   all `done`, in topological order, stable-tiebroken by add order. Deterministic:
   returns the same task twice.
3. **Compaction like state.** `flux task compact` collapses to one record per live task;
   auto-fires past `8×` the budget. CLAUDE.md forbids uncapped stored state, and an
   append-only file is uncapped by construction unless something caps it. Deterministic
   output (same records in → byte-identical file out) so independent clones agree.
4. **`done` records its evidence.** `op:"done"` carries `by` — what verified it —
   mirroring ADR 0001 rule 3. `/flux:wrap` reconciles `done` claims against the tree.

## CLI surface (scoped to the frontier, nothing more)

```
flux task add   <title> --routing <design|mechanical> [--files a,b] [--blocks id,…] [--verify CMD] [--ref PATH]
flux task start <id>
flux task done  <id> --by "<what verified it>"
flux task block <id> --on <id,…>          # add/replace blocking edges
flux task next                            # → the next unblocked task, deterministic; exit 1 if none
flux task list  [--all|--open|--blocked|--done]
```

The model calls verbs; it **never hand-edits `tasks.jsonl`**, exactly as with
`flux state set`. Any key starting with `-` is refused whole (the 2026-08-22 silent-
corruption guard applies here too).

**`flux prime` integration.** Prime surfaces the **current task and the counts**, never
the graph: e.g. `task: t3 reject-conflicting-confirm [mechanical] · 2 open, 1 blocked,
5 done`. The routing on that line is what routes the model for the session. The graph is
queried on demand by `flux task list`, not injected.

## What flux does NOT do

No automatic decomposition — the CLI stores and orders tasks, a skill invents them.
No tracker sync. No parser for PAUL / agent-os / Linear / beads formats (the per-project
fork `plan.md` forbids). No scheduler, no parallel execution, no auto-advance past a
session boundary. No beads dependency — its one relevant verb (`bd ready`) is the topo
sort above, ~50 lines of stdlib.

## Ledger metrics (falsifiable, per Principle 5)

The frontier metric from ADR 0001 is **retired** — spent by measurement, may not be
re-used. New metrics:

| capability | metric it must move | falsifier / delete condition |
|---|---|---|
| declared-files per task | **code-bucket ramp** — source-file reads (calls + tokens) before a session's first `Edit`/`Write`, on real multi-feature work | files declared but ramp's code bucket does not shrink vs. a no-index arm ⇒ the declaration was noise; drop `--files` |
| routing per task | routing re-derivation events per session (a session that reads code/plans *to decide* design-vs-mechanical before starting) | drops to ~0 already without the field ⇒ `state.jsonl`'s single routing was enough; drop per-task routing |
| decomposition survival | tasks re-derived by reading per cold session on a >10-task effort | a cold session reconstructs the DAG by reading prose anyway ⇒ the index is not carrying it |
| verified-done | tasks marked `done` that fail their own `verify` on replay | rate already ~0 ⇒ the `by` bookkeeping is theatre |

Two reporting cycles without movement deletes the capability, as with everything else.
**Fresh frontier data is allowed but not assumed:** the real-work dogfood runs at a
multi-feature scale the ramp corpus never had, so it *may* produce a new frontier number
— but this design does not presume one, and would not revive on the old, spent argument.

## The validation gate (do not build yet)

flux's scar tissue: it shipped two agents that sounded obviously right and measured at
**zero** invocations, then deleted them. `flux task` sounds right the same way. So it is
built on data, not on this document:

1. Run the **next real multi-phase feature** (the pre-registration's live project)
   through the thinnest thing that works — the existing flat `status.md` queue, or a
   minimal `tasks.jsonl` with only `add`/`next`/`done` and no compaction.
2. Log to `.flux/field-log.md`:
   - `[pack-miss]` — had to re-derive the phase list / a task's files by reading.
   - `[want]` — wished the CLI handed me the next unblocked task with its routing and
     files.
   - `[audit-hit]` — a declared-file set that was wrong in a way that cost a session.
3. If `[pack-miss]`/`[want]` pile up **and** `./bench/run.py ramp` shows a code-bucket
   worth attacking → build the full surface, on that evidence. This is exactly how
   ADR 0002 earned its way in. If they don't pile up — because `status.md` + `wayfinder`
   already held it — this design is filed unbuilt and the scar is not re-opened.

On validation, this graduates into an amendment to ADR 0001 (or ADR 0003), not before.

## Risks and open questions

- **Two sources of truth.** If `to-tickets` still publishes human tickets to a tracker
  *and* `tasks.jsonl` holds the machine DAG, they drift. Decide up front which is
  canonical (recommend: `tasks.jsonl` is canonical for execution; the tracker is a
  read-only human view, or `to-tickets` is simply not used on flux-executed efforts).
- **Declared-files accuracy is the whole bet.** The code-bucket saving only materializes
  if the decomposition step predicts a task's files well. If it can't, mechanism 1 pays
  nothing. This is the single most important thing the dogfood tests, and it is
  unmeasurable in advance — no session in the corpus ever had declared files.
- **Session-boundary ownership.** flux owns the session opener (`prime`, SessionStart).
  If beads or any peer is present, its `prime`/`hooks` must be disabled so two systems
  don't both fill context. (Kept here only to record the decision; beads is not adopted.)
- **Parallel edits inherit ADR 0002's semantics.** Two branches touching the same task
  both keep records; last-write-wins per op; the loser survives in the log. Good enough
  for status flips; a `block` and a `done` racing on the same task resolve by timestamp,
  which is acceptable but should be noted to whoever reads a surprising `next`.
- **Who assigns ids.** Monotonic `t1,t2,…` is simplest but collides across parallel
  branches. Either scope ids to the decomposition session, or use a short random suffix
  (no `Math.random` in the CLI is fine — this is Python, not a workflow script).
```
