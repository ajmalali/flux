---
name: audit
description: Adversarially review a phase plan before it executes — in a subagent, so the reading never lands in this context. Applies blocking and recommended fixes to the plan in place and returns a verdict. Use after /flux:plan on risky or design-routed work.
disable-model-invocation: true
---

# flux audit

A plan is cheapest to fix before anyone acts on it. This is the last honest read of
it. Not every phase needs one — a mechanical two-task plan usually doesn't. Design
routing, anything touching money, auth, data migration, or a device you can't undo a
mistake on: audit it.

## Run it in a subagent

Dispatch one general-purpose subagent with the plan path and the brief below. The
audit needs to read broadly — the plan, the files it names, the surrounding code — and
none of that reading belongs in the session that will execute the plan. Take back the
findings only.

## The brief

> You are reviewing a plan that is about to be executed by someone who will trust it.
> You are not the author and you are not here to encourage them.
>
> Read `<plan path>`, then read the code it names — enough to know whether the plan
> matches the repo as it actually is, not as it's described.
>
> Report, with specifics:
> - **Assumptions the plan makes and never states.** Anything underspecified is a
>   finding: the executing session will fill the gap by guessing.
> - **Failure paths that aren't in it.** What happens on the second run, on partial
>   completion, on the input that isn't the happy one.
> - **Acceptance criteria nobody could falsify**, and tasks whose `verify` doesn't
>   actually prove `done`.
> - **Blast radius outside the boundaries** — what this quietly breaks elsewhere.
> - **Ordering hazards** — a task that only works if another already landed, unsaid.
> - **What is genuinely solid**, and why. Briefly. It tells the author what not to
>   touch while fixing the rest.
>
> Classify every finding as **blocking** (execute this as-is and it's wrong),
> **recommended** (real, fixable now, cheap), or **deferred** (true but out of scope
> for this phase).
>
> Constraints: judge the plan against its own stated scope — do not import
> requirements from outside it, and do not redesign it. Do not assume a later phase
> fixes anything. No praise that isn't load-bearing.

## No rubber stamps

Every plan has something. A clean audit almost always means the failure paths went
unexamined — go back and look at what happens when the second thing fails after the
first one succeeded. Report "nothing blocking" only when you can say what you looked
at to conclude it.

## Apply the findings

Fold **blocking** and **recommended** into the plan file yourself, in place:

- an AC gap becomes a new or sharpened AC;
- a missing failure path becomes a task line or an AC, not a comment;
- blast radius becomes a `do not change` boundary;
- an unprovable `verify` gets replaced by one that proves it.

Add, don't silently rewrite: mark inserted lines with `<!-- audit -->` so wrap can
tell plan from patch. Then append to the plan:

```markdown
## audit — <date>
verdict: ready | ready with conditions | not ready
applied: N blocking, M recommended
deferred:
- <finding> — <why it's safe to leave>
```

One file, no second artifact. The plan carries its own history.

## Verdict

**ready** / **ready with conditions** → say what the conditions are, then `/flux:apply`.

**not ready** → the plan's premise is wrong, not its details. Do not offer apply. Say
what has to be re-decided and route back to `/flux:plan`.

Report the verdict, the counts, and the blocking findings in one screen. The applied
fixes are in the file; don't re-narrate them here.
