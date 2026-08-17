# Harness Design — Consolidated Change Document (v2 → v2.1)

Delta against `claude-code-harness-full-system-design.md` (v2), incorporating (a) the Aug 2026 tooling-landscape findings and (b) the critical review. Each change is written ticket-ready: rationale, action, acceptance criteria, dependencies, priority. Suggested epic structure at the end maps directly to `bd create`.

Priorities: **P0** = do before/during Phase 0 · **P1** = fold into existing phase · **P2** = opportunistic / re-evaluate later.

---

## A. Strategic changes (from the critical review)

### A1. Add a ground-truth A/B evaluation baseline — P0
- **Rationale**: v2 measures the harness against itself (tokens, gates, exploration calls) but never against the alternative. Claude Code absorbs harness features quarterly (native workflows, built-in worktree isolation, subagent patterns); without a baseline you can't detect the day the harness becomes net overhead. Biggest gap in v2.
- **Change**: Every N tickets (start: 1 in 10), run a comparable ticket through **vanilla Claude Code** (interactive or plain `claude -p`, no harness) and record: total cost, wall-clock time, gate-suite pass on first submission, defects found in review. Maintain a running comparison table in the metrics store.
- **Acceptance**: Comparison table exists with ≥3 baseline runs by end of Phase 1; harness-vs-vanilla delta is reviewed at every phase gate; a standing kill-criterion is written down ("if vanilla wins on cost AND quality for 3 consecutive samples, freeze harness feature work and investigate").
- **Depends on**: A2 (metrics store).

### A2. Metrics store as a first-class Phase 0 deliverable — P0
- **Rationale**: Every kill-switch in v2 §9 depends on data; in v2 the metrics were implied, not built. Move them from "track" to "deliverable."
- **Change**: SQLite (or flat JSONL) metrics store written by the Stage runner: per (ticket, stage) → tokens in/out, cache read/write tokens, `total_cost_usd`, wall time, gate results, retry counts, exploratory-call count, model/effort used. One `just metrics` report command.
- **Acceptance**: After any pipeline run, one command prints per-stage cost/time and the KPI dashboard from v2 §9.

### A3. "Meaner v1" scope cut — build order changes — P0
- **Rationale**: The harness is a second product for a team of one; payback requires ruthless sequencing. Knowledge layer and routing are the most speculative components; execution pipeline is the proven one.
- **Change**: Re-sequence: Phase 0–1 (execution pipeline + hardening + metrics + A/B) ship **before any knowledge-layer work beyond a repo map**. Knowledge layer enters only as buy-not-build (see C1). Model/effort routing deferred to Phase 3 and only if metrics show model spend is the dominant cost.
- **Acceptance**: Phase plan updated; no knowledge-layer custom code exists before Phase 2; each phase gate requires its advance-metric met before new scope opens.

### A4. Thinness principle made explicit — executor behind an interface — P0
- **Rationale**: Obsolescence defense. Parts of the Stage runner may be absorbed by Claude Code natively; durable value = beads graph, knowledge artifacts, ticket-sizing discipline, gate suite.
- **Change**: Stage runner calls Claude through a single `Executor` interface (`run(prompt_pack, config) -> result`). Claude Agent SDK is the first implementation. No stage code imports the SDK directly.
- **Acceptance**: Swapping the executor (e.g., to native workflows, Gas City, or another CLI agent) touches one module.

---

## B. Execution-layer changes (from landscape findings)

### B1. Timeboxed substrate evaluation: Archon and Gas City vs custom — P0 (half-day each, hard timebox)
- **Rationale**: Two credible substrates now exist. Archon = YAML-defined deterministic DAG workflows around Claude Code/Codex with context passing, logging, dashboard, loop nodes. Gas City = SDK extracting Gas Town's orchestration primitives (beads "molecules" = deterministic step workflows with a full ledger). Default hypothesis remains **custom Python wins** because the pipeline is dynamic exactly where YAML DSLs are weak (per-ticket model config, conditional stage skipping, bounded loops keyed on beads state, gate-driven transitions) — but this is docs-based, not hands-on; spend the half-day per tool to confirm or refute.
- **Change**: Spike each: implement Stage 1 + Stage 2 with a gate between them. Score: can it (1) read per-ticket config from beads, (2) skip a stage conditionally, (3) run a bounded fix loop, (4) surface per-stage cost? Regardless of outcome, **steal Archon's run-logging/dashboard model** for A2.
- **Acceptance**: Written decision memo (keep custom / adopt X) with the 4-point scorecard; decision is revisited only at phase gates, not continuously.
- **Depends on**: nothing; do first.

### B2. Beads v1.0 upgrade — soften the alpha caveats — P0
- **Rationale**: Beads and Gas Town shipped v1.0.0 (April 2026); beads at ~26k stars. The v2 caveats ("architecture in motion, consider the `br` Rust port") are now stale. Molecules + ledger also confirm the beads-as-orchestration-state pattern at scale.
- **Change**: Adopt beads ≥1.0; drop the `br` fallback from the plan; pin the 1.x minor version; re-read the 1.0 docs for molecules — if molecules can express the 5-stage pipeline natively, that strengthens the Gas City option in B1.
- **Acceptance**: Beads 1.x pinned in setup script; B1 memo includes a molecules assessment.

