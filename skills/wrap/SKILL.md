---
name: wrap
description: Close the session — `flux check`, re-run every task marked done today against its own `verify` and reopen what fails, write the tracer's outcome into its spec, write state, generate a handoff, commit, read back `flux prime`. The single exit ceremony; the next session starts from what this writes. Use at the end of every working session.
disable-model-invocation: true
---

# flux wrap

One ceremony, in order. Everything the next session knows, it knows because this ran.
A session that ends without it has lost what it learned.

## 1. Verify

```
flux check
```

Green closes the work. Red does not: either fix it now, or write the failure into
`open` and `position` in specifics (command, what fails, what you think it is) and say
plainly that nothing is closed. Never close on a scoped run — `flux run` output is not
a gate result, no matter how green.

## 2. Re-verify every done

`flux task list --done` — for each task marked done *this session*, run its `verify`
fresh, full output, exit code. The `--by` evidence was the executor's claim; this is
the check. A done that fails its own verify:

```
flux task reopen <id> --why "<what failed>"
```

An awaiting task is not re-verified — the person's word stands, and it is not done
until they give it. Never resolve one here.

## 3. Reconcile the spec against reality

Read `git diff` / `git status` — what is actually in the tree, not what you remember.
For a tracer, walk its `--ref` spec: each AC met, partially met or not met (partially
is not met); the task done as specified, differently, or not; everything that landed
and wasn't in it. Append to the spec file and set `status: done` (or `partial`):

```markdown
## outcome — <date>
shipped: <what is now true>
deviated: <what differed from the spec, and why — one line each>
deferred: <what was dropped, and what would have to happen to pick it up>
```

Fills have no spec file; the index is their record. Escalated fills are not yours to
reconcile — their `why` is what the next tracer session reads first.

Deviations are the point of this step. A wrap that records none, on work that had
some, makes every later plan slightly wrong.

## 4. Write state

```
flux state set position "<what is true right now>" \
  open "<live blockers / unverified claims — or empty>"
```

`phase` and `next` are derived from the index and printed by prime; set `next` only to
override what `flux task next` would say. Two rules, and they're where wrap goes wrong:

- `position` describes **reality**, including what's half-done or unverified — but
  never what prime derives live. Branch, dirty-file count, ahead/behind and the task
  counts are in the pack already; writing them into prose makes it wrong at the next
  commit.
- `open` carries what's still unproven — a device untested, a claim unverified, a
  deployment-gap check not yet run. It reappears at every session start until someone
  kills it. That's its job.

State is budget-capped; a refused write means the prose belongs in the spec, not in
state.

## 5. Update the effort's status doc

If the effort has `.flux/plans/<effort>/status.md`: current state, tick the queue, add
what a fresh session must not re-derive. Delete what's now stale — a status file that
only grows stops being read.

## 6. Handoff

```
flux handoff
```

Generated and capped; an awaiting task's steps ride it whole. Don't hand-write one
alongside it — `flux prime` surfaces the latest automatically next session.

## 7. Commit

Commit everything, docs and `.flux/tasks.jsonl` included — never leave the repo dirty
across sessions; an uncommitted tree is state the next session can't trust. Branch
first if the repo's convention says so. Open a PR only if asked.

## 8. Read back what you wrote

`flux prime` renders exactly what you just stored. Read it as a stranger would: does
it say which task is next, what a person is being asked to observe, what's unproven —
without this session's memory? If not, fix it now. Prime is only as true as this step
made it.

## Anti-patterns

Closing on a subset run · marking a fill done on the subagent's word · resolving an
awaiting task yourself · `position` that repeats the pack · dropping `open` items
because they're inconvenient · leaving the wrap for "next time".
