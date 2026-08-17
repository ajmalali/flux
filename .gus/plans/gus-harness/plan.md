# gus — Implementation Plan (v2.1)

A deterministic orchestration harness around Claude Code that owns the full lifecycle of a
software change: **knowledge layer → research → planning → ticketing → per-ticket pipeline →
parallel execution**, with deterministic gates enforced by the environment rather than the model.

Everything gus generates lives under a single `.gus/` folder in the target repo. This repo
dogfoods that layout. Concrete mechanism design (state machine, executor interface, artifact
handoff contract) lives in **[`design.md`](design.md)**.

Sources, imported under `.gus/research/`:
1. `upstream-phases-and-knowledge-layer.md` — research/planning as durably-artifacted stages;
   two-tier knowledge layer; eliminate noise, keep verification reads.
2. `per-ticket-pipeline.md` — thin Python state machine over the Claude Agent SDK; beads as
   state store; worktrees; deterministic gates as merge authority.
3. `harness-v2.1-changes.md` — Aug 2026 landscape + critical review deltas: A/B baseline vs
   vanilla Claude Code, metrics as a P0 deliverable, "meaner v1" re-sequencing, buy-not-build
   knowledge layer, beads 1.x, executor interface, substrate spikes.

## 1. Shape of the system

`gus` is an installable CLI tool run *inside a target repo* (not a service). All durable state
lives in the target repo (`.gus/` artifacts, beads DB) keyed by `(ticket, stage)` — the
orchestrator is stateless and resumable (see design.md §1).

```
┌────────────────────────────────────────────────────────────────────┐
│ L0 Knowledge layer (BOUGHT: repowiki map / OpenWiki-class wiki)    │
│   ranked repo map (zero-LLM) · agent-written wiki · hash freshness │
│   kept custom: ADR log · interface catalog · exploration-call KPI  │
├────────────────────────────────────────────────────────────────────┤
│ L1 Research (interactive, Opus-tier, high/xhigh)                   │
│   GSD/OpenSpec-derived templates + mandatory dissent sections      │
│   → .gus/research/<slug>/research.md                               │
├────────────────────────────────────────────────────────────────────┤
│ L2 Planning (Opus-tier, xhigh)                                     │
│   critique (INVEST·ambiguity·premortem) · ≥2 architectures ·       │
│   different-model plan review · verification-read drift gate       │
│   → .gus/plans/<slug>/plan.md + .gus/adr/NNNN-*.md                 │
├────────────────────────────────────────────────────────────────────┤
│ L3 Ticketing (decomposition-while-hot; core differentiator)        │
│   plan.md → bd graph (human-reviewed) · per-ticket context pack    │
│   (file refs + map slice) at creation time · molecules if adopted  │
├────────────────────────────────────────────────────────────────────┤
│ L4 Per-ticket pipeline (fresh session per stage; design.md)        │
│   tests → implement → review → fix → PR · runner-validated         │
│   artifacts · deterministic gates · reward-hacking hardening       │
├────────────────────────────────────────────────────────────────────┤
│ L5 Scheduler (deterministic, no LLM)                               │
│   bd ready → worktree per ticket · max_parallel · max_budget_usd   │
│   serialized merge queue (one merge in flight, rebase-on-green)    │
│   CI is the merge arbiter                                          │
├────────────────────────────────────────────────────────────────────┤
│ Cross-cutting: Executor interface (swap-able) · metrics store ·    │
│   A/B baseline vs vanilla Claude Code · plan re-injection          │
└────────────────────────────────────────────────────────────────────┘
```

## 2. Core decisions (ADRs in .gus/adr/)

| # | Decision |
|---|---|
| 0001 | Thin Python state machine; no LangGraph/Temporal/CrewAI (pending B1 spike confirmation) |
| 0002 | beads ≥1.0 as state store + ready-queue scheduler; pin 1.x; assess molecules |
| 0003 | Fresh session per stage; context packs as the interface |
| 0004 | Two-tier knowledge layer; verification reads stay mandatory (amended by 0009) |
| 0005 | Deterministic gates + environment hardening over LLM judgment |
| 0006 | All gus artifacts under a single `.gus/` folder |
| 0007 | Executor behind an interface; no stage code imports the SDK directly |
| 0008 | Metrics store + vanilla-Claude A/B baseline are P0 deliverables, with a written kill-criterion |
| 0009 | Knowledge layer is bought, not built (repowiki map; OpenWiki / deepwiki-by-cc spike) |

