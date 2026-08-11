---
id: FLX-11
title: /build — claim, implement, qualify, close
status: open
agent: deep
effort: medium
blockers: [FLX-10, FLX-06]
checkpoint: none
---
Spec: specs/harness/spec.md (AC-8, user story 5). ADR-0001, ADR-0002.

## Context
User-invoked, takes a ticket id. The four store verbs appear here: claim on start, close on finish (bd when present; else flip the frontmatter `status:` in place). Minimal context load is a hard rule: the ticket, the spec section it names, CONTEXT.md, gitnexus `context` on symbols the ticket names — and nothing else until a task demands it.

## Tasks
1. Files: skills/build/SKILL.md
   Action: flow — (a) claim atomically (`bd update --claim`; markdown fallback: check status is open, set claimed+worktree in one edit); refuse if already claimed elsewhere; (b) load minimal context; (c) implement task-by-task via the installed `/tdd` skill at the seams the ticket pre-agreed; (d) Qualify after every task: re-read actual output, run the Verify command fresh and read its output, compare against the task's Done and the AC it names — never claim from memory; (e) three failed qualify cycles on one task → stop, classify (intent → back to /plan; spec → fix ticket/AC first; code → targeted fix), escalate to the user with the classification; (f) close: commit message references the ticket id, mark done, check the diff against docs/architecture.md and ADRs — update or flag; offer /show-work. Completion criterion: "every task's Verify command run fresh in this session with output shown — list them."
   Verify: live-run FLX-07 (output style) via /build itself
   Done: dogfood run claims, implements, qualifies, closes with a linked commit (AC-8)

## Test plan
The dogfood run in Verify — /build building a flux ticket is the integration test. Also verify double-claim refusal from a second terminal.

## Boundaries
Respect the ticket's own Boundaries section absolutely — on conflict, stop and escalate (boundary violations are never rationalized). No scope beyond the ticket; discoveries become new tickets (`discovered-from`), not detours.
