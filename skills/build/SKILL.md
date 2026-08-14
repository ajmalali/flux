---
name: build
description: Implement one ticket end to end — atomic claim, minimal context, Execute→Qualify per task, close with a commit that names the id. Use to build a ticket off the frontier by hand.
disable-model-invocation: true
---

Take one ticket and leave with it closed: claimed atomically, implemented task by task,
every Verify run fresh, and a commit that names its id. The ticket is the brief — its Tasks
are the work, its Boundaries are the edge of the work, and this run stays inside both.

## 1. Claim, before anything is read

The claim comes first because it is state rather than intent (ADR-0001). A session that
reads for ten minutes and then finds the ticket held has already spent the window the claim
was there to protect.

The input is a ticket id. Absent: print the frontier and ask which one — never choose for
the user.

    bd ready --json

**With `bd`.** One command, atomic:

    bd update <id> --claim -a "$(basename "$PWD")"

The assignee is the worktree, not you, and that is load-bearing rather than cosmetic: prime
and the status line ask the store what *this worktree* holds, so a ticket claimed under a
person's name is claimed invisibly (ADR-0005, AC-4). `--claim` moves it to `in_progress` in
the same write, and re-running it on your own claim is a no-op rather than an error.

Held elsewhere, it exits non-zero and names the holder:

    Error updating FLX-11: issue already claimed by <worktree>

That is the end of the run. Say who holds it and stop. `--force` exists for a claim
abandoned by a crashed session, and taking one is the user's call, never yours.

**Without `bd`.** Read `specs/*/tickets/<id>-*.md`, refuse unless `status: open`, then set
`status: in_progress` and the worktree in a single edit — two edits is a race with nothing
atomic about it.

## 2. Load the ticket, then stop loading

Minimal context is the rule this skill is built around. A ticket was written to be
implementable from itself; every file read beyond it is a bet that the ticket was wrong
about that, and the bet is paid for in the same window the work happens in.

The whole of what this run may read before a task asks for more:

- the ticket body — `bd show <id> --json`, and `--json` on every read from the store, because
  the human-readable output is a rendering clipped to a terminal width;
- the one section of the spec its `Spec:` line names — that section, not the spec;
- `CONTEXT.md`, which is the vocabulary the ticket is written in;
- gitnexus `context` on the symbols the ticket names, where the repo is indexed;
- the files a task's `Files:` line names — when that task starts, not before.

Not the rest of the spec, not the neighbouring tickets, not the codebase at large, and not
`docs/adr/`: the ADRs are read at close, against a finished diff, where they cost one `ls`
and answer a question the diff has already asked.

Then say one line back before touching anything — the ticket id and tier, how many tasks,
and the acceptance criteria it names.

## 3. Execute, then Qualify

Tasks are done in order, one at a time, and task n+1 does not begin until task n qualifies.

**Execute.** Perform the Action on the named Files. Where the ticket pre-agreed a seam,
invoke `flux:tdd` and test at that seam — the seam was chosen when the ticket was written,
which is a better window for that decision than this one. Follow the patterns already in
this codebase rather than importing your own.

**Qualify.** Three moves, in this order: re-read the output you actually produced; run the
task's Verify command fresh in this session and read what it printed; compare both against
the task's Done and against the acceptance criterion that Done names. Never from memory,
never from an earlier run, never from what the edit was supposed to do — only from output
you have just read. The failure this prevents is not laziness, it is confidence: an edit
that went in cleanly reads as an edit that worked, and the Verify is the only thing that
knows the difference.

## 4. Three cycles, then stop

Three failed qualify cycles on one task is the limit. Do not attempt a fourth — classify
the failure instead and escalate with the classification, because the classification is
what decides whose problem it is:

| | |
| --- | --- |
| **intent** | The ticket wants the wrong thing. It goes back to `/flux:plan`; nothing here can fix it. |
| **spec** | The ticket or its acceptance criteria are wrong or incomplete. Fix those first — code written against a wrong Done qualifies against a wrong Done. |
| **code** | The ticket is right and the implementation is wrong. A targeted fix is enough. |

A boundary is not a cycle and gets no attempts at all. The ticket's Boundaries are absolute
and never rationalized: on conflict, stop and escalate, however small the crossing looks
from inside the task. Work discovered along the way becomes a ticket, not a detour:

    bd create "<title>" -t task -l <tier>,effort:<size> --deps discovered-from:<id> --stdin

## 5. Close

Four steps, in order.

**The message.** Write `.flux/commit-msg` — the subject `<TICKET-ID>: <one line>` at 72
characters or fewer, a blank second line, the body wrapped, a `Co-Authored-By:` trailer
last. Prose is the only part of a commit that is yours (ADR-0011); staging and committing
are machinery, and machinery that an agent performs by hand is where an unrelated edit
sitting in the tree rides along.

**The close.**

    bd close <id>

That is the trigger: `bin/flux-commit` stages the ticket's files, commits from the slot,
deletes it, and prints what it staged and what it left dirty. Read that output. A path left
dirty is the script saying the ticket named it too vaguely to stage safely, and resolving
that is part of closing, not a footnote to it.

Where that script is not wired in this repo, the slot survives the close untouched. Then
commit it by hand — stage the ticket's files only, `git commit -F .flux/commit-msg`, delete
the slot — and say in the closing report that this is what happened, so a commit made by
hand is never mistaken for one the harness made. If that commit comes back denied, the
guard is wired and the script is not: stop and say so. Working around a fail-closed deny is
worse than the gap it just found (ADR-0012).

**The reconciliation.** `ls docs/adr/` — the filenames state their decisions as sentences,
so the listing is the index and reading it costs almost nothing. Open only the ones the
finished diff touches. Vocabulary the diff introduces may be added to `CONTEXT.md`. A
contradiction with an ADR is flagged for the human and never resolved here: an ADR is
superseded deliberately, with a number, or it is not superseded (ADR-0010).

**The handback.** Report what changed, and offer `/flux:show-work <id>`.

## Done

Every task's Verify command run fresh in this session with its output shown — listed,
command and result, because a Verify nobody printed is a Verify nobody can tell was run.
The ticket closed, and a commit naming its id.

One other ending is legitimate, and it is step 4's: a classified escalation, the ticket
still claimed, nothing invented to get past the wall. What is never an ending is a task
that qualified from memory.
