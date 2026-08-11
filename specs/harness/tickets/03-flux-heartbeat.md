---
id: FLX-03
title: flux-heartbeat — Stop-hook state stamp
status: open
agent: build
effort: medium
blockers: [FLX-01]
checkpoint: none
---
Spec: specs/harness/spec.md (AC-3, AC-5). ADR-0001.

## Context
The Stop hook fires once at the end of every turn, regardless of whether any skill ran — this is what keeps state fresh when the user works "raw". Exit 0 always; exit 2 would force the model to continue, which heartbeat must never do. Check the current Stop event schema at https://code.claude.com/docs/en/hooks.

`.flux/session.json` shape (create dir/file if missing):
```json
{
  "last_turn_at": "<ISO8601>",
  "branch": "<git branch>",
  "head_sha": "<short sha>",
  "dirty_files": <count>,
  "claimed_ticket": "<id or null>",
  "last_synced_commit": "<sha, preserved — only /sync updates it>"
}
```
`claimed_ticket` resolution: `bd` if present, else the frontmatter scan (same logic as prime — extract to bin/flux-common sourced by both).

## Tasks
1. Files: bin/flux-heartbeat, bin/flux-common
   Action: write session.json atomically (temp file + mv); preserve `last_synced_commit` if present, initialize to current HEAD on first run. Extract shared ticket-resolution into flux-common; refactor flux-prime to source it. All failures exit 0. <500ms.
   Verify: tests/run.sh heartbeat
   Done: two consecutive runs produce valid JSON, preserve last_synced_commit, never exit non-zero (AC-3, AC-5)
2. Files: hooks/hooks.json
   Action: add Stop entry alongside the existing SessionStart entry.
   Verify: jq empty hooks/hooks.json
   Done: both hooks registered without clobbering each other

## Test plan
Fixtures: first run (no .flux), normal run, dirty tree, detached HEAD, malformed stdin. Assert atomicity: no partial JSON after a killed run.

## Boundaries
Heartbeat writes ONLY .flux/session.json — never tickets, never durable docs. Do not add bd write calls (notes/stamps to beads are a later nicety, not this ticket).