## 3. Tech choices

- **Language/tooling:** Python ≥3.12, `uv`-managed, `ruff` + `pyright` + `pytest` on gus itself.
- **Executor:** `Executor` protocol; first impl `claude-agent-sdk` (Python). Per-call `model`,
  `effort` (always explicit), `max_turns`, `max_budget_usd`, `permission_mode`, `allowed_tools`,
  `setting_sources=["project"]`; `fork_session` for critique branches.
- **State:** beads 1.x pinned; on-disk artifacts + checkpoints under `.gus/` (design.md §1).
- **Repo map:** `repowiki map` (zero-LLM, prompt-ready JSON) or Aider RepoMapper — whichever
  ranks better on the target repo; post-merge hook regeneration; no custom extractor.
- **Wiki:** OpenWiki or deepwiki-by-cc (Phase 2 spike); plain Markdown in-repo; load-bearing
  pages get human review on regeneration, leaf pages auto-sync.
- **Templates:** research/plan schemas mined from GSD + OpenSpec (attributed); custom-kept:
  mandatory dissent sections (assumptions / disconfirming evidence / steelman) + different-model
  plan review. Explicit non-adoption: BMAD role swarms; full Spec Kit ceremony (constitution
  concept only, mapped to CLAUDE.md).
- **Hooks:** `SessionStart` injects context pack (factual statements); `PreToolUse` (exit 2)
  blocks test-file edits during implement + dangerous commands everywhere.
- **Local models / routing:** deferred to M6, and only if metrics show model spend dominates.

### Model / effort routing (initial, config-driven)

| Stage | Model | Effort |
|---|---|---|
| Research interview | Opus-tier | high/xhigh |
| Requirement critique / red-team | Opus-tier (different model than planner when possible) | high |
| Architecture / plan authoring | Opus-tier | xhigh |
| Plan → tickets | Sonnet-tier | medium |
| Write tests / implement | Sonnet-tier | high |
| Review | different model + rubric (bake-off vs native-workflow multi-lens panel, M1 exit) | high |
| Explore/retrieval subagents | Haiku-tier | low |
| Repo map / wiki sync | zero-LLM script / cheap tier | n/a |

## 4. Repository layout

```
gus/                                # this repo (the tool)
├── pyproject.toml
├── README.md
├── .gus/                           # dogfooded: gus's own plans/ADRs/research
├── src/gus/
│   ├── cli.py                      # gus init|index|research|plan|tickets|run|status|metrics
│   ├── config.py                   # .gus/gus.toml loader (models, efforts, gates, caps, kill-criteria)
│   ├── executor/                   # Executor protocol + ClaudeAgentSDKExecutor (ADR 0007)
│   ├── runner/                     # transition fn, run_ticket loop, checkpoints (design.md §1)
│   ├── stages/                     # tests, implement, review, fix, pr (hydrate/config/artifact/gates/commit)
│   ├── gates/                      # lint, typecheck, opaque test runner, coverage — subprocess wrappers
│   ├── knowledge/                  # adapters over bought tools: repo map, wiki slicing, freshness
│   ├── phases/                     # research.py, planning.py, ticketing.py
│   ├── scheduler/                  # bd ready pull, worktrees, merge queue, caps
│   ├── metrics/                    # metrics.jsonl writer + `gus metrics` report + A/B harness
│   └── hooks/                      # hook scripts gus installs into target repos
└── tests/
```

Target-repo artifacts (created by `gus init`), committed vs. gitignored:

```
target-repo/
└── .gus/
    ├── gus.toml                    # config incl. kill-criteria (committed)
    ├── research/<slug>/            # committed
    ├── plans/<slug>/               # committed
    ├── adr/                        # committed
    ├── context/<ticket>/           # handoff artifacts (committed)
    ├── state/<ticket>/             # stage checkpoints (gitignored)
    ├── transcripts/                # gitignored
    ├── usage/metrics.jsonl         # gitignored
    ├── cache/                      # repo map, hash manifests (gitignored)
    └── .gitignore                  # written by gus init
```

