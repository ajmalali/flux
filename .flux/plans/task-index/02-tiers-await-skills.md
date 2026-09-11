---
phase: task-index-02-tiers-await-skills
status: done
files: [bin/flux, tests/test_task.py, skills/plan/SKILL.md, skills/apply/SKILL.md, skills/wrap/SKILL.md, README.md, .claude-plugin/plugin.json]
---

## objective
A task carries a tier (`tracer`/`fill`) that `escalate` can raise, a task can wait on a
person (`await`/`reopen`) with its steps surfaced by `next`, prime and the handoff, and the
three lifecycle skills plan/apply/wrap read and write the index instead of a phase file —
ADR 0004 build step 2, leaving adoption and claim seeding (step 3) untouched.

Contract source: `.flux/adr/0004-task-index-execution.md` points 1–4 and 9; glossary
`CONTEXT.md`. Everything the ADR left open is **settled here**, not re-argued in apply.
Phase 1's settled shapes (`01-index-core.md`) still bind; this file only adds to them.

## settled shapes

**Tier** — an `add` field, `"tier": "tracer"|"fill"`, set by `--tier`; **absent means
`tracer`** on replay and on `add`. The safe default is the one that keeps the work in the
parent: a fill dispatched to a subagent by mistake is the expensive error, a tracer run by
the parent by mistake is merely slow. A fill may name the slice it widens with
`--tracer <id>` (stored `"tracer": "t-x"`); the named id must exist and be tier `tracer`
(else exit 1). It is **optional** — the ADR's "fills implicitly block on their tracer" is
honoured when one is named: `task_blockers` treats `tracer` as one more `blocked_by` edge
(unknown id → `?t-x`, blocks forever). `--tracer` on a tracer → usage 2. Tier is never
lowered: no `--tier` on any verb but `add`, and `escalate` only goes fill → tracer.

**Ops** — three new records, appended like the rest, each capped at
`TASK_RECORD_MAX_BYTES` with the same refusal (checked before append, writes nothing):

```
{"ts":"…","id":"t-x","op":"escalate","why":"NEEDS_CONTEXT: which config file wins"}
{"ts":"…","id":"t-x","op":"await","steps":"open the app on both phones, tap chirp, hear it on the other"}
{"ts":"…","id":"t-x","op":"reopen","why":"chirp heard on one phone only"}
```

- `escalate <id> [--why "…"]`: refused on a `done` or `awaiting` task, and on a task
  already tier `tracer` (exit 1 each, message names the reason). Sets tier `tracer`,
  status **`open`**, clears this worktree's lease (a batch moves on; nobody holds it).
  Allowed from `open` (the executor raises the tier at pickup) and `active` (a subagent
  handed it back). The `why` is what the subagent said — `NEEDS_CONTEXT: …`/`BLOCKED: …`.
- `await <id> --steps "…"`: `--steps` required (usage 2 without). Allowed from `open`
  (a verification-only task never starts, ADR §4) and `active`; refused on `done` or
  already `awaiting` (exit 1). Clears the lease. Status becomes `awaiting`.
- `reopen <id> [--why "…"]`: allowed from `awaiting` (the observation failed) and from
  `done` (phase 1 refused `start` on done precisely because this verb was coming);
  refused from `open`/`active` (exit 1: "not closed"). Status `open`, tier unchanged,
  `starts` segment reset (as a start-after-done does today), `by`/`steps` cleared.
- `start` on `awaiting` → exit 1 (`awaiting a person — done --by or reopen`). `done`
  from `awaiting` is the happy resolution and needs no lease.
- Replay: unknown ops stay ignored; these three set status/tier as above. `_closed` is
  true after `done`, false after `reopen`.

**Order** — `_task_candidates` returns awaiting tasks **first** (rank −1, regardless of
leases — await clears them and no session holds one), then the phase 1 ranks. Awaiting
tasks are not done, so their dependents stay blocked. `next --all` lists them first too.

