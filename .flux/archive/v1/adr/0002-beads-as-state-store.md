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
- *(Amended 2026-08-17, v2.1 landscape update)* beads v1.0.0 shipped April 2026; pin the 1.x
  minor. The earlier `br` Rust-port fallback is dropped. Assess 1.0 "molecules" (deterministic
  step workflows with a full ledger) as a possible native container for the 5-stage pipeline —
  feeds the Gas City substrate evaluation.
- Graph construction from a plan is human-supervised (agents produce unlinked/mis-ordered graphs).
- bd's store lives in `.beads/` (its default) — the one flux artifact not under `.flux/`; move it
  under `.flux/beads/` if bd gains a custom-path option.
