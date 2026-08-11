# Context

Glossary for the Flux harness. Terms are opinionated: one term wins, rejected synonyms are listed under _Avoid_.

## Language

**Ticket**: One unit of implementable work, stored as a bead (or a markdown file pre-beads), carrying its own routing, tasks, test plan, and boundaries.
_Avoid_: task (reserved for the steps inside a ticket), issue, story.

**Frontier**: The set of tickets whose blockers are all closed — what can be worked on right now. Computed (`bd ready`), never maintained by hand.
_Avoid_: backlog, queue.

**Claim**: Atomic assignment of a ticket to one session/worktree. A ticket is claimed before any code is touched.
_Avoid_: pick up, assign.

**Smart zone**: The context budget inside which work stays high-quality. Working rule: specs and tickets are finished before ~50% of the window is used.
_Avoid_: context limit.

**Prime**: The SessionStart injection of current state (claimed ticket, frontier, handoffs, drift) so a session starts oriented without exploration.

**Heartbeat**: The Stop-hook stamp written after every turn, keeping session state fresh even when no skill was invoked.

**Drift**: Work that happened outside the harness — commits referencing no ticket, or a dirty diff with no claim. Detected by prime, repaired by /sync.

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
