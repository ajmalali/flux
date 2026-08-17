# Context

Glossary for the Flux harness. Terms are opinionated: one term wins, rejected synonyms are listed under _Avoid_.

## Language

**Ticket**: One unit of implementable work, stored as a bead (or a markdown file pre-beads), carrying its own routing, tasks, test plan, and boundaries.
_Avoid_: task (reserved for the steps inside a ticket), issue, story.

**Frontier**: The set of tickets whose blockers are all closed — what can be worked on right now. Computed (`bd ready`), never maintained by hand.
_Avoid_: backlog, queue.

**Claim**: Atomic assignment of a ticket to one session/worktree. A ticket is claimed before any code is touched.
_Avoid_: pick up, assign.

**Smart zone**: The context budget inside which work stays high-quality. Working rule: a planning run gives notice at 200k tokens and again at 350k — an absolute count rather than a share of the window, which means something different on a 200k model than on a 1M one. Both notices are advice, and stopping is the user's call; what keeps the run safe is that settled work is deposited every round, not the mark itself. A context-pressure notice is not advice and pauses the run.
_Avoid_: context limit.

**Prime**: The SessionStart injection of current state (claimed ticket, frontier, handoffs, drift) so a session starts oriented without exploration.

**Heartbeat**: The Stop-hook stamp written after every turn, keeping session state fresh even when no skill was invoked.

**Drift**: Work that happened outside the harness — commits referencing no ticket, or a dirty diff with no claim. Detected by prime, repaired by /sync.

**Baseline**: The commit up to which work is accounted for — ticketed, or accepted on the record by a declined reconciliation. Drift is measured from it and only /sync moves it. A baseline that is no longer in the current history, after a rebase or an amend, is *unresolvable*: drift reads zero until /sync re-anchors it, which is a different answer from a clean tree and is reported as one.
_Avoid_: sync point, last synced commit (that is the field it is stored in, not the concept).

**Durable home**: The one permanent place a piece of knowledge lives: glossary terms in CONTEXT.md, decisions in docs/adr/, specs in specs/. Everything else may only point at it.
_Avoid_: notes, state file.

**Residue**: What remains after settled knowledge is deposited into durable homes: open questions, current hypothesis, next action. Residue is all a handoff may contain.

**Handoff**: A thin residue file in .flux/handoffs/ that lets a fresh session continue a paused discussion. Consumed on resume.
_Avoid_: pause file, session dump.

**Routing tier**: Which agent implements a ticket — chore (haiku), build (sonnet), or deep (opus) — decided at ticket-writing time from complexity.
_Avoid_: model selection.

**Checkpoint**: A ticket attribute meaning the loop must stop for a human — human-verify or decision. Only for what genuinely needs human eyes; anything mechanically verifiable is automated.

**Qualify**: The post-task check: re-read actual output, re-run the verify command fresh, compare against spec and acceptance criteria. Three failed qualify cycles escalate with a classification (intent / spec / code).
_Avoid_: review (reserved for human review), validate.
