---
id: FLX-02
title: flux-prime — SessionStart state injection
status: open
agent: build
effort: medium
blockers: [FLX-01]
checkpoint: none
---
Spec: specs/harness/spec.md (AC-1, AC-2, AC-5). ADR-0001 (fail-open), ADR-0002 (bd behind verbs).

## Context
SessionStart hook stdout (exit 0) is injected into the model's context. It fires on startup, resume, clear, and after compaction — matcher `startup|resume|clear|compact`. Input arrives as JSON on stdin. Fetch the current event schema from https://code.claude.com/docs/en/hooks first; field names change.

Prime's output is the "where am I" block, in this order, each section omitted when empty:
1. Claimed ticket for THIS worktree (from `bd` if installed; else scan `specs/*/tickets/*.md` frontmatter for `status: claimed`).
2. Frontier: up to 5 ready tickets (`bd ready`; fallback: open tickets whose blockers are all `status: done`).
3. Unconsumed handoffs in `.flux/handoffs/` (filename + first line).
4. Drift line: commits since `.flux/session.json`'s `last_synced_commit` whose messages contain no ticket id (`FLX-\d+|bd-[a-z0-9]+`) → "N commits not linked to tickets — run /sync when convenient."
Target: whole block under ~30 lines, plain text.

## Tasks
1. Files: bin/flux-prime
   Action: bash + jq script implementing the above. Every failure path (no git repo, no jq, no bd, malformed stdin, missing .flux) exits 0, printing whatever sections it could compute. Wall time <500ms — no network, no `bd` calls that sync.
   Verify: tests/run.sh prime
   Done: fixture repo produces the expected block; malformed stdin exits 0 silently (AC-1, AC-5)
2. Files: hooks/hooks.json
   Action: SessionStart entry, matcher `startup|resume|clear|compact`, command `${CLAUDE_PLUGIN_ROOT}/bin/flux-prime`.
   Verify: jq empty hooks/hooks.json
   Done: hook fires on all four sources (AC-2)
3. Files: tests/run.sh, tests/fixtures/prime/*
   Action: create the bash test runner (first ticket to need it): pipes fixture stdin JSON, asserts on stdout, runs shellcheck on bin/*.
   Verify: bash tests/run.sh
   Done: runner exists, prime cases + shellcheck pass (AC-14)

## Test plan
Fixtures: claimed ticket present / nothing claimed / handoff pending / drift present / malformed JSON / bd absent. Live check happens in FLX-05.

## Boundaries
Do not implement heartbeat or statusline here. Do not write to any file — prime is read-only (heartbeat owns writes).
