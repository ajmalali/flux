---
name: resume
description: Pick up where the last session stopped — read the primed pack, reconcile it against the tree, name exactly one next action, start. Use at the beginning of a session, or after a context clear.
disable-model-invocation: true
---

# flux resume

The pack is already here. `flux prime` ran at session start and put `phase`,
`position`, `next`, `routing`, `open`, the check command and the latest handoff into
this context. Resume is what you do with it, not another read.

## 1. Use the pack you have

Don't re-read state, don't re-derive position, don't open the handoff unless the pack
points at it for a reason. If no pack is in context — prime didn't fire, or `.flux/`
is new — run `flux prime`; if that prints nothing, this repo hasn't adopted flux and
`flux init` is the answer.

## 2. Read exactly one more thing

If `next` names a plan, open that plan. Nothing else. The pull toward "just skimming
the recent commits first" is what a primed pack exists to replace — that reading was
already done, at wrap, by a session that had the full picture.

## 3. Reconcile before you work

State was written by a session that then stopped; the tree may have moved since.
Check the cheap disagreements:

- Dirty files `position` never mentions → something happened after the last wrap.
- `next` pointing at a plan already marked `status: done` → the wrap was incomplete.
- `open` items that the code shows are resolved → say so and clear them.

Found a disagreement: name it, ask if it's not obvious which side is true, and fix
state before starting new work. Working on top of wrong state is how a phase silently
goes off-plan.

## 4. Name one action, then take it

One. Not a menu, not three options with tradeoffs — the position determines the move:

| Position | Action |
|---|---|
| No plan for the current phase | `/flux:plan` |
| Plan written, not executed | `/flux:apply <path>` (or `/flux:audit` first, if the plan says it's risky) |
| Applied, not closed | `/flux:wrap` |
| Phase closed | `/flux:plan` for the next one |
| `open` names a blocker | Clear the blocker — it outranks the queue |

Say the action in one line with its path, and go. If the user wants something else
they'll redirect; asking first spends a turn to learn what a redirect would have told
you for free.

## Routing

`routing: design` means the shape is still open — expect to think before typing.
`routing: mechanical` means it's settled — expect to execute. It's a stamp from the
plan, not permission to switch models mid-session.