beads keeps `.beads/` (its default) — the one exception, tolerated until bd supports a custom path.

## 5. Milestones ("meaner v1" sequencing — change doc A3)

Execution pipeline + hardening + metrics + A/B ship **before any knowledge-layer work beyond a
repo map**. No custom knowledge-layer code exists before M2. Standing rule at **every** phase
gate, answered in writing: *"did the harness beat vanilla Claude Code on the last A/B samples,
and which planned feature does the data say to cut?"*

### Pre-M0 — Substrate spikes (hard timebox: half-day each)
- **B1:** implement Stage 1 + Stage 2 with a gate between them in Archon and in Gas City.
  Scorecard: (1) per-ticket config from beads, (2) conditional stage skip, (3) bounded fix loop,
  (4) per-stage cost surfacing. Default hypothesis: custom wins (the pipeline is dynamic exactly
  where YAML DSLs are weak). Steal Archon's run-logging/dashboard model regardless.
- **B2:** beads 1.x installed + pinned; molecules assessed — can they express the 5-stage
  pipeline natively? (Feeds the Gas City option and M4 decomposition.)
- **Exit:** written decision memo (keep custom / adopt X) with the 4-point scorecard + molecules
  assessment; revisited only at phase gates.

### M0 — Skeleton: executor, runner spine, gates, metrics, repo map
- `Executor` protocol + SDK impl + `ExecConfig` (design.md §1); `gus init` scaffolds `.gus/`.
- Checkpoint store + transition function + `run_ticket()` loop; idempotency and crash-resume
  proven with a stubbed executor in plain pytest (no LLM).
- Gate suite as subprocess wrappers (Python: ruff/pyright/pytest; TS: eslint/tsc/vitest).
- **Metrics store (A2):** per-(ticket, stage) JSONL + `gus metrics` report.
- **Repo map (C2, pulled forward):** `repowiki map` or RepoMapper wired to a post-merge hook.
- **Exit:** one trivial hand-written ticket flows through a single implement stage + gates end
  to end; `gus metrics` prints per-stage cost/time; `just repomap` regenerates in <30s, no LLM.

### M1 — Full pipeline, hardened + A/B baseline
- All five stages per the design.md stage I/O table, with runner-validated required artifacts.
- Hardening: opaque test runner, PreToolUse test-edit block, held-out tests, red-step verified
  by the runner, bounded review loop (max 3) → park with note.
- **A/B baseline (A1):** `gus run --vanilla` harness; 1-in-10 cadence; kill-criterion in gus.toml.
- **Review bake-off (B3):** Stage 3 as a Claude Code native workflow (adversarial-verify,
  multi-lens reviewers: correctness / security / design-fit) vs single different-model reviewer;
  keep the cheaper config that catches ≥ as many planted defects.
- **Exit:** (a) one real ticket → mergeable PR unattended; (b) a deliberately gameable ticket is
  caught; (c) ≥3 vanilla baseline runs in the comparison table.

### M2 — Knowledge layer, bought
- **C1 spike (1 day total):** OpenWiki vs deepwiki-by-cc on the target repo. Criteria: Markdown
  in-repo, incremental sync works on real diff patterns, acceptable sync cost, pages sliceable
  into hydration packs.
- **C3:** load-bearing pages (architecture overview, module boundaries) require human review on
  regeneration; leaf pages auto-sync. Verify-before-relying unchanged.
- Kept custom: ADR log, interface catalog (deterministic extraction), exploration-call KPI hook.
- **Exit:** wiki generated; one synthetic merge triggers a correct incremental update; hydration
  assembles packs from wiki pages + ADRs + repo map within token budget.

### M3 — Research + Planning phases
- Templates mined from GSD (run one feature through its flow first) and OpenSpec's change-spec
  format (start from the published Beads+OpenSpec workflow cheatsheet); dissent sections are
  harness-validated before a phase can close.
