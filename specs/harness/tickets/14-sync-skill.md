---
id: FLX-14
title: /sync — reconcile off-harness work
status: open
agent: build
effort: medium
blockers: [FLX-02, FLX-03]
checkpoint: none
---
Spec: specs/harness/spec.md (AC-11, user story 9). ADR-0001 (detection is hook-work; repair is skill-work).

## Context
User-invoked, prompted by prime's drift line. Detection already exists (prime compares `last_synced_commit` from session.json against git log, FLX-02/03); this skill is only the repair. Lazy by design — never blocks, never nags beyond prime's one line.

## Tasks
1. Files: skills/sync/SKILL.md
   Action: flow — (a) list commits since `last_synced_commit` whose messages match no ticket id; (b) for each cluster of related commits (group by files touched), use gitnexus `detect_changes`/`impact` when available (plain diff reading otherwise) to summarize what changed; (c) create retroactive tickets, already closed, linking the commit shas — history stays queryable, zero ceremony; (d) check the combined changes against docs/architecture.md, docs/adr/, and CONTEXT.md: update architecture.md for structural changes, flag (never silently rewrite) contradictions with an ADR or glossary term; (e) update `last_synced_commit` in .flux/session.json — the only writer of that field besides initialization. Completion criterion: "every unattributed commit accounted for in a retroactive ticket — print the commit→ticket table."
   Verify: make two raw commits, run /sync
   Done: retroactive closed tickets exist, drift line gone next session, contradiction check ran (AC-11)

## Test plan
Live: raw commits touching (a) a leaf file and (b) something architecture.md describes — the second must trigger a doc update or flag. Edge: zero drift → /sync says so and exits without writes.

## Boundaries
Retroactive tickets are always created closed — /sync never reopens work or judges the raw changes. Contradictions with ADRs are flagged for the human, never auto-resolved.
