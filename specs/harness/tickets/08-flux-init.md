---
id: FLX-08
title: /flux-init — idempotent per-project bootstrap
status: done
agent: build
effort: medium
blockers: [FLX-02, FLX-03, FLX-04]
checkpoint: none
---
Spec: specs/harness/spec.md (AC-13, user story 10).

## Context
User-invoked skill (`disable-model-invocation: true`). Behavior ships in the plugin; state is created by /flux-init; nothing is hand-copied. The skill is a checklist where every item is check-then-create — running it twice must change nothing (that IS the verify mode). Read mattpocock-skills `writing-for-agents` before authoring; completion criterion: "every checklist item reported as [exists] or [created] — none skipped."

## Tasks
1. Files: skills/flux-init/SKILL.md
   Action: checklist steps —
   (a) seed CONTEXT.md (empty Language section), docs/adr/, specs/, .flux/ + .gitignore entries
   (b) tooling: jq present? bd present? (`brew install beads` prompt if not) → `bd init` + `bd setup claude` if repo has none
   (c) merge `statusLine` into .claude/settings.json via jq (create file if absent, never clobber other keys)
   (d) append the flux section to CLAUDE.md (create if absent; skip if marker `<!-- flux -->` already present)
   (e) offer optional gitnexus indexing (optional pending license question — see spec Further notes)
   (f) existing codebase (has >20 source files, no CLAUDE.md map): dispatch an Explore scout to draft the CLAUDE.md architecture map + propose 5-10 glossary candidates from the code's own vocabulary, for user approval
   Verify: run on a throwaway repo twice — second run reports all [exists], zero writes
   Done: fresh repo gains the full harness; rerun is a no-op (AC-13)

## Test plan
Live: `mkdir /tmp/sandbox && git init` → /flux-init → verify tree + settings; run again → no-op; run on a repo that already has CLAUDE.md and CONTEXT.md → only missing pieces added.

## Boundaries
Never overwrite an existing CONTEXT.md, CLAUDE.md content outside the flux marker, or settings keys other than statusLine. No commits — report what was created and let the user commit.