### B3. Evaluate Claude Code native workflows for intra-stage fan-out — P1 (Phase 1)
- **Rationale**: Anthropic's workflow engine now does deterministic orchestration, parallel/pipeline primitives, journaling/resume, and passes only necessary data to downstream nodes — plus six named patterns (incl. adversarial verification, generate-and-filter, loop-until-done). This doesn't replace the persistent ticket pipeline, but it can replace hand-rolled fan-out *inside* a stage (e.g., Stage 3 adversarial verify with perspective-diverse reviewers; parallel gate runs).
- **Change**: Prototype Stage 3 as a native workflow (adversarial-verify pattern: N reviewers with distinct lenses — correctness, security, design-fit vs plan/ADRs — majority-survive). Compare vs single different-model reviewer on cost + catch rate.
- **Acceptance**: One review-stage bake-off with metrics; keep the cheaper config that catches ≥ as many planted defects.

### B4. Context-pack handoff hygiene — reference, don't paste — P2
- **Rationale**: waggle-style attributed artifact references (a ~30-byte token a consumer resolves into only the slice it needs under a byte budget) is the right *pattern* for stage handoffs even if the tool itself isn't adopted: it prevents context packs from bloating as they accumulate stages.
- **Change**: Handoff artifacts are stored on disk keyed by ticket and **referenced by path + section** in prompts; the hydration step resolves references into content within the token budget, rather than stages appending full artifacts to a growing pack.
- **Acceptance**: Stage 4's prompt contains resolved slices of review.md + diff, not the concatenation of all prior stage artifacts; measured pack size does not grow monotonically across stages.

---

## C. Knowledge-layer changes: buy, don't build

### C1. Replace custom module cards + gardener with OpenWiki or deepwiki-by-cc — P1 (Phase 2)
- **Rationale**: The riskiest custom subsystem in v2 (silent-staleness failure mode) now exists in maintained form. OpenWiki: agent-written Markdown wiki you own, built for agents to read as memory, with a scheduled GitHub Action that diffs commits since last run and updates only relevant pages. deepwiki-by-cc: self-hosted, agentic page generation with claim verification against code actually read, and a sync mode regenerating only pages whose source files were touched by the diff — i.e., the hash-invalidation design, shipped.
- **Change**: Spike both on the target repo (1 day total). Selection criteria: (1) output is plain Markdown in-repo (owned, reviewable), (2) incremental sync actually works on your diff patterns, (3) cost per sync is acceptable on a local/cheap model, (4) pages can be sliced into hydration packs. Keep from v2 custom-built only: **ADR log** (it's just markdown + convention), **interface catalog** (deterministic extraction), and the **exploration-call KPI hook** (that's harness-side).
- **Acceptance**: Wiki generated for the target repo; one synthetic merge triggers a correct incremental update; hydration pre-flight assembles packs from wiki pages + ADRs + repo map within budget.
- **Depends on**: C2.

### C2. Repo map via RepoWiki `map` (zero-LLM) or Aider RepoMapper — P1 (Phase 2, but cheap enough to pull into Phase 0)
- **Rationale**: RepoWiki ships `repowiki map` — a ranked repo map with zero LLM calls and a prompt-ready JSON format for agents. Removes the last custom-extractor from the critical path.
- **Change**: Adopt whichever produces better ranking on the target repo; wire into post-merge hook; output goes into every hydration pack.
- **Acceptance**: `just repomap` regenerates in <30s with no LLM cost; map slice appears in Stage 2 prompts.

### C3. Human-approval gate stays — P1
- **Rationale**: Unchanged from v2 but now applies to bought tools: agent-written wiki pages that feed planning decisions get the same treatment as the architecture digest.
- **Change**: Pages tagged "load-bearing" (architecture overview, module boundary pages) require human review on regeneration; leaf pages auto-sync. Verify-before-relying rule unchanged.
- **Acceptance**: Sync PRs separate load-bearing page changes for review; leaf pages merge automatically.

---

## D. Research & planning phase changes: adopt SDD scaffolding

