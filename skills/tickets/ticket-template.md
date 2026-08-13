# Ticket template

_One shape, two stores. What follows is the ticket as it reads on paper; the store it
lands in decides how much of it is literal — see **Where each field goes** at the bottom._

---

```markdown
---
id: <stamped by the store — never chosen by hand>
title: <one line, what changes and for whom — not how>
status: open
agent: chore | build | deep
effort: low | medium | high
blockers: [<ticket id>, ...]
checkpoint: human-verify | decision | none
---

Spec: specs/<slug>/spec.md (AC-n, AC-m; user story k). <ADR-nnnn, only when a Boundary
below quotes it.>

## Context

_Why this ticket exists and what the implementer needs to know before touching anything:
the constraint that shaped it, the prior art already in the repo, the thing that will
look wrong and isn't. One or two paragraphs. Never a restatement of the Tasks._

## Tasks

_Numbered, in the order they are done. Every task states four things, and a task missing
any of them is not ready to be written — see the F/A/V/D rule below._

1. Files: <the paths this task may touch, or `(none)` for a task with no diff>
   Action: <what to do to them, specifically enough that two implementers would produce
   the same shape>
   Verify: <a command, run fresh, whose output settles it>
   Done: <the observable that makes it true, naming the AC it satisfies>

## Test plan

_How this ticket proves itself as a whole: the level each behavior is tested at, the
fixtures or sandbox it needs, and what a live run means when the verify is a live run._

## Boundaries

_The edge of the work. What this ticket does not touch, what it must not generalize, and
where a tempting adjacent fix belongs instead. This is the section that keeps a routed
agent inside its lane._
```

---

## The F/A/V/D rule

If you cannot specify **Files**, **Action**, **Verify**, and **Done** for a task, the
task is too vague — split it or ask. That rule is not paperwork. Each of the four is
load-bearing for a different reader:

- **Files** is the blast radius. A task that cannot name its files has not been decided
  yet, and the implementer will decide it instead, in the worst window for it.
- **Action** is the brief. Written thinly it invites improvisation; written as a plan it
  stops being a ticket.
- **Verify** is a command someone runs fresh and reads the output of. "Check that it
  works" is not one. Where the only honest verify is a person looking at the result, that
  is not a weak Verify — it is a `checkpoint`, and it is marked in the frontmatter.
- **Done** is what closes the task, phrased as an observable and naming its AC. It is
  what a qualify cycle compares the Verify output against.

Splitting is the usual fix, and asking is the other one: a task that resists F/A/V/D
because the spec never settled the question is a question for the spec's author, not a
gap for the implementer to fill.

## Where each field goes

**Beads (`bd`).** The frontmatter is never written as text. `id` and `status` are the
bead's own; `agent` and `effort` and `checkpoint` are labels — `deep`, `effort:medium`,
`checkpoint:human-verify`; `blockers` are dependencies (`bd dep add <ticket> <blocker>`).
Everything from the `Spec:` line down is the description, verbatim.

**Markdown fallback.** The frontmatter is literal YAML at the top of
`specs/<slug>/tickets/NN-<kebab-title>.md`, and the body follows it unchanged. `status`
moves in place (`open` → `in_progress` → `done`); `blockers: []` when there are none.

Either way the body is identical, which is the point: a ticket read out of one store is
the same ticket read out of the other.
