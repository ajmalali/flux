---
name: tickets
description: Decompose an approved spec into routed, self-contained tickets, in a window that has read nothing else. Use after /flux:plan, or to re-ticket a spec that has changed.
disable-model-invocation: true
---

Take one approved spec and leave with the tickets that implement it, written in a window
clean enough to do precision work. This run writes tickets and nothing else: no code, no
spec edits, no exploration of the codebase the tickets will land in.

## 1. The guard

Ticket decomposition is the most precision-hungry step in the harness, and the window it
runs in is an input to it (ADR-0003). So the first thing this skill does is look at the
window it was invoked in, before it reads the spec.

Two checks. Either one trips.

**The count.** `.flux/session.json` carries this session's token count, stamped by the
heartbeat at the end of every turn and by prime at session start:

    jq -r '.context_tokens' .flux/session.json

Over 50,000, the window is polluted — that is the mark ADR-0003 cites, where context-rot
research puts the start of degradation. `null` means this session cannot know its count:
say so plainly, never substitute an estimate, and let the second check decide alone.

**The window itself.** Anything in this session other than the prime block, the user's
invocation, and this skill. A file read, a test run, a design argued, a spec written here
— `/flux:plan` in this same window is the case this guard exists for, and it is the one
most likely to be tried.

Polluted, either way: refuse in one line and stop.

    run /clear first, then /tickets <spec-path>

Do not soften it, do not offer to continue carefully, and do not weigh how the window
feels — a degraded window reads as a fine one from the inside, which is the whole reason
the check is mechanical. Refusing costs one `/clear`. Being wrong costs a decomposition
written at the bad end of a long conversation, and that failure is silent: the tickets
look plausible and go wrong three sessions later.

A user who answers the refusal by telling you to proceed anyway has made a call that is
theirs to make. Honour it, and say so in this run's first line and again beside the
printed mapping, so these tickets are never mistaken for ones written clean.

## 2. Read the spec, and nothing else

The input is a spec path. Absent: name the `specs/*/spec.md` files that exist and ask
which — never guess, and never ticket a `spec-draft.md`, which by definition is a run
that has not finished.

Read exactly two things: `specs/<slug>/spec.md` and `CONTEXT.md`. The spec's user stories
and acceptance criteria are what you decompose; the glossary is the vocabulary every
ticket is written in — use those terms exactly, and never a synonym listed under _Avoid_.
One exception, and it is narrow: an ADR the spec names by number, when a ticket's
Boundaries have to quote it. Read that one file, not the directory.

Nothing else. Not the codebase, not the existing tickets, not the files a ticket will
touch. The pull to go and look is real and it is the guard failing in slow motion: a spec
that cannot be decomposed without opening the code has a gap, and a gap is a question for
its author (step 5), not an excuse for a file read.

Say one line back before anything else: the spec path, how many user stories and ACs it
carries, and how many slices you are proposing.

## 3. Slice

Cut the spec into tracer-bullet vertical slices — each one the thinnest end-to-end thing
that works and can be seen working.

- **One window per ticket.** A slice a fresh session can finish, including its verify. If
  it needs two windows it is two tickets; if three slices are one file each, they are
  probably one ticket.
- **Vertical, not layered.** No ticket whose only output is a schema, a config stub, or a
  scaffold nobody calls. A ticket that cannot state what observably works when it closes
  is a layer, not a slice.
- **Ordered by dependency, not convenience.** The order tickets are written in is the
  order they can be built in.
- **Coverage is the completion criterion.** Every user story in the spec is covered by at
  least one ticket, and every ticket names the ACs it serves. Both directions get checked
  and printed in step 7.

## 4. Score, route, mark

Give every slice a complexity score, 1–10, and let the score choose the agent. Score what
the ticket leaves undecided, not how long it takes: novelty of the design left to the
implementer, blast radius across the codebase, how much ambiguity survives the spec, and
whether the Verify is a command or a judgement.