### D1. Mine GSD and OpenSpec for templates instead of writing them — P1 (Phase 2)
- **Rationale**: The research/planning templates in v2 §2–3 (interview checklist, mandatory dissent sections, plan rubric) now have battle-tested equivalents. GSD: lean spec-driven meta-prompting/context-engineering framework built for Claude Code, the lightweight solo-dev option. OpenSpec: lightweight vendor-neutral spec format, strongest on brownfield change management. Spec Kit's "constitution" concept (immutable principles file applying to every change) maps onto CLAUDE.md.
- **Change**: Install GSD; run one feature through its flow; extract/adapt its planning prompts into the harness templates. Adopt OpenSpec's change-spec format as the `research.md`/`plan.md` schema if it fits (there is a published Beads+OpenSpec workflow cheatsheet — start from it). **Keep from v2 regardless**: mandatory dissent sections (assumptions / disconfirming evidence / steelman) — no SDD framework enforces these — and the different-model plan-review stage.
- **Acceptance**: Templates in the harness are derived-from-and-attributed to GSD/OpenSpec rather than written from scratch; one real feature flows research → plan → beads using them; dissent sections are harness-validated before phase close.
- **Explicit non-adoption**: BMAD (12+ role agents, highest token cost — v2's principles reject role-swarm overhead); full Spec Kit ceremony (constitution concept only).

### D2. Decomposition-while-hot unchanged, plus molecules check — P1
- **Rationale**: No landscape tool does per-ticket context packs at decomposition time; this stays custom and is a core differentiator. Beads 1.0 molecules may provide the container for "ticket + deterministic step sequence."
- **Change**: If B2's molecules assessment is positive, encode the 5-stage sequence as a molecule template attached at ticket creation; context pack remains a pack of file references (per B4).
- **Acceptance**: A created ticket carries: relevant-file list, repo-map slice, interfaces, test strategy, model/effort estimate, and (if adopted) its stage molecule.

---

## E. Parallelization & ops changes

### E1. Session-viewer selection updated — P2 (Phase 4)
- **Rationale**: v2 suggested claude-squad / vibe-kanban as optional viewers. Update: vibe-kanban's company (Bloop) shut down Apr 10 2026 — community-maintained, fully local now; still usable but flag it. Claude Squad remains the lean terminal/tmux option; Conductor (Melty) is polished but macOS-only; Sculptor if container isolation becomes the norm. Also note Claude Code has shipped built-in worktree isolation — check whether it obviates the external manager entirely.
- **Change**: Defer viewer choice to Phase 4; first test Claude Code's native worktree isolation; adopt an external viewer only if the native option can't show N parallel harness runs adequately.
- **Acceptance**: Phase 4 runs use native isolation or a chosen viewer with a one-line justification in the decision log.

### E2. Merge queue discipline (from Gas Town's Refinery pattern) — P2 (Phase 4)
- **Rationale**: Gas Town serializes merges through a dedicated Refinery role — validation that the merge point needs explicit serialization, matching v2's "CI as arbiter."
- **Change**: Implement the merge step as a serialized queue in the harness (one merge in flight; rebase-next-on-green), not as per-agent merging.
- **Acceptance**: Under parallel load, merges land strictly serially; a red CI run blocks the queue rather than being bypassed.

---

## F. Caveat updates to v2 (documentation-only)

- **§11 beads caveat**: replace "alpha, architecture in motion, consider `br`" with "v1.0 shipped Apr 2026; pin 1.x; molecules available for orchestration state."
- **§7 tooling table**: add rows — Archon (evaluated substrate, see B1 memo), Gas City (evaluated substrate), OpenWiki / deepwiki-by-cc (knowledge layer, adopted per C1), RepoWiki map (repo map), GSD/OpenSpec (planning templates), Claude Code native workflows (intra-stage fan-out, per B3). Mark vibe-kanban with the Bloop-shutdown flag.
- **§8 rollout**: insert A1/A2 into Phase 0 deliverables; move all custom knowledge-layer construction out of Phase 2 in favor of C1/C2 spikes; add B1 as the Phase 0 pre-step.
- **New standing rule (from review)**: at every phase gate, answer in writing: "did the harness beat vanilla Claude Code on the last A/B samples, and which planned feature does the data say to cut?"

---

## Suggested epic → ticket mapping for beads

```
epic: harness-v2.1
  ├─ bd: A2 metrics store                    (P0, no deps)
  ├─ bd: B1 substrate spikes (Archon, GasCity) (P0, no deps, timeboxed)
  ├─ bd: B2 beads 1.x upgrade + molecules eval (P0, no deps)
  ├─ bd: A4 executor interface               (P0, deps: B1)
  ├─ bd: A1 A/B baseline harness             (P0, deps: A2)
  ├─ bd: C2 repo map adoption                (P0/P1, no deps)
  ├─ bd: B3 native-workflow review bake-off  (P1, deps: A2, phase-1 pipeline)
  ├─ bd: C1 knowledge-layer buy spike        (P1, deps: C2)
  ├─ bd: C3 load-bearing page approval flow  (P1, deps: C1)
  ├─ bd: D1 GSD/OpenSpec template mining     (P1, deps: none)
  ├─ bd: D2 molecule-attached decomposition  (P1, deps: B2, D1)
  ├─ bd: B4 reference-based handoffs         (P2, deps: phase-1 pipeline)
  ├─ bd: E1 native worktree isolation test   (P2, phase 4)
  └─ bd: E2 serialized merge queue           (P2, phase 4)
```

Sizing note: every item above except C1 and D1 should decompose to tickets completable in a single smart-zone session — apply the harness's own sizing discipline to building the harness.
