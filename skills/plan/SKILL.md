---
name: plan
description: Interview an idea into an approved spec, inside the smart zone. Use to plan a feature, turn a ticket or an ADR into a spec, or resume a paused planning discussion.
disable-model-invocation: true
---

Take one idea and leave with a spec its author has approved, written before the window
degrades. This run produces `specs/<slug>/spec.md` and nothing else: tickets are a
separate session (ADR-0003), and code stays out of bounds apart from a prototype branch.

## 1. Open

The input arrives as an idea in prose, a ticket id, or an ADR pointer. A ticket id means
`bd show <id>`, or the matching file under `specs/*/tickets/` when `bd` is absent; an ADR
pointer means read that ADR. An unconsumed handoff in `.flux/handoffs/` naming this
feature means a resumed discussion. What consuming it obliges belongs to the pause skill
and is written down once, there — read that file and follow it:

    ${CLAUDE_PLUGIN_ROOT}/skills/pause/SKILL.md

The questions the handoff lists are the frontier you start from.

Settle the slug before the first question: kebab-case, one directory, `specs/<slug>/`. A
`spec-draft.md` already sitting there is the resumed draft; keep its sections and carry on.

Say one line back before grilling starts — the problem in your own words, the slug, and
the two budget marks from step 4, which are advice rather than stops.

## 2. Grill

Invoke `flux:grilling` and work its design tree until the frontier is empty.
Keep `flux:domain-modeling` active for the whole run: a term that settles
goes into `CONTEXT.md`, and a decision meeting the ADR bar goes into `docs/adr/`, in the
round it settles rather than at the end.

The spec is deposited the same way. Close every round by writing what it settled into
`specs/<slug>/spec-draft.md`, under the heading it belongs to in the template. The draft
appears the round the first section settles and is current at every round boundary after
it — never a document you sit down to compose, only one you have been keeping. A later
round that overturns an earlier answer edits the heading it already wrote.

Depositing as you go is what makes a pause cheap, and it is what keeps the spec out of the
degraded end of the window: sections get written at the quality of the round that settled
them, not at the quality of the last round of a long conversation.

Facts about this codebase arrive as summaries. Query gitnexus when the repository is
indexed; otherwise dispatch one `Explore` subagent per open question, briefed to return
findings and line references rather than file contents. A file read into this window
spends on one question what a scout answers in a paragraph.

Head each round with its ledger, so both parties can see the budget being spent:

```
Round 2 · 5 questions · 1 scout
```

## 3. Prototype detour

A question that only running code can answer earns a detour: invoke `flux:prototype`,
on a throwaway branch named `prototype/<slug>-<question>`.
Return with the answer, and with the branch name when the spec should point a reader at
it. The working branch ends the detour exactly as it started.

## 4. Budget

`.flux/session.json` carries this session's token count, stamped by the heartbeat at the
end of every turn. Read it at every round boundary, never mid-round:

    jq -r '.context_tokens' .flux/session.json

That count is absolute rather than a share of the window, and it has two marks. It is the
same number the status line shows the user, as of the last completed turn — so quote it as
read, and never estimate one. `null` means this session cannot know its count: say that
plainly instead of substituting a guess, and work the context-pressure rule below, which
needs no number.

Both marks are advice. Whether a run stops is the user's call and never yours: report the
count, say what you would do, and carry on grilling unless you are told otherwise.
Continuing past either mark is a legitimate answer — a run whose draft is current stays
cheap to abandon at any point, which is what buys the user that freedom.

**200k — first notice.** One line of its own: the count, and how much frontier is left.

**350k — second notice.** One line again: the count, the frontier, and that this is where
the status line starts showing `/pause`. Recommend stopping, then do as the user says.

A context-pressure notice — approaching compaction, or a low-context warning — is not
advice and is not the user's discretion. It is a real limit arriving, so pause on it at
the next round boundary whatever the count reads. This is what keeps a run safe on a
window too small to reach either mark.

Pause when the user calls it, or when context pressure forces it. The steps belong to the
pause skill and are written down once, there — read that file and follow it:

    ${CLAUDE_PLUGIN_ROOT}/skills/pause/SKILL.md

It is user-invoked, so this run reaches it by reading it rather than by invoking it. Carry
one fact in: the draft has been kept current every round, so its deposit step covers the
round in progress and nothing earlier.

That ends the run. Resuming happens in a fresh window, at step 1.

## 5. Promote the draft

Frontier empty: the draft already holds every settled section, so this step is promotion
and not composition. Read `specs/<slug>/spec-draft.md` against the template beside this
file,

    ${CLAUDE_PLUGIN_ROOT}/skills/plan/spec-template.md

fill any heading the rounds left thin, apply the rules the template states, then save it
as `specs/<slug>/spec.md` and delete the draft. Acceptance criteria are the section that
decides whether this spec was worth writing: each one names an observable, and reads as
something a person could check without opening the code.

## 6. Approval

Present the spec for approval — the acceptance criteria in full, and one sentence per
other section. Requested changes are edits to the file. A change that opens a new question
puts that question back on the frontier and returns you to step 2, budget still counting.

On approval, close with what changed — the terms added to `CONTEXT.md`, the ADRs written,
the spec path — and the next move: `/flux:tickets`, in a session that has read nothing
else. Tickets are never written here.

## Done

Two endings, and no third: an approved `specs/<slug>/spec.md`, or a `spec-draft.md` with
a handoff beside it. A run that produces neither is still running.
