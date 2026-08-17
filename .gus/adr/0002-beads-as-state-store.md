# 0002 — beads (`bd`) as state store and ready-queue scheduler

Status: accepted

## Context
Fresh-session-per-stage requires external memory: ticket state, dependencies, decisions that
survive context clears. Scheduling must be deterministic (no LLM assigning work).

## Decision
Use beads: `bd ready --json` as the dependency-aware ready queue, `bd update/close/comment` as
per-stage state transitions, `discovered-from` deps for newly-found work. Pin a known-good version.

## Consequences
- Deterministic topological scheduling for free; git-backed JSONL merges cleanly.
- Alpha-stage churn risk: expect `bd doctor --fix`; the `br` Rust port (frozen classic
  SQLite+JSONL architecture) is the fallback if instability bites.
- Graph construction from a plan is human-supervised (agents produce unlinked/mis-ordered graphs).
- bd's store lives in `.beads/` (its default) — the one gus artifact not under `.gus/`; move it
  under `.gus/beads/` if bd gains a custom-path option.
