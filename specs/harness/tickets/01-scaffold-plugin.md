---
id: FLX-01
title: Scaffold plugin + self-hosted marketplace skeleton
status: done
agent: chore
effort: low
blockers: []
checkpoint: none
---
Spec: specs/harness/spec.md (Implementation decisions → Layout)

## Context
The flux repo is simultaneously a Claude Code plugin and its own marketplace. Fetch the current schemas from https://code.claude.com/docs/en/plugins and /plugin-marketplaces before writing JSON — do not write fields from memory.

## Tasks
1. Files: .claude-plugin/plugin.json
   Action: plugin manifest — name "flux", version 0.1.0, description, author; declare skills/agents/hooks/output-styles components per current docs schema.
   Verify: jq empty .claude-plugin/plugin.json
   Done: manifest parses and matches the documented schema (AC-14)
2. Files: .claude-plugin/marketplace.json
   Action: marketplace manifest listing the flux plugin with source "./" so the repo self-hosts.
   Verify: jq empty .claude-plugin/marketplace.json
   Done: `/plugin marketplace add <path-to-repo>` succeeds locally (AC-14)
3. Files: skills/.gitkeep, agents/.gitkeep, hooks/.gitkeep, bin/.gitkeep, output-styles/.gitkeep, tests/.gitkeep, .gitignore, README.md
   Action: create empty component dirs; .gitignore covers `.flux/` and OS noise; README = 10 lines (what flux is, install commands, pointer to spec and artifact).
   Verify: git status shows only intended files
   Done: repo tree matches the layout in the spec

## Test plan
Manual: `/plugin marketplace add` + `/plugin install flux@flux` from the local path succeeds (empty plugin is fine at this stage).

## Boundaries
Do not write any skill, agent, hook, or bin content — skeleton only. Do not touch specs/ or docs/.
