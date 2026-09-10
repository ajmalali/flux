# flux execution

The vocabulary of how flux turns a grilled design into sessions of work. Storage
and verbs are in `.flux/adr/`; this file is the glossary only.

## Language

**Task**:
The unit a single session executes and marks done with evidence. Held in the
task index, never in prose.
_Avoid_: ticket, item, step, phase (a phase is the retired one-file-per-session unit)

**Index**:
The append-only log of task events that flux replays to know what is open,
blocked, done, or waiting on a person.
_Avoid_: backlog, tracker, queue, DAG

**Tracer**:
A task that cuts a thin end-to-end slice and needs judgment. Runs in the parent
session on a frontier model and carries a full plan spec.
_Avoid_: design task, big task, spike

**Fill**:
A task that widens what a tracer proved, mechanical enough to run in a subagent
from a one-line intent specified at pickup.
_Avoid_: small task, trivial task, mechanical task, chore

**Tier**:
Whether a task is a tracer or a fill. A default the executor may raise to tracer,
never lower.
_Avoid_: routing, agent type, model

**Escalate**:
The act of raising a fill to tracer after a subagent hands it back unfinished.
_Avoid_: retry, bump, fail

**Awaiting-human**:
A task status meaning the work is done except for an observation only a person
can make. The steps travel with the task; the session ends there.
_Avoid_: blocked (blocked means waiting on another task), manual, paused

**Batch**:
The set of runnable fills a parent session dispatches to subagents in one
session, in dependency order, editing nothing itself.
_Avoid_: sprint, run, parallel job

**Parent**:
The interactive session that owns the index for its duration. Executes one
tracer itself, or dispatches one batch and gates it, never both.
_Avoid_: orchestrator, harness, controller
