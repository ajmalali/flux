---
id: FLX-06
title: Routing agents — chore, build, deep
status: open
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

## Test plan
Manual: dispatch each agent with a trivial prompt; confirm the model tier in the transcript.

## Boundaries
Keep each body under ~30 lines — agents inherit the ticket's context; they need discipline, not knowledge. No tools restrictions in v0.1.