- `gus research <slug>`: read-only interview session, Opus/high, Explore subagents for lookups
  → `research.md` (problem, current behavior w/ file:line, constraints, non-goals, open
  questions, glossary).
- `gus plan <slug>`: critique passes (INVEST, ambiguity vs glossary, premortem fork), ≥2
  architectures scored, different-model plan review, **verification-read drift gate** — no plan
  finalizes with load-bearing claims referencing stale-hash files unchecked.
- **Exit:** one real feature flows research → plan → approved using the mined templates;
  planning catches ≥1 stale-abstraction or ambiguity before implementation.

### M4 — Ticketing: decomposition-while-hot (core differentiator, stays custom)
- `gus tickets <slug>`: plan.md → bd graph (human-reviewed before live); interface-first
  ordering, file-level ownership.
- Each ticket carries at creation: relevant-file list, repo-map slice, interfaces, test
  strategy, model/effort estimate — as **references, not pasted content** (B4); and its stage
  molecule if B2's assessment was positive (D2).
- Reference-based handoffs enforced pipeline-wide: pack size must not grow monotonically across
  stages (asserted in tests).
- Bidirectional writeback: failures that invalidate the plan → ADR superseded, plan amended,
  affected tickets regenerated.
- **Exit:** ≥90% of stages start with zero cold exploration (no Read/Grep outside the pack).

### M5 — Parallelism + merge discipline
- Scheduler: `bd ready --json` → worktree per ticket; hard `max_parallel` + `max_budget_usd`.
- Test Claude Code's **native worktree isolation** first; external viewer (Claude Squad /
  community vibe-kanban) only if native can't show N parallel runs (E1).
- **Serialized merge queue (E2, Refinery pattern):** one merge in flight, rebase-next-on-green;
  red CI blocks the queue, never bypassed. CI is the merge arbiter.
- **Exit:** 3+ tickets in parallel, zero cross-contamination, merges land strictly serially.

### M6 — Economics (only if metrics justify)
- Enter only if the metrics store shows model spend is the dominant cost.
- Prompt-cache-stable prefixes (already structured for it); complexity heuristic → model/effort
  routing; optional LiteLLM/local-model cascade for summaries/commit messages — kill any cascade
  whose escalation rate makes it net-negative.
- **Exit:** ≥40% token/cost reduction per ticket vs M1 baseline, no gate-suite regression.

## 6. Thresholds that change the plan

- **Kill-criterion (standing):** vanilla Claude Code wins on cost AND quality for 3 consecutive
  A/B samples → freeze harness feature work, investigate.
- Verification reads catch stale-context errors in <5% of plans → widen knowledge-layer
  reliance; >20% → tighten drift gate, shorten sync interval.
- Deterministic gates catch ≥90% of defects → shrink the LLM reviewer stage.
- A ticket routinely needs >3 review iterations → tickets are too big; fix decomposition.
- Wiki sync cost exceeds measured retrieval savings → wiki goes on-demand-only; repo map stays.
- bd graph construction keeps producing bad dependencies → keep it human-supervised permanently.

## 7. Risks

- **Claude Code absorbs harness features quarterly** (native workflows, worktree isolation) —
  defenses: executor interface (ADR 0007), A/B baseline (ADR 0008), thinness principle: durable
  value is the beads graph, knowledge artifacts, ticket-sizing discipline, and gate suite.
- **Stale context remains the dominant residual risk** — drift gate mitigates, doesn't eliminate.
- **Sycophancy only partially mitigable** — human owns final architecture calls.
- **`total_cost_usd` is a client-side estimate** — verify routing economics against real billing.
- Landscape tools (Archon, Gas City, OpenWiki, deepwiki-by-cc, RepoWiki) are young — every
  adoption goes through a timeboxed spike with a written memo, never straight to dependency.

## 8. Defaults chosen (flag if wrong)

- Substrate spikes (Pre-M0) happen before any runner code; custom-Python remains the default
  hypothesis pending the memos.
- First gate adapters: Python + TypeScript targets.
- Routing/local models gated behind metrics evidence (M6), not scheduled by default.
- beads 1.x (the `br` fallback is dropped per the v2.1 landscape update).
