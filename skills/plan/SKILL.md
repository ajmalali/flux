---
name: plan
description: Decompose work into the task index — one `flux task add` per task, tracers with a spec file behind `--ref`, fills as `--tier fill --tracer <id>`. Use for work that spans sessions, cannot be undone, or whose shape is still unsettled; ordinary work goes straight to /flux:apply.
disable-model-invocation: true
---

# flux plan

**First, whether to plan at all.** A plan pays for itself when the work outlives the
session, takes a step that cannot be undone, or is still being argued about. Ordinary
well-specified work does not need one: measured twice on the benchmark, the
plan→audit→apply→wrap path cost ~3x a single primed apply session and delivered
identical results (`.flux/analysis/2026-08-22-ceremony-two-cycles.md`). If none of
the three conditions holds, say so in one line and route to `/flux:apply`.

The output is the index, not a document: tasks a cold session executes one at a time
without re-deriving anything. Everything a task's spec doesn't say, the executing
session — or its subagent — will have to guess.

## Read first, narrowly

The primed pack is already in context — `task`, `position`, `next`, `open`. Add only:

- the ADR or design the work was grilled into, and the effort's `status.md` if any;
- source files whose *current shape* the tasks' correctness depends on.

Send wider reading to the built-in `Explore` agent; take its pointers, not its files.

## Size the work into tiers

- **Tracer** — a thin end-to-end slice that proves the shape: runs in the parent
  session, one per session, and earns a full spec file. If it does not fit a session,
  it is two tracers.
- **Fill** — widens a proven slice from a one-line intent: the title, its files and
  its verify are the whole spec, because a subagent finishes it from those alone. If
  it needs a paragraph, it is a tracer.
- **Verification-only** — no files, one check that covers several tasks; a human
  observation is allowed as the verify (apply turns it into `await`).

State the count you picked — tracers and fills — in one line, with the reason. Then
write.

## Decompose into the index

Tracers first; a fill needs its tracer's id.

```
flux task add "<title>" --files a,b --verify "<cmd>" --ref .flux/plans/<effort>/<slug>.md
flux task add "<one-line intent>" --tier fill --tracer <id> --files a,b --verify "<cmd>"
```

`--blocked-by t-x,t-y` for edges beyond the tracer — declare them now; edges are not
edited later. Add order is `next` order among equals, so add in the order you would
run them. `--ref` points at the tracer's spec file, written before the `add`:

```markdown
---
phase: <slug>
status: planned
files: [paths this tracer expects to touch]
---

## objective
One sentence: what is true when this is done that is not true now.

## acceptance criteria
AC-1 — Given <precondition>, when <action>, then <outcome someone else could observe>.

## task
files: <paths>
do: <the specific change — not "improve X", not "handle errors">
verify: <the command or observation that proves it, run fresh>
done: AC-1 when <condition>

## boundaries
do not change: <what this tracer must leave alone, and why it's tempting>
out of scope: <the adjacent thing — often the fills that widen this>

## verification
`flux check` green, plus: <what check cannot see — a screen, a device, a log line>
```

Write acceptance criteria someone else could falsify. "Works correctly" is not an AC.
A task whose `verify` is "read the code" is a task you have not finished specifying.

## Check coherence before you finish

Against the ADR, `CLAUDE.md`, and what `open` already records: does a task contradict
a stated constraint, a decision already made, or the effort's scope? Does a fill
touch a file its tracer has not yet proven? Surface what you find, in specifics, and
wait. Find nothing and say nothing — silence is the pass.

## Close

```
flux task next
```

Read it back: that line is what the next session opens on. `flux state set next` only
to override it. Then one line: tracers and fills added, the first tracer's ref, and
whether it is risky enough to warrant `/flux:audit` on that spec first. No menus.
