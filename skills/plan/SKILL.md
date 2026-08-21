---
name: plan
description: Write a self-contained phase plan into .flux/plans/ — objective, acceptance criteria, 2-3 tasks, boundaries, verification, routing stamp. Use when starting a new phase of work.
disable-model-invocation: true
---

# flux plan

Produce ONE file a cold session can execute without re-deriving anything. It is the
contract `/flux:apply` executes and `/flux:wrap` reconciles against. Everything the
plan doesn't say, the executing session will have to guess.

## Read first, narrowly

The primed pack is already in context — `phase`, `position`, `next`, `open`. Add only:

- the effort's `plan.md` / `status.md` under `.flux/plans/`, if one exists;
- source files whose *current shape* the plan's correctness depends on.

Send wider reading to `flux-explorer`; take its pointers, not its files. Do not chain
prior summaries "for context" — unread context still costs the same as read context.

## Size the work before writing it

- **Small** — one sentence, 1–2 files, no new pattern or dependency. One task, one AC,
  no boundaries section. Still gets a plan; still gets wrapped.
- **Standard** — 2–3 tasks. This is the target: work that fits before quality decays.
- **Too big** — 4+ tasks, or spans parts that can fail independently. Split it into
  sequential phase plans and write only the first. Do not write the giant plan and
  hope apply survives it.

State the size you picked in one line, with the reason. Then write.

## Where it goes

`.flux/plans/<NN-slug>.md` — or `.flux/plans/<effort>/<NN-slug>.md` when that effort
already has a directory.

## The file

```markdown
---
phase: NN-slug
routing: design | mechanical
status: planned
files: [paths this phase expects to touch]
---

## objective
One sentence: what is true when this is done that is not true now.

## acceptance criteria
AC-1 — Given <precondition>, when <action>, then <outcome someone else could observe>.

## tasks
### T1 — <verb-first name>
files: <paths>
do: <the specific change — not "improve X", not "handle errors">
verify: <the command or observation that proves it, run fresh>
done: AC-1 when <condition>

## boundaries
do not change: <what this phase must leave alone, and why it's tempting>
out of scope: <the adjacent thing you'll want to fix mid-apply>

## verification
`flux check` green, plus: <what check cannot see — a screen, a device, a log line>
```

Write acceptance criteria someone else could falsify. "Works correctly" is not an AC.
Every task needs all four lines; a task whose `verify` is "read the code" is a task
you have not finished specifying.

`routing` is read at session start: **design** when the shape is still open
(architecture, a new surface, unclear tradeoffs); **mechanical** when the shape is
settled and only execution remains.

## Check coherence before you finish

Against the effort's plan, `CLAUDE.md`, and what `open` already records: does this
plan contradict a stated constraint, a decision already made, or the phase's own
scope? Does it rewrite a file that was just rewritten? Surface what you find, in
specifics, and wait. Find nothing and say nothing — silence is the pass.

## Close

```
flux state set phase "<NN-slug>" next "/flux:apply <path>" routing "<design|mechanical>"
```

Then one line: the path, the size, and whether the phase is risky enough to warrant
`/flux:audit` first. No menus.