**Compaction** — every terminal op folds into the add record **with its own stamp and
replays as a synthetic op**, the phase 1 rule generalised: `"status":"awaiting"`,
`"steps"`, `"await_ts"`; a reopened-and-still-open task carries `"reopen_ts"` (+`"why"`)
so a merged earlier `done` cannot resurrect it; an escalated task carries `"tier":"tracer"`,
`"escalated":"<why>"`, `"escalate_ts"` (folded tier is the *current* tier; the original
fill-ness survives as the presence of `escalated`). `tier` and `tracer` fold as plain add
fields. `escalate` on an awaiting-then-reopened task is a normal escalate. Idempotence and
byte-identity across clones hold as before.

**Output grammar** (phase 1 rows unchanged when none of this is in play — the phase 1
tests must pass untouched):
- `list`: status prints `awaiting`; suffixes ` [fill]` (tier fill only — tracer is the
  unmarked default), ` [fill of t-x]` when a tracer is named, ` [escalated]`,
  ` (awaiting: <steps clipped to 80 bytes>)`. New filter `--awaiting`. Count line gains
  `, A awaiting` **only when A > 0** and `, E escalated` **only when E > 0**, appended
  after `K done`. `task_counts` returns five numbers; `open` still counts awaiting.
- `next`: ` · tier: fill`, ` · tracer: t-x` for fills; an awaiting task prints
  ` · awaiting: <steps whole>` and no files/verify (the person, not the session, acts).
- `escalate`/`await`/`reopen` print `flux task: <verb> <id>  <title>` on stdout.

**Prime** — `TASK_AWAIT_BUDGET = 300`. When the head candidate is awaiting, the `task:`
line is followed by `await: <id> <steps>` clipped to that budget with `marker="…"`, and
the derived `next:` reads `next: <id> <title>  [awaiting a person — flux task done <id>
--by "…" | reopen <id>]`. With no awaiting task the pack is **byte-identical** to 2.12.0.

**Handoff** — a `## awaiting` section (`- <id> <title>` then `  steps: <whole>` per task)
between `## state` and `## working tree`, only when ≥1 task is awaiting; otherwise the
file is byte-identical to today's. "Whole" is bounded by the record cap; the handoff's own
clip still applies last.

