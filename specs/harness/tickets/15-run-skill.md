---
id: FLX-15
title: /run — frontier orchestrator over worktree-isolated agents
status: open
agent: deep
effort: high
blockers: [FLX-11, FLX-05]
checkpoint: none
---
Spec: specs/harness/spec.md (AC-12, user story 6, Out of scope: no auto-retry).

## Context
Built LAST, deliberately: manual mode must feel right first, and native agent teams may absorb parts of this — check https://code.claude.com/docs/en/agent-teams for current state before building; prefer native primitives over custom machinery wherever they now reach. A while-loop over the frontier, not a swarm.

## Tasks
1. Files: skills/run/SKILL.md
   Action: flow — (a) frontier from `bd ready` (or the markdown fallback); (b) for each ready ticket up to 3 concurrent: dispatch its routed agent (ticket's `agent:` field → agents/{chore,build,deep}.md) with worktree isolation, the agent following /build's own flow (claim → implement → qualify → close); (c) `checkpoint: human-verify` tickets are never dispatched — the loop stops and presents PAUL's checkpoint format: what was built / how to verify / how to resume; (d) a ticket failing its qualify escalation is tagged with the classification (intent/spec/code) and returned to the frontier as blocked-on-human — no retry; (e) after each completion, recompute the frontier (newly unblocked tickets enter); (f) end when frontier is empty or all remaining tickets are checkpoints/blocked → print a run report table: ticket / agent / result / commit. Completion criterion: "report table row for every ticket the run touched."
   Verify: live-run on 3+ remaining flux tickets with a deliberate checkpoint among them
   Done: parallel worktree execution, checkpoint stop, failure tagging, report — all observed (AC-12)

## Test plan
The live run in Verify, watched via the native agent view. Edge: two tickets touching the same file → worktree isolation prevents the collision; merge order surfaced to the human.

## Boundaries
Concurrency cap 3 is hard in v0.1. /run never merges to main — every branch lands via human diff review. No retry logic (spec: out of scope).
