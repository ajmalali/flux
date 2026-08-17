# 0003 — Fresh session per stage; context packs are the interface

Status: accepted

## Context
Context rot is measurable well before the window fills (significant degradation from ~50K tokens
across 18 frontier models, Chroma 2025); lost-in-the-middle penalizes accumulated history.

## Decision
Every pipeline stage runs in a fresh SDK session hydrated from a compact context pack
(repo-map slice + ticket brief + governing ADRs + plan summary), never from prior-session history.
The plan/ADR summary is re-injected at every stage (plan reminders measurably reduce plan drift,
arXiv 2604.12147).

## Consequences
- Handoff artifacts must be complete: what isn't in the pack doesn't exist for the stage.
- Fixed per-stage prompt cost; for tiny tickets, allow merging test+implement stages
  (complexity-conditional split, see plan §M7).

## Alternatives
One long session per ticket: loses the context-hygiene benefit; rejected.
