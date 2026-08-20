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
  **Re-examined 2026-08-18 (T4c) and upheld: gitnexus does not supersede this.** Measured on
  three tickets against a real 88-file repo, gitnexus's symbol/flow pack section did not reduce
  `exploratory_calls` relative to the ranked file list (23 vs 19 in total) and cost more wall
  time and output tokens. Neither map beat carrying no map at all, and between-ticket variance
  exceeded any between-variant difference — so the swap is refused for lack of evidence, not
  decided against on principle. Memo: `plans/flux-harness/gitnexus-memo.md`. Whether the
  `[repo_map]` pack section earns its place at all is now an open A/B question for M1.
- **Structural gate (added by T4c):** `gitnexus check --cycles --json -r .` is a validated
  **opt-in** `[[gates]]` entry — exit-status-shaped, no new flux code. Deliberately not in
  `flux init`'s defaults: it answers about the indexed commit, and flux does not manage a
  gitnexus index.
- **Review input (settled by T4c, binding on T5):** the review stage hydrates from the `git diff`
  of the stage commits, as the design.md stage I/O table says. `gitnexus detect-changes` may
  append an execution-flow overlay *alongside* the diff, never instead of it: its symbol
  attribution slips on short symbols, and it has no JSON output.
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
