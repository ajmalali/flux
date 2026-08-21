---
name: wrap
description: Close a phase — verify with `flux check`, reconcile the plan against what actually shipped, write state, generate a handoff, commit. The single exit ceremony; the next session starts from what this writes. Use at the end of every working session.
disable-model-invocation: true
---

# flux wrap

One ceremony, in order. Everything the next session knows, it knows because this ran.
A session that ends without it has lost what it learned.

## 1. Verify

```
flux check
```

Green closes the phase. Red does not: either fix it now, or write the failure into
`open` and `position` in specifics (command, what fails, what you think it is) and say
plainly that the phase is **not** closed. Never close on a scoped run — `flux run`
output is not a gate result, no matter how green.

## 2. Reconcile plan against reality

Read the plan. Read `git diff` / `git status` — what is actually in the tree, not what
you remember doing. Then walk it:

- Each AC: met, partially met, or not met. Partially met is not met.
- Each task: done as specified, done differently, or not done.
- Everything that landed and wasn't in the plan.

Append to the plan file and set `status: done` (or `status: partial`) in its
frontmatter:

```markdown
## outcome — <date>
shipped: <what is now true>
deviated: <what differed from the plan, and why — one line each>
deferred: <what was dropped, and what would have to happen to pick it up>
```

Deviations are the point of this step. A wrap that records none, on a phase that had
some, makes every later plan slightly wrong.

## 3. Write state

```
flux state set phase "<where things are>" position "<what is true right now>" \
  next "<the first thing the next session should do>" routing "<design|mechanical>" \
  open "<live blockers / unverified claims — or empty>"
```

Three rules, and they're where wrap usually goes wrong:

- `position` describes **reality**, including what's half-done or unverified.
- `next` must be executable by someone with no memory of today. "Continue the
  refactor" is not; "`/flux:plan` phase 03 — migrate kiosk state into `.flux/`" is.
- `open` carries what's still unproven — a device untested, a claim unverified. It
  reappears at every session start until someone kills it. That's its job.

State is budget-capped; a refused write means the prose belongs in the plan doc, not
in state.

## 4. Update the effort's status doc

If the effort has `.flux/plans/<effort>/status.md`: current state, tick the queue,
add what a fresh session must not re-derive. Delete what's now stale — a status file
that only grows stops being read.

## 5. Handoff

```
flux handoff
```

Generated and capped. Don't hand-write one alongside it; `flux prime` surfaces the
latest automatically next session.

## 6. Commit

Commit everything, docs included — never leave the repo dirty across sessions; an
uncommitted tree is state the next session can't trust. Branch first if the repo's
convention says so. Open a PR only if asked.

## 7. Read back what you wrote

`flux prime` renders exactly what you just stored. Read it as a stranger would: does
it say where the work is, what's unproven, and what to do first — without this
session's memory? If not, fix it now. Prime is only as true as this step made it.

## Anti-patterns

Closing on a subset run · aspirational `next` describing intent instead of the next
action · `position` that reports the plan rather than the tree · dropping `open`
items because they're inconvenient · leaving the wrap for "next time".
