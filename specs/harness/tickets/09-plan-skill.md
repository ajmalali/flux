---
id: FLX-09
title: /plan — interview to approved spec, inside the smart zone
status: open
agent: deep
effort: high
blockers: [FLX-01, FLX-24]
checkpoint: none
---
Spec: specs/harness/spec.md (AC-6, user story 3). ADR-0003.

## Context
User-invoked. Composes the skills this plugin vendors (ADR-0009) by reference: invoke `flux:grilling` for the interview discipline (design tree, frontier of questions, recommended answers, sub-agents fetch facts) and `flux:domain-modeling` for glossary/ADR upkeep — do NOT restate their content. Facts about the codebase come from gitnexus queries or Explore scouts returning summaries; raw file contents stay out of the window. Read `writing-for-agents` before authoring.

## Tasks
1. Files: skills/plan/SKILL.md
   Action: flow — (a) accept an idea, a bead id, or an ADR pointer as input; (b) grill to an empty question-frontier, domain-modeling active throughout; (c) prototype detours permitted via the vendored `flux:prototype` skill (throwaway branch + pointer back); (d) close every round by writing what it settled into specs/<slug>/spec-draft.md under its template heading, and promote that draft to specs/<slug>/spec.md when the frontier empties — composition never happens in one push at the end; (e) present for approval. Budget rule, on the statusline's absolute token count rather than a share of the window: notice at 200k, notice again at 350k, both advisory — report the count, recommend, and carry on unless the user says stop. A context-pressure notice is not advisory and pauses at the next round boundary, which keeps the run safe on a window smaller than either mark. Pausing costs a flush of the round in progress plus a residue handoff, because the draft is already written. Completion criterion: "spec approved and saved, or draft + handoff written — no third ending."
   Verify: live-run on a real small feature idea for a zaps repo
   Done: draft current at each round boundary; one notice at 200k and one at 350k, neither stopping the run on its own; ends with an approved spec or a user-called pause (AC-6)
2. Files: skills/plan/spec-template.md
   Action: the template from this repo's own spec: Problem statement / Solution / User stories (numbered) / Implementation decisions / Testing decisions / Acceptance criteria (AC-n) / Out of scope / Further notes. Rule embedded: no file paths in specs — they go stale; prototype-branch pointers allowed.
   Verify: template used by the live run
   Done: generated spec has all sections

## Test plan
Live dogfood run (task 1's verify). Confirm CONTEXT.md gained/updated at least one term during the run.

## Boundaries
/plan never creates tickets (ADR-0003) and never writes code outside a prototype branch. Do not duplicate grilling/domain-modeling instructions into this skill — invoke them.
