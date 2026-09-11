---
phase: task-index-04-adopt-broadcast
status: planned
files: [~/Dev/broadcast/.flux/tasks.jsonl, ~/Dev/broadcast/.flux/state.jsonl, ~/Dev/broadcast/.flux/plans/]
---

## objective
broadcast executes off a task index instead of a phase file: its stalled phase-01 remainder
and its next slice are decomposed into `.flux/tasks.jsonl` there, the two-phone chirp test
is an `await` task carrying its procedure, and a cold session in that repo opens on the
index rather than on a 2026-08-27 state block. This is ADR 0004 build step 3's dogfood —
the first index flux does not own.

Contract source: `.flux/adr/0004-task-index-execution.md` §Dogfood. **This session runs in
`~/Dev/broadcast`, not in flux**, and edits no flux file.

## what is true there today (verified 2026-09-11)
- `.flux/` present (flux.toml, state.jsonl, field-log.md, cache, plans); no `tasks.jsonl`.
- `state.jsonl` last written 2026-08-27 and still carries `routing = design`, a key deleted
  in loop phase 07 — evidence the repo has not run a current flux.
- `phase = 01-sync-skeleton`; gate green (33 tests); AC-1/AC-2/AC-4 pass on an iPhone 13
  Pro Max (max drift 3.33 ms); **AC-3 — the two-phone chirp offset ≤ 40 ms — is the only
  thing outstanding**, procedure in `.flux/plans/01-sync-skeleton.status.md`.
- `open` still records: RN-vs-Flutter undecided, gate command empty until a stack exists,
  iOS background-audio vs Android foreground-service unresolved, WebRTC bridge cost unknown.
- One commit; `packages/protocol`, `docs/adr`, `CONTEXT.md` untracked.

## settled shapes

**The chirp test is the first task and it is `await`, not a tracer.** Its verify is a human
observation (two phones, `?test=chirp`, record WAV, `measure-sync analyze`), so it is added,
then put in `await` with the steps from `01-sync-skeleton.status.md` clipped to the record
cap — the steps in the task, the long procedure left in the status file and pointed at by
`--ref`. Nothing else blocks on a person.

**Decompose the slice that is already grilled, not the whole product.** broadcast's ADRs in
`docs/adr` and phase 01's plan are the source; anything resting on the undecided RN-vs-Flutter
question is *not* decomposed this session — an index full of tasks nobody can start is the
failure mode this dogfood is meant to expose, not demonstrate.

**Fills need their tracer's files to be real.** `packages/protocol` exists; other packages
the ADR counts on for parallel fills may not. A fill whose declared files do not exist yet
belongs behind the tracer that creates them, via the implicit tracer edge — do not invent
`--blocked-by` chains to compensate.

**The repo's state keys are rewritten once**, by `flux state set` (not by hand), so `routing`
disappears and `next` stops naming a phase file. `phase` leaves the pack on its own once the
index has open tasks (ADR 0004 point 7) — do not fight it.

## task
files: ~/Dev/broadcast/.flux/tasks.jsonl, ~/Dev/broadcast/.flux/state.jsonl
do: in `~/Dev/broadcast`, run `flux task add` for the chirp verification (then `flux task
  await` with its steps), for the phase-01 remainder the chirp unblocks, and for the next
  grilled slice — tracers with `--files`/`--verify`/`--ref`, fills with `--tier fill
  --tracer <id>`; then `flux state set` so position/next/open describe the index.
verify: `flux task next` returns the chirp task as awaiting with its steps; `flux prime`
  prints the `await:` line and no `routing` line
done: AC-1..AC-4

## acceptance criteria
AC-1 — Given a cold session in `~/Dev/broadcast`, when `flux task next` runs, then it
returns the chirp task, marked awaiting, with the observation steps.
AC-2 — Given `flux task list --all`, then every task shows a `--verify` and every non-verification
task shows declared files, and at least one fill names its tracer.
AC-3 — Given `flux prime` in that repo, then the pack carries the `await:` line, carries no
`routing` line, and its `position`/`next` describe the index rather than 2026-08-27.
AC-4 — Given the index, then no task's declared files depend on the RN-vs-Flutter decision.

## precondition (not expressible as an edge)
This task is `--blocked-by t-g5ub` (claims seeded) only, but it should also run **after
`t-v2b7`, the 2.14.0 deployment-gap check**: broadcast executes the *installed* plugin copy,
and its task log must be compacted by a CLI that preserves reopen evidence (`t-6if4`), or the
replay-check claim ADR 0004 seeds one cycle out has no denominator there. Edges are declared
at `add` time and not edited, so this is recorded here instead. `flux task next` orders
`t-v2b7` first anyway (earlier add ts); do not start this one out of order.

## boundaries
do not change: any file under `~/Dev/flux` — this session's whole output lives in broadcast.
do not change: broadcast's product code, `docs/adr`, or `CONTEXT.md`. The tempting move is to
"just fix" the untracked working tree while there; it is a different session's job.
do not decide: RN-vs-Flutter, the iOS/Android background-audio constraint, or the gate
command — all are grill material, and deciding them inside a decomposition is how a plan
session turns into an unreviewed architecture session.
out of scope: running the chirp test itself (it is the human's, and it is the point of the
`await` shape); seeding claims (done in the flux repo before this session).

## verification
`flux task next` + `flux prime` as above, plus: the flux repo's working tree is clean
afterwards (`git -C ~/Dev/flux status --short` empty of changes this session made), and
`flux ledger --verdict` in flux shows the two day-one claims now counting broadcast
sessions as eligible.
