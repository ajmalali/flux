# gus — Implementation Plan

A deterministic orchestration harness around Claude Code that owns the full lifecycle of a
software change: **knowledge layer → research → planning → ticketing → per-ticket pipeline →
parallel execution**, with deterministic gates enforced by the environment rather than the model.

Everything gus generates — research docs, plans, ADRs, context packs, transcripts, usage logs,
config — lives under a single `.gus/` folder in the target repo. This repo dogfoods that layout:
this plan lives at `.gus/plans/gus-harness/plan.md`.

This plan synthesizes two research documents (imported under `.gus/research/`):

1. *Upstream phases + knowledge layer* — Research and Planning as first-class, durably-artifacted
   stages on a frontier model; a two-tier persistent knowledge layer that eliminates tool-call
   noise (not verification reads) from interactive sessions.
2. *Per-ticket pipeline* — a thin Python state machine over the Claude Agent SDK, beads (`bd`) as
   the dependency-aware state store, git worktrees for parallelism, and deterministic gates
   (lint/typecheck/test/coverage) as the merge authority.

## 1. Shape of the system

`gus` is an installable CLI tool run *inside a target repo* (it is not a service). All durable
state lives in the target repo (`.gus/` git-versioned artifacts, beads DB) or on disk keyed by
`(ticket, stage)` — the orchestrator itself is stateless and resumable.

```
┌────────────────────────────────────────────────────────────────────┐
│ L0 Knowledge layer (continuous, cheap)                             │
│   repo map (tree-sitter+PageRank) · symbol index · arch docs       │
│   hash-based freshness · context-pack assembler · hook injection   │
├────────────────────────────────────────────────────────────────────┤
│ L1 Research (interactive, Opus-tier, high/xhigh effort)            │
│   Socratic interview · anti-sycophancy → .gus/research/<slug>/research.md │
├────────────────────────────────────────────────────────────────────┤
│ L2 Planning (Opus-tier, xhigh)                                     │
│   (i) requirement critique: INVEST · ambiguity pass · premortem    │
│   (ii) architecture: ≥2 alternatives · devil/angel · tradeoff matrix│
│   verification-read gate (doc-code drift check) →                  │
│   .gus/plans/<slug>/plan.md + .gus/adr/NNNN-*.md                   │
├────────────────────────────────────────────────────────────────────┤
│ L3 Ticketing (Sonnet-tier, mechanical)                             │
│   plan.md → bd epics/tickets w/ deps · per-ticket context pack     │
│   (relevant-file list + repo-map slice, computed at creation time) │
├────────────────────────────────────────────────────────────────────┤
│ L4 Per-ticket pipeline (fresh session per stage)                   │
│   write tests → implement (TDD) → review → address → PR            │
│   deterministic gates between stages · reward-hacking hardening    │
├────────────────────────────────────────────────────────────────────┤
│ L5 Scheduler (deterministic, no LLM)                               │
│   bd ready → worktree per ticket · max_parallel · max_budget_usd   │
│   CI is the merge arbiter                                          │
├────────────────────────────────────────────────────────────────────┤
│ Cross-cutting: model/effort routing · usage+cost logging ·         │
│   prompt-cache-friendly prefixes · plan re-injection per stage     │
└────────────────────────────────────────────────────────────────────┘
```

## 2. Core decisions (ADRs seeded in .gus/adr/)

| # | Decision | Rationale (from the research) |
|---|---|---|
| 0001 | Thin Python state machine; no LangGraph/Temporal/CrewAI | Agentless-style simple pipelines beat complex agent graphs; MAST failure taxonomy penalizes coordination surface |
| 0002 | beads (`bd`) as state store + ready-queue scheduler | Dependency-aware `bd ready --json` is the scheduling primitive; git-backed JSONL survives context clears; pin a version (alpha churn) |
| 0003 | Fresh session per stage, context packs as the interface | Context rot: degradation from ~50K tokens; small high-signal briefs beat accumulated history |
| 0004 | Two-tier knowledge layer; verification reads stay mandatory | "Eliminate noise, not verification" — 23% of repos carry stale doc references; drift gate before plan finalization |
| 0005 | Deterministic gates + environment hardening over LLM judgment | Hardening cuts reward-hacking exploit rates ~88% at no task-success cost; LLM reviewer judges only what machines can't |
| 0006 | All gus artifacts under a single `.gus/` folder | One namespace in target repos; nothing scattered across docs/; committed vs. cache split is explicit |

