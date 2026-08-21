---
name: apply
description: Execute an approved phase plan task by task — execute, report status honestly, then qualify against the spec before moving on. Iterates with `flux run --filter failures`, concludes with `flux check`. Use after /flux:plan (and /flux:audit, if run).
disable-model-invocation: true
---

# flux apply

Execute the plan. The plan is the spec; your memory of executing it is not evidence.

Start only on explicit approval and a plan path. "Looks good" is approval; silence
isn't. Read the plan once, in full — its boundaries bind you as much as its tasks.

## Per task: execute → report → qualify

### 1. Execute

Do the task's `do`, to the files in its `files`. Respect `boundaries`. When a change
you want to make falls outside them, stop and say so — do not make it "just this
once"; untracked edits are what makes the next plan wrong.

### 2. Report a status, honestly

| Status | When | What follows |
|---|---|---|
| `DONE` | Finished, no doubts | Qualify normally |
| `DONE_WITH_CONCERNS` | Finished, but something feels wrong about the approach, the coverage, or the correctness | Qualify the concern **first**, then the rest |
| `NEEDS_CONTEXT` | Can't finish — information that isn't in the plan or the repo | Stop. Name exactly what's missing. Ask |
| `BLOCKED` | Can't finish — permissions, missing dependency, broken environment | Stop. What you tried, what blocks, what would unblock |

`NEEDS_CONTEXT` is not failure — it's what stops an hour of work built on a wrong
guess. `DONE_WITH_CONCERNS` costs nothing to say and is the only way a real doubt
survives to where it can be checked.

### 3. Qualify

Your report of your own work is optimistic. Check the artifact, not the memory.

1. **Re-read what you actually wrote.** Open the files. Not a diff from memory.
2. **Run `verify` fresh.** Full command, full output, exit code. A remembered pass is
   not a pass.
3. **Compare against both** the task's `do` and its linked AC, line by line.
4. **Score it:** `PASS` — matches. `GAP` — something specified is missing. `DRIFT` —
   it does something other than what was specified.
5. `GAP`/`DRIFT`: name what doesn't match, concretely. Fix. Re-qualify. Three
   attempts, then stop and hand the user the specifics — what's failing, what you
   tried, what you think it means.

Before claiming any task complete:

| Thinking… | Instead | Because |
|---|---|---|
| "should work now" | Run verify, read the output | Confidence isn't evidence |
| "already checked that" | Check it again, fresh | Remembering a check isn't a check |
| "close enough" | Compare to the AC word by word | Close is a GAP |
| "the test passes" | Also compare to the spec | Tests prove what they test, not what was asked |
| "minor deviation" | Say it out loud, now | Deviations compound; wrap needs them accurate |

## Verification: iterate scoped, conclude whole

While working, run the narrow thing:

```
flux run --filter failures -- <the one test file / the one target>
```

Same filtered cost as the gate, none of the wait. To finish, run the gate:

```
flux check
```

`flux check` takes no arguments and never narrows — that's what makes "check passed"
mean anything. **A scoped run is never a completion.** Never report a task or a phase
done on the strength of one green test file. If `flux check` is red, the phase is red,
including when the failure looks unrelated — say so, don't route around it.

## Delegate the reading

- Need to find where something lives, or how a pattern is used → `flux-explorer`.
- Gate failing in a way you need diagnosed → `flux-verifier`. It returns each distinct
  failure once, no stack dumps.

Both exist so the raw output never enters this session. Use them before pasting a
large file or a long log into your own context.

## When something turns out wrong, diagnose before patching

Three different problems look identical at the moment of failure:

- **Intent** — the plan built the wrong thing. Don't patch. Re-plan the phase; mark
  the current plan superseded.
- **Spec** — the plan was right in aim, wrong or silent in detail. Fix the *plan*
  first — the AC or the task — then the code to match. Patching only the code leaves
  wrap reconciling against a lie.
- **Code** — the plan was right, the implementation isn't. Fix in place, re-qualify.

Ask which one it is before you touch anything. Guessing the layer is how a phase
turns into four fragile patches.

## Finish

Report: tasks completed of total; any non-`DONE` statuses and how they resolved; every
deviation from the plan, however small; `flux check` verdict.

Then `/flux:wrap`. Do not close the phase yourself — apply executes, wrap closes.
