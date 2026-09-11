# flux

A Claude Code plugin that handles the boring, repeatable parts of a working session
so you don't have to. At session start it prints where you left off. While you work
it keeps test output short. At the end it saves state for the next session. One
Python file, no dependencies.

## Install

In Claude Code, once per machine:

    /plugin marketplace add ajmalali/flux
    /plugin install flux@marketplace

Then in each repo you want it in:

    flux init

That writes `.flux/flux.toml` with your test command detected. Repos without `.flux/`
are left alone.

## Update

The plugin does not update itself. Run this and restart Claude Code:

    claude plugin update flux@marketplace

It pulls from GitHub `main` and only updates if `plugin.json` has a higher version
than what you have. Existing `.flux/` folders need no changes.

One exception, from 2.12.0: the first `flux state set` or `flux task add` in a repo
appends `tasks.jsonl merge=union` to `.flux/.gitattributes`, so the task index merges
the way the state log already does. It shows up as a one-line diff on a tracked file.
Commit it.

## A typical day

Open a session. flux prints a short pack before you type anything. Branch, current
phase, what to do next, open problems, the last handoff. Read it and start working.

Say the task back in one line and do it. Run the narrow test while iterating, the
full gate when you think you're done:

    flux run --filter failures -- <one test file>
    flux check

`flux check` prints failures only. Green means done. Nothing else does.

When you stop, save where you are so tomorrow's session can pick up cold:

    flux state set position "what is true now" next "first thing to do tomorrow"
    flux handoff
    git commit

Or run `/flux:wrap`, which does all of that in order. If you get past 120 requests,
flux nudges you to wrap and `/clear`. If you quit without wrapping, the next session
opens with a warning.

That's the whole routine for bug fixes and small features. No skills, one session.

## Bigger work

Use the skills when a feature outlives one session, changes something you can't undo,
or you're still arguing about its shape. The work goes into the task index, and a
session takes one task or one batch from it.

1. `/flux:plan` decomposes the design into the index. Tracers are thin end-to-end
   slices with a spec file each. Fills widen a proven slice from a one-line title.
2. `/flux:audit` picks a tracer's spec apart before you act on it. Skip for mechanical
   work.
3. `/flux:apply` takes `flux task next`. A tracer runs in your session. Fills run as a
   batch in subagents; one that can't finish gets escalated to a tracer, not retried.
   A task whose check is something only you can see, like a phone in your hand, is
   parked as awaiting and the next session opens on the steps.
4. `/flux:wrap` re-runs each done task's own verify, reopens what fails, saves state,
   commits.

The next session reads the pack and takes the next task. Nothing is planned twice.

We measured the old plan-per-phase path twice on single-session work. It cost 3x and
delivered the same result, so don't reach for it out of habit.

## Skills

All are user-invoked. The model never sees them unless you type the command.

| Skill | What it does |
|---|---|
| `/flux:plan` | Decomposes work into the task index: one `flux task add` per task, tracers with a spec file, fills with a title and files. Closes by reading back `flux task next`. |
| `/flux:audit` | Reviews a plan adversarially in a subagent so the reading never lands in your context. Fixes blocking problems in place and returns a verdict. |
| `/flux:apply` | Takes the next task. Puts an awaiting task to you, runs a tracer in your session, or dispatches a batch of fills to subagents and escalates what can't finish. Reports status honestly, then checks its own output against the spec before calling anything done. |
| `/flux:wrap` | Ends the session. Runs `flux check`, re-runs every done task's own verify and reopens failures, writes the tracer's outcome, writes state, generates the handoff, commits. |
| `/flux:grill` | Interviews you relentlessly about a design until it holds up. Writes ADRs as it goes. Use before `/flux:plan` when the idea is still soft. Vendored from mattpocock-skills, MIT. |
| `/flux:adopt` | Moves a repo's existing project docs (PAUL, STATE.md, ROADMAP.md, a fat CLAUDE.md) into `.flux/`. Optionally archives the old framework. Once per repo. |

## Commands

| Command | What it does |
|---|---|
| `flux check` | Runs your configured test command, prints failures only. |
| `flux run --filter failures -- <cmd>` | Same filter on any one command. |
| `flux state set <key> "<value>"` | Writes `phase`, `position`, `next`, or `open`. Refuses to go over budget. |
| `flux task add "<title>" [--files a,b] [--blocked-by t-x] [--tier fill --tracer t-x]` / `start <id>` / `done <id> --by "…"` | The execution index. One append-only log of what is left; `done` has to say what verified it. A fill waits on its tracer. |
| `flux task escalate <id> --why "…"` / `await <id> --steps "…"` / `reopen <id>` | Raise a fill to a tracer when a subagent can't finish it. Park a task on a person with the steps they follow. Reopen a done or awaiting task. |
| `flux task next` / `flux task list` | Which task is next, derived — not asserted. An awaiting task comes first. `start` leases the task across worktrees, so a second session skips it. `prime` shows the current task and the counts in place of `phase`, plus the awaiting steps clipped; the handoff carries them whole. |
| `flux handoff` | Writes a short handoff from git status, state, and recent commits. |
| `flux log <tag> "…"` | Field note when the pack missed something you needed. Tags are `pack-miss`, `audit-hit`, `want`. |
| `flux ledger` | Reads your session transcripts and prints context size, request counts, wrap rate, and cost per session. `--verdict` scores whether each feature moved its metric. |

Every feature in flux names a metric it has to move. Two cycles without movement and
it gets deleted. That rule has already removed eight skills and two agents.

## Development

    python3 -m unittest discover -s tests

Design docs live in `.flux/plans/flux-v2/`. The old v1 harness is archived at tag
`v1-final`.