| Score | `agent:` | What it means |
| --- | --- | --- |
| 1–3 | `chore` | Already decided. Mechanical. The verify command is the entire safety net. |
| 4–7 | `build` | Clear spec, agreed seams, existing patterns in the repo to follow. |
| 8–10 | `deep` | Novel design inside the ticket, cross-cutting change, or a diagnosis. |

**Effort is a separate axis** — `low`, `medium`, `high` — and it measures how much work,
not how hard. A deep ticket can be low effort: an hour of thinking and twenty lines. A
chore can be high: a sweep across sixty files with nothing to decide. Score them
independently and do not let one drag the other; a routing tier inflated by size sends
easy bulk work to the expensive model, and one deflated by it sends design to haiku.

**Checkpoint** is for what a machine cannot judge, and only that. `human-verify` where the
acceptance criterion is felt or seen — an interface, a diagram, the experience of a loop.
`decision` where the work must stop for a human choice before it can continue. Anything
with an executable Verify is not a checkpoint, however important it is. Checkpoints are
hard stops in `/flux:run`, so a decorative one stalls the frontier.

## 5. Blockers, and the questions

Declare a blocker only when it is one: A is blocked by B when A cannot be *verified* until
B is done. Touching the same file is not a blocker; reading better in order is not a
blocker. Every false blocker is a ticket the frontier will not offer.

Ids do not exist yet — the store stamps them at creation — so blockers are carried as
slice numbers (S1…Sn) until step 6 wires them.

Then collect what you cannot answer from the spec:

- **Spec gaps** — anything a ticket would have to invent to be writable. These go back as
  questions. Never invent scope absent from the spec, and never edit the spec to close a
  gap; that is a `/flux:plan` run, in its own window.
- **Edge cases the spec implies but does not state** — each one a question with your
  proposed answer attached, so it costs one word to settle.

## 6. Quiz, then write

Nothing is written until the user has answered. Present all of it in one message:

1. The slice list — one line each: number, title, tier, effort, checkpoint, blockers by
   slice number.
2. The mapping, both directions: user story → slices, and slice → ACs.
3. **The granularity question.** Name the two slices you were least sure about and say
   which way you would move them — split this one, merge these two — then ask.
4. The edge cases and the spec gaps from step 5.

Then stop and wait. Answers that move the shape mean reshaping and re-presenting, not
patching the list in place.

On approval, write the tickets in the shape of the template beside this file,

    ${CLAUDE_PLUGIN_ROOT}/skills/tickets/ticket-template.md

which also states where each frontmatter field lands in each store, and the F/A/V/D rule
every task is written against.

**With `bd`.** Create in dependency order, capture the id each create returns, then wire
the blockers with the ids you captured:

```bash
id=$(bd create "<title>" -t task -l build,effort:medium --stdin --silent <<'BODY'
Spec: specs/<slug>/spec.md (AC-3; user story 2).

## Context
...
BODY
)
bd dep add "$id" "<blocker id>"
```

Labels carry the frontmatter: the tier (`chore`/`build`/`deep`), `effort:<low|medium|high>`,
and `checkpoint:human-verify` only when there is one. Read anything back with `--json`.

**Without `bd`.** Write `specs/<slug>/tickets/NN-<kebab-title>.md`, numbered in dependency
order, frontmatter literal and `status: open`, `blockers: [<PREFIX>-03]` naming the ids
you assigned.

## 7. Print the mapping

The run ends with the mapping on screen, both directions, because it is the completion
criterion and not a summary:

- every user story, and the tickets covering it — a story with none is a hole, and you
  say so rather than closing the run;
- every ticket, its ACs, tier, effort, checkpoint, and blockers.

Close with the frontier (`bd ready --json`) and the next move: `/flux:build`, one ticket
per fresh session.

## Done

Every user story covered, every ticket naming its ACs, the mapping printed — or a refusal
with nothing written. There is no third ending, and a run that answers questions about a
spec without producing tickets is still running.
