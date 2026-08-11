---
id: FLX-13
title: /pause — deposit settled knowledge, write thin handoff
status: open
agent: build
effort: low
blockers: [FLX-02]
checkpoint: none
---
Spec: specs/harness/spec.md (AC-10, user story 8).

## Context
User-invoked (also invoked by /plan's budget rule). Two steps in strict order — deposit first, residue second. The handoff must stay thin because everything fat already has a durable home; a handoff that restates a spec section is a bug. flux-prime (FLX-02) already surfaces `.flux/handoffs/*` — this skill only produces the files.

## Tasks
1. Files: skills/pause/SKILL.md, skills/pause/handoff-template.md
   Action: flow — (a) deposit: new glossary terms → CONTEXT.md; decisions meeting the ADR bar (hard to reverse / surprising / real tradeoff) → docs/adr/; agreed spec sections → specs/<slug>/spec-draft.md; (b) residue: write .flux/handoffs/<branch>-<slug>.md from the template — Open questions / Current hypothesis / Next action / Deposited (paths list); (c) tell the user: "paused — /clear or close the terminal; next session will surface this." Completion criterion: "the handoff contains zero facts absent from the Deposited paths — only questions, hypothesis, next action."
   Verify: live pause of a real discussion, then a fresh session
   Done: prime surfaces the handoff; resuming from it recovers the discussion without re-asking settled questions (AC-10)
2. Files: skills/plan/SKILL.md
   Action: replace /plan's inline pause description with an invocation of this skill (single source of truth).
   Verify: /plan at budget invokes /pause
   Done: no duplicated pause instructions anywhere

## Test plan
The live pause/resume cycle in task 1's Verify. Edge: pausing with nothing settled yet (deposit step is a no-op, handoff still valid).

## Boundaries
Handoffs are per-worktree files, gitignored, consumed (archived to .flux/handoffs/done/) on resume. Never write a handoff to the OS temp dir or the repo root.