## 3. Tech choices

- **Language/tooling:** Python ≥3.12, `uv`-managed package, `ruff` + `pyright` + `pytest` on gus itself (dogfood the gate suite).
- **Executor:** `claude-agent-sdk` (Python). Per-call `model`, `effort` (set **explicitly**, never default), `max_turns`, `max_budget_usd`, `permission_mode`, `allowed_tools`, `setting_sources=["project"]`. `fork_session` for branching critique passes off a shared base.
- **State:** beads pinned to a known-good version; on-disk artifacts under `.gus/` in the target repo (context packs, transcripts, usage logs, stage checkpoints).
- **Repo map:** tree-sitter parse → symbol-reference graph → personalized PageRank → token-budgeted map (Aider's algorithm; evaluate vendoring vs. RepoMapper MCP). SQLite cache under `.gus/cache/`, invalidated per-file by content hash.
- **Symbol nav (later):** Serena MCP server as an optional add-on; not on the critical path.
- **Hooks:** `SessionStart` injects the context pack (factual statements, not imperatives); `UserPromptSubmit` for per-turn enrichment; `PreToolUse` (exit 2) blocks test-file edits during implement and dangerous commands everywhere.
- **Local models:** deferred to M7 behind a LiteLLM proxy; nothing in the core depends on it.

### Model / effort routing (initial table, config-driven)

| Stage | Model | Effort |
|---|---|---|
| Research interview | Opus-tier | high/xhigh |
| Requirement critique / red-team | Opus-tier (different model than planner when possible) | high |
| Architecture / plan authoring | Opus-tier | xhigh |
| Plan → tickets | Sonnet-tier | medium |
| Write tests / implement | Sonnet-tier | high |
| Review | different model + rubric | high |
| Explore/retrieval subagents | Haiku-tier | low |
| Knowledge-layer maintenance | script / local | n/a |

## 4. Repository layout

```
gus/                                # this repo (the tool)
├── pyproject.toml
├── README.md
├── .gus/                           # dogfooded: gus's own plans/ADRs/research
│   ├── plans/gus-harness/plan.md   # this file
│   ├── adr/
│   └── research/                   # imported source research docs
├── src/gus/
│   ├── cli.py                      # gus init|index|research|plan|tickets|run|status
│   ├── config.py                   # .gus/gus.toml in target repo: models, efforts, gates, caps
│   ├── knowledge/
│   │   ├── repomap.py              # tree-sitter + PageRank map, token-budgeted
│   │   ├── freshness.py            # per-file content-hash manifest, drift detection
│   │   └── contextpack.py          # assemble brief: map slice + ticket + ADRs (<5s)
│   ├── phases/
│   │   ├── research.py             # interactive interview → research.md
│   │   ├── planning.py             # critique passes + architecture → plan.md + ADRs
│   │   └── ticketing.py            # plan.md → bd graph + per-ticket context packs
│   ├── pipeline/
│   │   ├── runner.py               # Stage abstraction; idempotent, keyed (ticket, stage)
│   │   └── stages/                 # tests.py, implement.py, review.py, fix.py, pr.py
│   ├── gates/                      # subprocess wrappers: lint, typecheck, test (opaque runner), coverage
│   ├── scheduler/                  # bd ready pull, worktree lifecycle, caps
│   ├── sdk/                        # Agent SDK wrapper: routing, usage/cost capture, retries
│   └── hooks/                      # hook scripts gus installs into target repos
└── tests/
```

Everything gus writes **into a target repo** lives under `.gus/` (created by `gus init`):

```
target-repo/
└── .gus/
    ├── gus.toml                    # config (committed)
    ├── research/<slug>/research.md # committed
    ├── plans/<slug>/plan.md        # committed
    ├── adr/NNNN-<decision>.md      # committed
    ├── context/<ticket>/           # per-ticket context packs (committed — part of the ticket brief)
    ├── transcripts/                # gitignored
    ├── usage/                      # per-stage token/cost logs (gitignored)
    ├── cache/                      # repo-map SQLite, hash manifests (gitignored)
    └── .gitignore                  # written by gus init: transcripts/, usage/, cache/
```

beads keeps its own store (`.beads/` by default); if a future bd version supports a custom
path, move it under `.gus/beads/` — otherwise accept the one exception and document it.

## 5. Milestones

Each milestone has an exit benchmark; don't advance until it passes.

### M0 — Skeleton (repo, SDK wrapper, gates)
- `uv`-managed package, `gus` CLI entry point, `gus init` scaffolds `.gus/` + gitignore, `gus.toml` config loader.
- `sdk/` wrapper: one `run_stage()` call = fresh `query()` with explicit model/effort/max_turns/max_budget_usd/permission_mode/allowed_tools; captures `usage`, `total_cost_usd` (treat as estimate), `num_turns` to `.gus/usage/`.
- `gates/`: lint/typecheck/test/coverage as plain subprocess calls with adapters for Python (ruff/pyright/pytest) and TypeScript (eslint/tsc/vitest) targets.
- Install beads, pin version, `bd init` integration.
- **Exit:** `gus run --ticket <id>` executes a trivial hand-written ticket through a single implement stage + gates end-to-end and logs cost.

### M1 — Knowledge layer, Layer 1 (deterministic)
- `repomap.py` + SQLite cache; `freshness.py` content-hash manifest updated by a git post-commit hook.
- `contextpack.py` assembles: repo-map slice + ticket brief + governing ADRs; `SessionStart` hook injects it as factual statements.
- Drift gate primitive: "is any file this pack references stale vs. HEAD?"
- **Exit:** context pack assembles in <5s; touching a file and committing correctly flags dependent artifacts stale.

### M2 — Per-ticket pipeline, serial + hardened (build this before upstream phases — it's the consumer that proves the interfaces)
- Five stages: write tests (confirm they *fail for the right reason*) → implement → review → address → PR.
- Hardening: opaque test runner (pass/fail + minimal diagnostics only), `PreToolUse` hook blocks test-file edits during implement, held-out test support, bounded review loop (max 3) then park ticket for human triage with a failure note.
- Reviewer: different model + structured rubric (correctness, test adequacy, security, readability); files follow-up beads; deterministic gates run upstream of it.
- Plan-reminder re-injection: each stage prompt re-includes the plan/ADR summary.
- **Exit (two benchmarks):** (a) one real ticket flows through all 5 stages unattended to a mergeable PR; (b) a deliberately gameable ticket (easiest "solution" is weakening the test) is caught by the harness.

### M3 — Research phase
- `gus research <slug>`: interactive session, read-only (`plan` permission mode), Opus-tier/high; system prompt enforces interview-not-answer, one question at a time, explicit disagreement, named assumptions; Explore subagents (Haiku, low) for any codebase lookup so the conversation stays clean.
- Terminates by writing `.gus/research/<slug>/research.md` (problem, current behavior w/ file:line citations, constraints, non-goals, open questions, glossary, references).
- **Exit:** research.md for a real feature is complete enough that a fresh session can run planning without re-asking the human anything already answered.

### M4 — Planning phase
- `gus plan <slug>`: consumes `research.md` (not the raw conversation) in a fresh session.
- Pass 1 critique: INVEST per story (list only failed criteria + reason), ambiguity taxonomy grounded in the research glossary, premortem via devil's-advocate fork (`fork_session`).
- Pass 2 architecture: ≥2 genuinely distinct designs scored on complexity/blast radius/reversibility/test surface/performance; devil/angel/judge synthesis.
- **Verification-read gate:** before finalizing, every load-bearing claim ("we already have X") is spot-checked against live code; any referenced file whose hash is stale forces a read. Plan cannot finalize with unverified claims.
- Outputs: `.gus/plans/<slug>/plan.md` (milestones, task list w/ deps) + one ADR per decision, agent-optimized.
- **Exit:** on 3–5 real features, planning catches ≥1 stale-abstraction or ambiguity per feature before implementation.

### M5 — Ticketing + bidirectional writeback
- `gus tickets <slug>`: Sonnet-tier decomposition of approved plan.md into bd epics/tickets with deps (interface-first ordering, file-level ownership); human reviews the graph before it's live (graph construction is human-supervised — known weak spot).
- Per-ticket context pack computed at creation time (relevant files + map slice + links to research/plan/ADRs + INVEST-clean acceptance criteria) under `.gus/context/<ticket>/`.
- Writeback: pipeline failures that invalidate the plan mark ADRs superseded, amend plan.md, regenerate affected tickets.
- **Exit:** ≥90% of pipeline stages start with zero cold exploration (measured: no Read/Grep of files outside the pack in stage transcripts).

### M6 — Parallelism
- Scheduler loop: pull `bd ready --json` → worktree per ticket → run pipeline → CI on branch is merge arbiter (never auto-merge on agent say-so). Hard `max_parallel` + per-run `max_budget_usd`.
- **Exit:** 3+ independent tickets complete in parallel, zero cross-contamination, conflicts surface in CI not silent overwrites.

### M7 — Economics
- Prompt-cache-friendly stable prefixes (system + context pack first, varying tail).
- Complexity heuristic (files touched, LOC estimate, new-vs-modify) → model/effort/split-or-merge-stages routing; log actuals, refine from history. No learned router until data shows the heuristic is the bottleneck.
- Optional: LiteLLM proxy routing commit messages / summaries / triage to a local model — only if measured net savings.
- **Exit:** ≥40% token/cost reduction per ticket vs M2 baseline with no gate-suite quality regression.

### M8 — Layer 2 knowledge + observability polish
- LLM-maintained architecture docs regenerated on significant diffs (cheap tier); CLAUDE.md kept small and factual.
- `gus status` dashboard: per-ticket stage, cost, gate results, parked tickets.
- **Exit:** knowledge-layer maintenance cost < measured retrieval savings; otherwise cut Layer 2 to on-demand (pre-agreed threshold).

## 6. Thresholds that change the plan

- Verification reads catch stale-context errors in **<5%** of plans → widen knowledge-layer reliance; **>20%** → tighten drift gate, shorten re-index interval.
- Deterministic gates catch **≥90%** of defects → shrink the LLM reviewer stage.
- A ticket routinely needs **>3** review iterations → tickets are too big; fix decomposition, not the loop.
- Cascade/local-model escalation makes net cost exceed always-Sonnet → kill that cascade.
- bd graph construction keeps producing bad dependencies → keep it human-supervised permanently.

## 7. Risks

- **Alpha dependencies:** beads architecture in motion (pin version; `br` Rust port as fallback), SDK option churn (`effort` passthrough had historical gaps — verify on installed version), hook semantics evolving (re-verify against official hooks reference).
- **Stale context is the dominant residual risk** — the drift gate mitigates, doesn't eliminate. Budget for plans built on changed abstractions.
- **Sycophancy is only partially mitigable** — a human owns final architecture decisions on high-stakes calls.
- **Cost figures are estimates** — `total_cost_usd` is client-side; verify against Console billing before trusting routing economics.

## 8. Defaults chosen (flag if wrong)

- **Build order** puts the per-ticket pipeline (M2) before research/planning (M3–M4): the pipeline is the consumer that validates the context-pack and ticket interfaces, and it delivers usable value earliest. The research docs order them the other way (knowledge layer → planning → pipeline); knowledge layer stays first either way.
- **First gate adapters:** Python + TypeScript targets.
- **Local models:** deferred entirely to M7.
- **beads over the `br` Rust port** initially, pinned.
