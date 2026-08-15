---
name: pause
description: End a long run cheaply — deposit what settled into its durable home, then write a thin handoff a fresh session resumes from. Use to stop a discussion before the window degrades, or when context pressure forces it.
disable-model-invocation: true
---

Take one run that has gone long and leave it resumable at almost no cost: everything
settled written into the place that already owns it, and a handoff carrying only what has
no home yet. Two steps, in this order — deposit, then residue. The order is the whole
design: residue is defined as what deposit left over, so a handoff written first is a
handoff that duplicates a spec section instead of pointing at one.

## 1. Deposit

Settled knowledge goes to its durable home, and there are only three:

| | |
| --- | --- |
| **CONTEXT.md** | Vocabulary this run started using and would otherwise re-agree next session. Match the file's shape — the term, one definition, an `_Avoid_` line naming the synonyms it beat. |
| **docs/adr/** | A decision that was hard to reverse, surprising, or a real tradeoff. The filename states the decision as a sentence, because `ls docs/adr/` is the index. Anything under that bar is not an ADR; it is a line in the spec. |
| **specs/\<slug\>/spec-draft.md** | Sections the run agreed, each under the heading it belongs to in the spec template. A planning run has been keeping this every round, so this covers the round in progress and nothing more. |

A fact that fits none of the three is not settled. It is residue, and step 2 is where it
goes — as an open question or as the current hypothesis, marked provisional.

Nothing settled at all is a legitimate outcome, not a failure: the deposit is a no-op,
say so, and go on to write the handoff anyway. A run that produced only questions is
exactly the run worth handing off.

## 2. Residue

Write `.flux/handoffs/<branch>-<slug>.md` from the template beside this file,

    ${CLAUDE_PLUGIN_ROOT}/skills/pause/handoff-template.md

taking `<branch>` from `git rev-parse --abbrev-ref HEAD` with slashes turned to dashes,
and `<slug>` from the feature the run was about. One file per paused run, in that
directory only — never the repo root, never the OS temp dir. `.flux/` is machine state
and gitignored (ADR-0001), so a handoff is per-worktree by construction and never
travels in a commit.

Then read what you wrote against the one criterion that makes it a handoff:

> the handoff contains zero facts absent from the Deposited paths — only questions,
> hypothesis, next action.

The check is mechanical. Take each sentence and ask whether a reader could learn a
settled fact from it; if they could, that sentence belongs in a durable home and its path
belongs under **Deposited** instead. Restating a spec section here is a bug, not
thoroughness — two copies of a decision is how the next session ends up working from the
stale one.

## 3. Hand back

Print the deposited paths and the handoff path, then one line, verbatim in spirit:

    paused — /clear or close the terminal; next session will surface this.

That is the end of the run. Do not carry on working: the whole point of the pause was
that this window is the expensive one.

## Resuming

Presence in `.flux/handoffs/` means unconsumed — prime prints filename and first line
every session until something takes it. Whoever reads that file is what takes it, and the
reading obliges three things, written here and in no other file: read the handoff, move it
to `.flux/handoffs/done/`, and treat its Deposited paths as settled. The obligation binds
a reader rather than a role — a skill, an agent, or a session that resumed from prime's
line with nothing invoked at all owes the same three. A resumed discussion never re-asks a
question already answered, which is the acceptance criterion this whole skill exists for
(AC-10).

Reading the handoff is the resume. There is no resume command and none is wanted: by the
moment anyone could invoke one they have already read the file, so the command would only
announce a step that had happened.

## Done

The durable homes written, or a stated no-op. A handoff at
`.flux/handoffs/<branch>-<slug>.md` whose four headings hold questions, a hypothesis, a
next action, and paths — and no fourth kind of thing. The user told, in one line, that
the session is safe to end.
