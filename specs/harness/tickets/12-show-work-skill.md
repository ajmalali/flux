---
id: FLX-12
title: /show-work — diff-scoped behavior diagram artifact
status: open
agent: build
effort: medium
blockers: [FLX-01]
checkpoint: none
---
Spec: specs/harness/spec.md (AC-9, user story 7).

## Context
User-invoked, takes a ticket id or defaults to the current branch vs merge-base. Claude Code artifacts render mermaid natively (```mermaid in markdown, `<pre class="mermaid">` in HTML) — no infrastructure. The skill is a prompt template with hard conventions; its value is the constraints.

## Tasks
1. Files: skills/show-work/SKILL.md
   Action: flow — (a) `git diff $(git merge-base <base> HEAD)...HEAD` + the ticket's AC list; (b) choose diagram type by change shape: sequenceDiagram for request/event paths (API work, bug fixes on a flow), flowchart for logic/state changes, erDiagram for schema; (c) hard rules: ≤12 nodes, only changed behavior, NEW vs CHANGED edges styled distinctly, untouched context nodes greyed, node labels use CONTEXT.md vocabulary; (d) artifact contains: the one diagram, a ≤5-sentence plain-English "what changed and why", the AC checklist with the verify command that proved each; (e) publish as an artifact, print the link. Completion criterion: "every AC in the ticket appears in the checklist as pass/fail with its evidence command."
   Verify: live-run against a completed flux ticket's branch
   Done: artifact matches all hard rules for a backend-ish and a config-ish diff (AC-9)

## Test plan
Two live runs with different change shapes (one produces a sequenceDiagram, one a flowchart) to prove the type-selection rule.

## Boundaries
Diagram the diff, never the whole system. If the diff exceeds what 12 nodes can honestly show, emit two smaller diagrams rather than one dense one.
