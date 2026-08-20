# 0004 — Two-tier knowledge layer; verification reads stay mandatory

Status: accepted — amended by 0009 (the layer is bought, not built; the noise-vs-verification
principle here is unchanged)

## Context
Goal is to eliminate tool-call *noise* from interactive research/planning sessions — not to
eliminate codebase reading. Stale pre-computed context is "confidently wrong": DOCER found genuine
referential rot in a large fraction of repos with doc-code references (arXiv 2606.09090).

## Decision
- Layer 1 (deterministic, ~free): tree-sitter+PageRank repo map, symbol index, per-file
  content-hash manifest for freshness; regenerated via git post-commit hook.
- Layer 2 (LLM-maintained, cheap tier): architecture docs, small factual CLAUDE.md.
- A **drift gate**: any load-bearing claim in a plan referencing a file whose hash is stale vs.
  HEAD forces a live verification read before the plan can finalize.
- Exploration in interactive sessions goes through read-only Explore subagents (Haiku, low
  effort); only distilled summaries return to the parent context.

## Consequences
- Plans start warm (pre-computed context packs) but never trust the knowledge layer alone.
- If Layer 2 maintenance cost exceeds retrieval savings, cut Layer 2 to on-demand; Layer 1 stays.
