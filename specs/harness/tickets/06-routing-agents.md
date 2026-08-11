---
id: FLX-06
title: Routing agents — chore, build, deep
status: done
agent: chore
effort: low
blockers: [FLX-01]
checkpoint: none
---
Spec: specs/harness/spec.md (Implementation decisions → routing by complexity).

## Context
Three subagent definitions with model/effort frontmatter — this is the per-ticket model-routing mechanism. Check current frontmatter fields (model, effort, tools, disable-model-invocation, isolation) at https://code.claude.com/docs/en/sub-agents before writing.

## Tasks
1. Files: agents/chore.md
   Action: model haiku, effort low, disable-model-invocation true. Body: "mechanical work with an executable verify command as the whole safety net" — renames, config, codemods, scaffolds, doc sync. Includes the condensed Qualify rule: run the verify command fresh, read its output, never claim from memory.
   Verify: frontmatter fields match documented schema
   Done: agent invocable via the Agent tool with haiku
2. Files: agents/build.md
   Action: model sonnet, effort medium, disable-model-invocation true. Body: standard tickets — clear spec, agreed seams, existing patterns. Full Execute→Qualify loop (from /build's description in the spec) + 3-strikes escalation with intent/spec/code classification.
   Verify: same
   Done: same, with sonnet
3. Files: agents/deep.md
   Action: model opus, effort high, disable-model-invocation true. Body: novel design inside the ticket, cross-cutting changes, gnarly diagnosis. Same loop; additionally instructed to record any real tradeoff as an ADR draft.
   Verify: same
   Done: same, with opus

## Result — 2026-08-11
Written as agents/{chore,build,deep}.md with `name`/`description`/`model`/`effort` and
nothing else. The `disable-model-invocation: true` these tasks asked for does not exist
for subagents — it is a skills-and-commands field — so the descriptions carry that intent
instead (ADR-0008, which also records why `claude plugin validate .` at the repo root
would not have caught a broken agent file, and the colon-in-description YAML trap it did
catch). Bodies are 18/22/26 lines. Verified: `claude plugin validate
.claude-plugin/plugin.json` passes with only the pre-existing root-CLAUDE.md warning;
`bash tests/run.sh` 45 passed, 0 failed. After `/reload-plugins` the three loaded as
`flux:chore` / `flux:build` / `flux:deep` with descriptions intact, and a trivial dispatch
of each returned Haiku 4.5, Claude Sonnet 5 and Opus 5 respectively — the `model:` field
routes. Effort is not self-reportable and was not confirmed this way; the frontmatter
carries it and the schema is documented.

## Test plan
Manual: dispatch each agent with a trivial prompt; confirm the model tier in the transcript.

## Boundaries
Keep each body under ~30 lines — agents inherit the ticket's context; they need discipline, not knowledge. No tools restrictions in v0.1.
