---
id: FLX-07
title: Output style — plain language, keep coding instructions
status: open
agent: build
effort: low
blockers: [FLX-01]
checkpoint: none
---
Spec: specs/harness/spec.md (Solution → output style). Research: output styles modify the system prompt directly — stronger than CLAUDE.md rules.

## Context
Check current format at https://code.claude.com/docs/en/output-styles. Frontmatter needs `name`, `description`, and `keep-coding-instructions: true` (default is false and would strip SWE behavior).

## Tasks
1. Files: output-styles/flux.md
   Action: communication rules, phrased positively (never as prohibitions — negation drags the forbidden pattern into context):
   - Lead every response with the outcome in one sentence.
   - Complete sentences; technical terms spelled out; glossary terms from CONTEXT.md when the repo has one.
   - At most five sentences before any list or code block.
   - Summaries describe user-visible behavior, then mechanism.
   - When reporting completed work: what changed, how it was verified, what remains.
   Verify: style selectable via /config → Output style after plugin install
   Done: a test session in the style produces answers matching the rules

## Test plan
Manual A/B: same question with and without the style; confirm coding ability intact (keep-coding-instructions worked).

## Boundaries
Style covers voice and format only — no workflow instructions (those live in skills), no project facts (those live in CLAUDE.md).
