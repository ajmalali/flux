---
id: FLX-10
title: /tickets — spec to routed tickets, fresh window only
status: open
agent: deep
effort: medium
blockers: [FLX-09, FLX-06]
checkpoint: none
---
Spec: specs/harness/spec.md (AC-7, user story 4). ADR-0002, ADR-0003.

## Context
User-invoked. The polluted-window guard is the whole point (ADR-0003): if the session already carries substantial context (heuristic: any prior implementation or long discussion visible in this window), refuse with "run /clear first, then /tickets <spec-path>". Ticket bodies follow the exact format of specs/harness/tickets/ — these files are the living example.

## Tasks
1. Files: skills/tickets/SKILL.md
   Action: flow — (a) guard, then read ONLY the named spec + CONTEXT.md; (b) decompose into tracer-bullet vertical slices, each sized for a single fresh context window; (c) score each ticket's complexity 1-10 → route: ≤3 chore, 4-7 build, ≥8 deep; mark checkpoint: human-verify where only human eyes can judge; (d) declare blockers; quiz the user on granularity and edge cases before writing anything (Matt's to-tickets discipline); (e) create via bd (create + dep add) when available, else numbered markdown files in specs/<slug>/tickets/. Completion criterion: "every user story in the spec is covered by ≥1 ticket, and every ticket names its AC — list the mapping."
   Verify: live-run against a spec produced by /plan
   Done: tickets carry routing, F/A/V/D tasks, test plan, boundaries, blockers; story→ticket mapping printed (AC-7)
2. Files: skills/tickets/ticket-template.md
   Action: the frontmatter + body template (id/title/status/agent/effort/blockers/checkpoint; Context/Tasks/Test plan/Boundaries), with the F/A/V/D rule: "if you can't specify Files + Action + Verify + Done, the task is too vague — split or ask."
   Verify: generated tickets match it
   Done: template exists and is referenced, not duplicated, by SKILL.md

## Test plan
Live dogfood (task 1). Also verify the guard: invoke /tickets in this same planning-heavy session → it must refuse.

## Boundaries
/tickets writes tickets and nothing else — no code, no spec edits (spec gaps go back as questions). Never invent scope absent from the spec.