**Skills** (ADR §9, roster unchanged, all under `SKILL_BUDGET_BYTES = 6000` — apply is at
5853 today and must *shed* the phase-plan-only prose to make room):
- `plan`: keeps the plan-or-not gate and sizing. Then **decomposes into the index**:
  one `flux task add` per task — tracers with `--ref` at a spec file
  `.flux/plans/<effort>/<slug>.md` holding the phase 1 template (objective, AC, one
  task's four lines, boundaries, verification); fills as `--tier fill --tracer <id>`
  with the one-line intent as the title, `--files`, `--verify`, and `--blocked-by` for
  edges beyond the tracer. Verification-only tasks (no files) are allowed. Closes with
  `flux task next` read back; `flux state set next` only as an override.
- `apply`: starts from `flux task next`. **Awaiting head** → print the steps, ask the
  person, resolve with `done --by "<what was observed>"` or `reopen --why`, and stop.
  **Tracer** → `start`, read its `--ref` spec once, execute → report → qualify (kept
  verbatim), `done --by "<evidence>"`; one tracer per session. **Fills** → `next --all`,
  `start` each, dispatch to a subagent (built-in `general-purpose`, parent's model) with
  a spec composed at pickup: title, files, verify, the tracer's ref. Sequential by
  default; parallel only on disjoint declared files. The parent edits nothing.
  `NEEDS_CONTEXT`/`BLOCKED` → `escalate --why`, move on, never retry. After the batch:
  `flux check` once; red → re-run each fill's `verify`, escalate the failing one, green
  fills stay and get `done --by`. A verify that is a human observation → `await --steps`
  and the session ends there. One tracer *or* one batch, never both.
- `wrap`: `flux check`; for every task marked done this session re-run its `verify`
  fresh (a done that fails its own verify is reopened with `--why`); the `## outcome`
  block goes into the tracer's spec file when there is one; `flux state set position …
  open …` (phase and next are derived — set `next` only to override); status doc;
  `flux handoff`; commit; read back `flux prime`.

## acceptance criteria
AC-1 — Given `add "F" --tier fill --tracer <T>` with T open, when `next` runs, then F is
blocked by T; after `done T --by x`, `next` returns F with ` · tier: fill · tracer: <T>`;
`escalate F --why "NEEDS_CONTEXT: …"` then leaves F `open`, unmarked `[fill]`, marked
`[escalated]`, and a second `escalate F` exits 1.
AC-2 — Given task A active with a lease, when `await A --steps "look at the phone"` runs,
then the lease file is gone, `next` prints A first with ` · awaiting: look at the phone`
even when an open runnable B exists, `start A` exits 1, and `done A --by "seen"` closes it;
given `reopen A` instead, A is `open` and `next` returns A by add order.
AC-3 — Given a log with one awaiting, one escalated, one reopened-open and one done task,
when `flux task compact` runs twice, then `list --all` is unchanged before/after and the
second run is byte-identical; a `done` record appended with a ts *earlier* than the folded
`reopen_ts` still replays to `open`.
AC-4 — Given an awaiting task, when `flux prime` runs, then the pack has an `await:` line
≤300 bytes (with a 500-byte `--steps`) and the derived `next:` names done/reopen; given the
same index with no awaiting task, the pack is byte-identical to the pack captured before
this phase; `flux handoff` carries the steps whole under `## awaiting`, and with no
awaiting task the handoff is byte-identical to today's for the same state.
AC-5 — Given the rewritten skills, when `flux check` runs, then `TestLifecycleSkills` is
green (frontmatter, `disable-model-invocation: true`, each file < 6000 bytes), and each of
plan/apply/wrap names every verb it is expected to issue (`grep -c` for `flux task add`,
`flux task next`, `escalate`, `await`, `reopen`, `done --by` per the table in T3).

## tasks
### T1 — Add tier, `--tracer`, and `escalate`
files: bin/flux (task section: `_TASK_USAGE`, `_TASK_ADD_FLAGS` + `--tier`/`--tracer`, `_new_task`, `replay_tasks`, `task_blockers`, `task_counts`, `compact_tasks`, `_task_ops`, `_task_row`, `_task_next_line`, new `_task_escalate`, `cmd_task` dispatch; docstring usage lines), tests/test_task.py (new `TestTaskTiers`)
do: per the settled shapes for tier and `escalate`. `add` validates `--tier` ∈ {tracer, fill} (usage 2 otherwise), `--tracer` only with `--tier fill`, and that the named tracer exists and is a tracer (exit 1). Replay defaults tier to `tracer` for records without the field (every 2.12.0 record). `task_blockers` folds `tracer` into the edge list. `escalate` appends the op, clears the own lease, prints the stdout line. `list` suffixes and count-line `, E escalated` (only when E > 0); `next` line suffixes. Compaction folds `tier`, `tracer`, `escalated`, `escalate_ts`; `_task_ops` expands `escalate_ts` into a synthetic `escalate` op.
verify: `python3 -m unittest tests.test_task -v` — tests: tier defaults to tracer on a 2.12.0-shaped record; `--tier bogus` usage 2; `--tracer` on a tracer usage 2; `--tracer` naming a fill or unknown id exit 1; AC-1 sequence; escalate on done/tracer/awaiting exits 1; escalate clears the lease file; compaction of an escalated task is idempotent and replays to tier tracer + `[escalated]`; every phase 1 test unchanged and green. Then `flux check`.
done: AC-1 when those tests pass and the full suite stays green (306 + new).

### T2 — Add `await`/`reopen`, awaiting-first order, prime and handoff surfacing
files: bin/flux (`_task_await`, `_task_reopen`, `_task_start` refusal, `_task_candidates` rank −1, `_task_list` `--awaiting`, `compact_tasks`/`_task_ops` folds, `TASK_AWAIT_BUDGET`, `_task_pack_lines` returning a third `await` line, `_prime_inner` emitting it after the task line inside the phase slot, `cmd_handoff` `## awaiting` section via a small `_task_awaiting(root)` helper that returns `[]` fast when `tasks.jsonl` is absent), tests/test_task.py (new `TestTaskAwait`, additions to `TestTaskPrime`, a handoff test)
do: per the settled shapes for `await`, `reopen`, order, compaction, prime and handoff. `_task_pack_lines` grows to `(task_line, next_line, await_line)`; the prime loop appends `await_line` right after `task_line` when non-empty. `cmd_handoff` inserts the section only when the helper returns tasks — the no-awaiting path must not touch a byte. `reopen` from `done` resets `starts`, `by`, `done_ts`; from `awaiting` resets `steps`. Count line `, A awaiting` only when A > 0.
verify: tests: AC-2 sequence incl. lease-file absence after await; AC-3 compaction incl. the earlier-ts `done` vs folded `reopen_ts` case (write the record directly, as a merge would); `await` without `--steps` usage 2; a 1.1 KB `--steps` refused naming `TASK_RECORD_MAX_BYTES` and writing nothing; `reopen` on open exits 1; `next --all` lists awaiting before runnable; AC-4 prime: capture the pack with one open task before adding any awaiting task, add+await a second task, assert `await:` present and ≤300 bytes with a 500-byte steps string, then `done` it and assert the pack (from line 2 — the dirty count changes while `tasks.jsonl` is edited; or commit the index first as phase 1 did) equals the capture; handoff: `## awaiting` with the whole steps string, and byte-equality (from the `branch:` line — the header carries a timestamp) with a no-awaiting handoff for the same state. Then `flux check`.
done: AC-2, AC-3, AC-4 when those tests pass and `flux check` is green.

### T3 — Rewrite plan/apply/wrap in place; docs and version
files: skills/plan/SKILL.md, skills/apply/SKILL.md, skills/wrap/SKILL.md, README.md (§A typical day unchanged; §Bigger work rewritten to the task flow: plan decomposes into the index, apply takes the next task or a batch, wrap verifies and closes; §Skills three rows; §Commands: one row for `escalate`/`await`/`reopen`, and the `flux task next` row mentions awaiting-first), .claude-plugin/plugin.json (2.12.0 → 2.13.0), bin/flux docstring `Commands:` line
do: per the settled Skills shape, each file rewritten whole, frontmatter `name`/`disable-model-invocation: true` kept, `description` updated to the new behaviour. Keep apply's status table and the qualify checklist verbatim — they are the part that works; cut the phase-plan-only prose (approval paragraph, "Delegate the reading", "diagnose before patching" trimmed to three lines) to stay under 6000 bytes. Verb table each skill must name, checked by grep in AC-5: plan → `flux task add`, `--tier fill`, `--tracer`, `--ref`, `flux task next`; apply → `flux task next`, `--all`, `start`, `done --by`, `escalate`, `await`, `reopen`, `flux check`; wrap → `flux check`, `verify`, `reopen`, `flux state set`, `flux handoff`, `flux prime`. Skills contain judgment only: which tasks, batch or not, parallel or not — no procedure the CLI already owns is restated.
verify: `flux check` green (`TestLifecycleSkills` covers existence, frontmatter, invocability, budget); `wc -c skills/*/SKILL.md` all < 6000; the AC-5 grep table all ≥1; `bin/flux --help` eyeballed once (TestHelp cannot catch a docstring error); `git diff README.md` shows only the four sections named in `files`.
done: AC-5 when the greps and the suite pass and README/plugin.json are committed with the code.

## boundaries
do not change: the phase 1 output grammar for tasks that carry none of the new fields — every phase 1 test stays green untouched (byte-identity is the AC, not a nicety). `state.jsonl` code, `_seal_inner`, lease semantics (only `escalate`/`await` gain a `_lease_clear` call). `skills/audit`, `skills/adopt`, `skills/grill` — roster unchanged (ADR §9); audit still targets a spec file, which a tracer's `--ref` still is. `_CLAIM_METRICS` and the ledger — the escalation-rate and replay-check metrics are phase 3's (they land with the `flux claim add` that needs them; until then `E escalated` on the count line is the number, visible by hand).
out of scope: a `[task] fill_model` knob (ADR §8, gated on escalation rate); editing `blocked_by`/`tracer` after `add` (declare at add; reopen + re-add if wrong); a `--tier tracer` lowering path (never); parallel dispatch machinery in the CLI (the skill decides; the CLI holds no scheduler, ADR §2); the escalation-rate ledger metric and any claim seeding (phase 3); adopting broadcast (phase 3); `flux run` deletion (on notice, separate decision); the 2.13.0 deployment-gap check beyond noting it in `open` at wrap.

## verification
`flux check` green (expect 306 + ~30 new), plus what tests cannot see:
- In this repo, by hand: `flux task add "probe" --tier fill --tracer <bad>` exits 1;
  an `await` on a scratch task makes `bin/flux prime` show the `await:` line, `done`
  removes it, and the index is then deleted before commit (this repo is not adopted
  on the index yet — phase 3 is).
- `bin/flux prime` in this repo at HEAD vs with the change applied, compared from line 2:
  empty (no index here).
- Read each rewritten skill once as a cold session would: can apply run a batch from
  the text alone without re-deriving the ADR? If it has to open the ADR, the skill is
  incomplete.
- After push: `claude plugin update flux@marketplace` shows 2.13.0 and `flux task
  escalate` from a fresh shell in another adopted repo says `no such task`, exit 1,
  not traceback (the 2026-09-08 deployment-gap check, carried in `open` until done).

## outcome — 2026-09-11
shipped: tier (`--tier tracer|fill`, absent = tracer) and `--tracer <id>` on `add`,
validated (usage 2 / exit 1 as specified); a fill's tracer is one more blocking edge.
`flux task escalate|await|reopen` with every refusal in the settled shapes, record-
capped, lease-clearing. Awaiting tasks rank first in `next`/`next --all`; `list`
gains `--awaiting`, the `[fill]`/`[fill of t-x]`/`[escalated]`/`(awaiting: …)`
suffixes and the conditional `, A awaiting`/`, E escalated` count tail; `next` gains
`· tier: fill · tracer: t-x` and the awaiting form. Compaction folds all three ops
and replays them as synthetic ops at their own stamps (idempotent, byte-identical).
Prime: `await:` line under `task:` capped at `TASK_AWAIT_BUDGET`=300, derived `next:`
names done/reopen; no awaiting → byte-identical pack (line-2 diff in this repo:
empty). Handoff: `## awaiting` between `## state` and `## working tree`, steps whole,
absent otherwise. plan/apply/wrap rewritten whole around the index (4165/5928/4315
bytes); README §Bigger work/§Skills/§Commands; plugin.json 2.13.0. 327 green
(306 + 21). AC-1..5 met; the plan was applied without an audit pass (`status:
planned` at apply time — flagged, accepted by invocation).
deviated:
- `escalate`/`await` refuse on a live *foreign* lease (exit 1, mirrors `done`) — the
  plan only said they clear the lease; clearing another session's hold silently would
  be the worse behaviour.
- `escalate` resets the start segment (`starts`/`where`) so a tracer session picking
  the task up elsewhere does not render a false `[2 starts]` conflict.
- `E escalated` counts every escalated task, done included, and `[escalated]` stays
  on done rows — the escalation-rate numerator stays readable by hand until phase 3.
- Explicit `--tier tracer` writes no `tier` field (absent = tracer keeps the record
  2.12.0-shaped).
- A blocked awaiting task is not a candidate (plan silent); it surfaces once its
  blockers close.
- AC-4 prime test asserts byte-identity after `reopen`, not after `done` — the plan's
  verify text could not hold (a `done` changes the count line).
- Shared `_task_id_and_flag`/`_task_load`/`_task_held_elsewhere`/`_task_record_fits`
  helpers; `add`'s refusal message unchanged.
- apply's "Delegate the reading" section dropped, "diagnose before patching" cut to
  three lines, per T3; wrap's `flux state set` drops `phase`/`next` (derived).
deferred: the 2.13.0 deployment-gap check (push + plugin update + `flux task escalate
t-x` from a fresh shell in an adopted repo) — in `open`. Phase 3 (adopt on broadcast,
seed the two day-one claims, escalation-rate + replay-check ledger metrics) untouched
by design. This repo is still not adopted on the index (phase 3 decides).
