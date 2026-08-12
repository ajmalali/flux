# Spec: <feature>

Vocabulary: CONTEXT.md. Decisions: docs/adr/.

_Every heading below appears in the finished spec. Replace each italic line with the
real content; a section with genuinely nothing in it says `None.` rather than being cut._

_No file paths. A spec outlives the layout it was written against, so name the component,
the verb, or the seam that carries the behavior — never the file it currently sits in.
The single exception is a prototype branch: name it as `prototype/<slug>-<question>` so a
reader can check it out._

## Problem statement

_What is wrong today, and for whom. The state of the world without this feature, in a
paragraph — no solution language._

## Solution

_The shape of the answer in one paragraph: the components it adds and what each is for.
Enough that a reader can picture the system, not enough to implement from._

## User stories

_Numbered, one line each, in the voice of the person the feature is for: "I <do
something> and <observe something>." Each one is behavior somebody can see happening._

1. ...

## Implementation decisions

_The choices already settled during the interview, as a bulleted list with the reason
attached to each. A decision that was hard to reverse, surprising, or a real tradeoff has
its own ADR — name it here and keep the rationale there._

## Testing decisions

_How this feature will be proved to work: the level each behavior is tested at, the
fixtures or sandbox it needs, and the command that runs it._

## Acceptance criteria

_Numbered `AC-n`, one observable each, phrased so a person can check it without opening
the code. These are what the tickets will be written against, and what closes them._

- AC-1: ...

## Out of scope

_What was considered and deliberately excluded, each with the reason. This section is what
stops the same question being reopened three sessions later._

## Further notes

_Anything true and worth keeping that fits nowhere above: unresolved externalities,
sequencing that only matters later, a prototype branch worth reading._
