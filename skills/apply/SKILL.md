---
name: apply
description: Execute the next task from the index (`flux task next`), or the task as the user stated it. An awaiting task is put to the person; a tracer runs here; fills dispatch to subagents as a batch. Execute, report status honestly, qualify against the spec. Iterates with `flux run --filter failures`, concludes with `flux check`.
disable-model-invocation: true
---

# flux apply

Execute the work. The spec is the task's `--ref` file, its index line, or the request
as the user worded it; your memory of executing it is not evidence. Say the task back
in one line, with the files you expect to touch, before you start.

## Which shape this session is

Read `flux task next`. It decides, in this order:

- **Awaiting head** — the line carries `awaiting:`. Print the steps, ask the person to
  do them, and resolve on their word alone — `flux task done <id> --by "<what was
  observed>"` or `flux task reopen <id> --why "<what failed>"` — then stop. Nothing
  else runs in a session that opened on a human checkpoint; `done --by` is its end.
- **Tracer** — no `tier: fill`. `flux task start <id>`, read its `--ref` spec once, in
  full, then execute → report → qualify below. One tracer per session; when it is
  done — `flux task done <id> --by "<evidence>"` — the session is done.
- **Fill** — `tier: fill`. Take the batch: `flux task next --all`, keep the fills,
  `start` each. Dispatch each to a built-in `general-purpose` subagent on the parent's
  model with a spec composed at pickup — title, `files`, `verify`, the tracer's ref —
  and the status table below as its report format. Sequential by default; parallel
  only when the declared `files` are disjoint. **The parent edits nothing.**

No index, or nothing runnable? The task is what the user asked for and the boundary is
the files that answer it. Execute it here as a tracer would, without `start`/`done`.

One tracer *or* one batch, never both.

## Per task: execute → report → qualify

### 1. Execute

Do the task's `do`, to the files in its `files`; respect the spec's boundaries. When
a change you want falls outside, stop and say so — do not make it "just this once";
untracked edits are what makes the next plan wrong.

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
3. **Compare against both** the task's `do` and its linked AC, line by line —
   or, with no plan, against the request as the user worded it.
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

## Escalate, never retry

A fill that reports `NEEDS_CONTEXT` or `BLOCKED`: `flux task escalate <id> --why
"<what it said>"` and move to the next independent fill. The parent does not retry it,
does not finish it, does not open its files to "just see". A tracer session will.

After the batch, the gate once:

```
flux check
```

Red → re-run each fill's own `verify`; `escalate` the one that fails; the green fills
stay. Then `flux task done <id> --by "<evidence>"` for each fill that passed — the
evidence is the verify output, not the subagent's word.

A `verify` that is a human observation — a phone, a screen, a device — is not run
here: `flux task await <id> --steps "<what the person does>"`, and the session ends
there. The next one opens on it.

## Verification: iterate scoped, conclude whole

While working, run the narrow thing:

```
flux run --filter failures -- <the one test file / the one target>
```

To finish, the gate — `flux check`, no arguments, never narrowed. A scoped run is never
a completion. Red is red, including when the failure looks unrelated: say so.

## When something turns out wrong

Intent (the wrong thing got built: re-plan, don't patch) · spec (right aim, wrong
detail: fix the spec, then the code) · code (fix in place, re-qualify). Name the layer
before touching anything.

## Finish

Report: tasks done of total, by id; every non-`DONE` status and how it resolved; every
deviation from the spec, however small; `flux check` verdict. Then `/flux:wrap` —
apply executes, wrap re-verifies each done and closes. Working without an index,
record what moved with `flux state set` and stop.
