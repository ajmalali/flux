# 0009 — Knowledge layer is bought, not built

Status: accepted (amends 0004)

## Context
The custom knowledge layer (module cards + LLM gardener) was the riskiest subsystem in the
original plan — silent staleness is its failure mode. As of Aug 2026, maintained tools cover it:
RepoWiki `map` (ranked repo map, zero LLM calls, prompt-ready JSON), OpenWiki (agent-written
in-repo Markdown wiki with scheduled incremental diff-based updates), and deepwiki-by-cc
(self-hosted, claim verification against code actually read, sync regenerates only pages whose
source files the diff touched).

## Decision
- Repo map: adopt `repowiki map` or Aider RepoMapper (whichever ranks better on the target
  repo); post-merge hook regeneration. No custom extractor.
  **Resolved 2026-08-18 (T4b): `repowiki map`.** RepoMapper's PageRank only runs when
  `--chat-files` is supplied — every file otherwise ranks 1.0 — and its HEAD does not execute on
  any tree-sitter version. Bake-off in `plans/flux-harness/repo-map-memo.md`. The tool is invoked
  as a configured command (`[repo_map] command`), not taken as a flux dependency.
- Wiki: timeboxed spike (1 day) of OpenWiki vs deepwiki-by-cc; selection criteria: Markdown
  in-repo, incremental sync works on real diffs, acceptable sync cost, pages sliceable into
  hydration packs.
- Kept custom: ADR log (markdown + convention), interface catalog (deterministic extraction),
  exploration-call KPI hook (harness-side by nature).
- Unchanged from 0004: verification reads stay mandatory; drift gate before plan finalization;
  load-bearing pages get human review on regeneration (leaf pages auto-sync).

## Consequences
- No custom knowledge-layer code exists before Phase 2 (M2); the execution pipeline ships first.
- Tool-adoption risk is bounded by timeboxed spikes with written memos, never direct dependency.
