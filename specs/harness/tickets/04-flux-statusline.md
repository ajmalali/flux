---
id: FLX-04
title: flux-statusline — always-visible state line
status: done
agent: build
effort: medium
blockers: [FLX-03]
checkpoint: none
---
Spec: specs/harness/spec.md (AC-4).

## Context
The statusline command receives rich JSON on stdin (model, workspace, git/worktree info, context-window usage) and prints one line. Fetch the current input schema from https://code.claude.com/docs/en/statusline — field names must come from docs, not memory. Output format, exactly:

`FLX-03 · flux · claimed · ctx 41%`  → `<ticket> · <worktree-or-repo name> · <ticket status> · ctx <N>%`
No ticket claimed → `— · flux · idle · ctx 41%`

Ticket comes from `.flux/session.json` (written by heartbeat, FLX-03 — hence the blocker); context % and worktree name from the stdin JSON.

## Tasks
1. Files: bin/flux-statusline
   Action: bash + jq, <100ms (statusline runs often — no git subprocesses; everything from stdin JSON + one session.json read). Missing session.json, absent fields, malformed stdin → still print a valid line, exit 0.
   Verify: tests/run.sh statusline
   Done: fixtures produce the exact expected strings, including the no-ticket and no-.flux cases (AC-4, AC-5)
2. Files: README.md
   Action: add the one-line `statusLine` settings snippet users need (flux-init will automate it later; documented now for the FLX-05 checkpoint).
   Verify: snippet is valid JSON when inserted into a settings.json
   Done: copy-pasteable

## Test plan
Fixtures: claimed / idle / missing session.json / context field absent. Assert output is always exactly one line.

## Boundaries
Read-only: statusline writes nothing. Do not compute drift or frontier here — that's prime's job; statusline must stay <100ms.
