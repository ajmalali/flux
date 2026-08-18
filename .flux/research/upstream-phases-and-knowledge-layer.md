# Critical Design Review & Consolidated Implementation Guide: A Deterministic Orchestration Harness Around Claude Code

## TL;DR
- **Build the two new upstream phases (Research → Planning) as first-class, durably-artifacted stages that run on a frontier model at high effort, because plan quality is the single largest lever on downstream success — a subpar plan hurts more than no plan at all, and structured pre-planning buys roughly +7–10 percentage points of issue-resolution on SWE-bench-class benchmarks.** Do this before you optimize execution economics.
- **Do NOT fully eliminate codebase reading during planning — that premise is wrong.** Eliminate *tool-call noise from the interactive conversation* (via a persistent, continuously-maintained knowledge layer plus Explore/retrieval subagents), but keep *targeted verification reads* in the loop. Pre-computed context that goes stale is "confidently wrong," which is worse for an agent than ignorance; every load-bearing claim a plan depends on must be spot-checked against live code.
- **Adopt a two-tier context economy:** a cheap/local model or deterministic script maintains a repo-map + symbol index + architecture docs continuously (hash/Merkle-invalidated on commit), and the frontier planning model consumes distilled briefs, not raw grep output. Route research/planning to Opus-tier + high/xhigh effort; route TDD implementation to Sonnet-tier; route exploration/retrieval to Haiku-tier or a local model via LiteLLM.

## Key Findings

1. **Plan quality dominates outcomes, and this is now empirically grounded.** arXiv 2604.12147 (*Evaluating Plan Compliance in Autonomous Programming Agents*, IBM–Illinois / Hirzel et al.) examined "16,991 trajectories from SWE-agent across four LLMs on SWE-bench Verified and SWE-bench Pro under eight plan variations," concluding verbatim: "Providing the standard plan improves issue resolution… periodic plan reminders can mitigate plan violations… A subpar plan hurts performance even more than no plan at all." Independent work (CodeR, arXiv 2406.01304) attributes a +10.33-point issue-resolution gain to pre-planning over on-the-fly deciding; Probe-and-Refine (arXiv 2606.20512) shows structured guidance converts extra exploration compute into a 7–10 pp improvement while *unstructured* exploration "saturates quickly" and yields nothing. This validates the user's instinct to invest heavily in Research and Planning phases.

2. **"Plan once with the expensive model, execute many times with the cheap one" is a real, documented economic pattern.** The official Claude Code docs describe the `opusplan` alias as a "Special mode that uses opus during plan mode, then switches to sonnet for execution" (per Ercan Atay, Claude Code v2.1.77). The rationale, per hands-on testing by Codely (Opus 4.6 vs Sonnet 4.6), is: "Opus 4.6 is also better for implementing the plan, but the difference is not as big. The gap between both models narrows significantly during the implementation phase. That small difference makes using Sonnet for implementation more attractive due to its lower cost… Therefore, Opus 4.6 for planning and Sonnet 4.6 for implementing." You pay for frontier reasoning only where it moves the needle.

3. **The Claude Agent SDK exposes an `effort` parameter (low/medium/high/xhigh/max) that is the correct knob for phase-based compute control** — it governs how many tokens Claude spends (including how many tool calls it makes), not the price tier. API default is high; Anthropic recommends xhigh as the starting point for demanding coding/agentic work, and low "for simpler tasks… such as subagents."

4. **The dominant industry pattern for "no re-reading" is NOT a static dumped context — it is just-in-time retrieval plus context isolation.** Anthropic's "Effective context engineering for AI agents" (Rajasekaran, Dixon, Ryan & Hadfield, Anthropic Applied AI Team, Sept 29, 2025) states verbatim: "CLAUDE.md files are naively dropped into context up front, while primitives like glob and grep allow it to navigate its environment and retrieve files just-in-time, effectively bypassing the issues of stale indexing and complex syntax trees." The way to keep the *interactive* conversation clean is to push retrieval into Explore subagents whose intermediate work never enters the main context — only the distilled summary returns.

5. **Stale pre-computed context is a first-order risk, not a footnote.** Multiple 2026 sources converge: "When docs were for humans, staleness was tolerable… AI agents are not [good at compensating]. When an agent reads a context document that says user_id is in the accounts table, and it was actually migrated… the agent doesn't figure it out. It confidently operates on wrong information." The DOCER analysis in arXiv 2606.09090 (*Context Rot in AI-Assisted Software Development*, Treude & Baltes) detected "230 stale code element references across 82 repositories, or 23.0% of those analyzed (95% CI 18.8–27.2%)" out of 356 repos (median 1, max 20 per repo); manual inspection of 50 flagged elements found 32 (64%) were "genuine referential rot." This is the core reason the user's "eliminate codebase reading" premise must be softened to "eliminate noise, keep verification."

6. **The tooling to build the knowledge layer already exists and is mostly open-source:** Aider's tree-sitter + PageRank repo map (and its standalone MCP fork RepoMapper), Serena (LSP-backed symbolic MCP server, ~40 languages), DeepWiki (Cognition/Devin auto-generated wikis with an MCP server), and Cursor's Merkle-tree incremental indexing model as a reference architecture. Claude Code's SessionStart and UserPromptSubmit hooks are the deterministic injection points for context packs.

7. **Sycophancy/agreement bias is a documented, measurable threat specifically to the planning phase.** LLMs "prioritize expected user agreement over honesty," and opinion-agreement sycophancy is "largely imperceptible to participants, yet it subtly reinforced persistence in initial judgments by reducing sensitivity to opposing evidence." Because the user's planning phase is an interactive discussion where the human proposes an architecture, this is exactly the failure mode to engineer against — via devil's-advocate personas, multi-perspective critique, and a different model/rubric for requirement red-teaming.

## Details

### Part I — The Research Phase (upstream of everything)

**Purpose:** converge with the human on a shared understanding of the problem before any solution is proposed. This is discovery, not design.

**Design.** Run this as an interactive Claude Code session in a mode analogous to plan mode (read-only, no edits). Use a frontier model (Opus-tier) at high/xhigh effort — this is the cheapest phase in tokens and the most valuable in outcome, per Anthropic's own framing that "phases 1 and 2 (Explore + Plan) are the cheapest in terms of tokens and the most valuable in terms of outcome."

**Interview/Socratic pattern.** Instruct the model explicitly to interview rather than answer: elicit the actual problem, the users, the constraints, the non-goals, and the definition of done, asking one clarifying question at a time. This directly counters the ambiguity problem: per the Orchid benchmark (1,304 function-level tasks) in arXiv 2604.21505 (*Assessing the Impact of Requirement Ambiguity on LLM-based Function-Level Code Generation*), ambiguity "consistently degrades generation quality across all evaluated models, reducing Pass@1 accuracy by an average of 7.22 percentage points, with the largest observed decline reaching 31.10 points." Front-loading disambiguation pays off downstream.

**Anti-sycophancy from the first turn.** Because interaction context increases sycophancy, the research agent's system prompt should require it to surface disagreements, name assumptions, and refuse to simply mirror the user's framing. Consider a "tenth-man"/devil's-advocate sub-pass.

**Durable output — `research.md`.** The phase MUST terminate by writing a durable artifact so downstream stages never re-derive understanding. Suggested structure:
```
docs/research/<slug>/research.md
  # Problem statement (what, for whom, why now)
  # Current behavior / today's pain (with live-code citations: file:line)
  # Constraints (technical, product, regulatory)
  # Non-goals / out of scope
  # Open questions (resolved | deferred)
  # Glossary of domain terms
  # References: linked ADRs, prior tickets, external docs
```

### Part II — The Planning Phase (two parts, one or more plans out)

**Part (i): Understand & critique the requirement.** Feed `research.md` (not the raw conversation) into a fresh session. Run a structured requirement critique:
- **INVEST checklist** for each candidate story (Independent, Negotiable, Valuable, Estimable, Small, Testable) plus SMART for technical tasks derived from them. Have the model list *only* the criteria a story fails, with a one-to-two-sentence reason (the Mountain Goat Software pattern).
- **Ambiguity taxonomy pass** (semantic, syntactic, functional, operational, scope, temporal, quality) — but note the documented weakness: without domain grounding, LLM ambiguity detectors show high recall/low precision (over-flagging), so pair the pass with the pre-computed domain glossary from `research.md`.
- **Premortem / red-team pass**: "Assume this shipped and failed six months later — enumerate why." Use a devil's-advocate persona and, ideally, a *different model* than the one that will write the plan, to break anchoring.

**Part (ii): Discuss implementation architecture → produce plan(s).** This is where sycophancy and first-suggestion anchoring bite hardest. Mitigations, in order of value:
- **Multi-perspective / structured tradeoff matrix**: force the model to generate ≥2 genuinely distinct architectures and score each against explicit criteria (complexity, blast radius, reversibility, test surface, performance), rather than defending the first idea.
- **Devil-Angel critique** (from the RedDebate pattern): one persona attacks the leading design, one defends, a judge synthesizes. In an LLM-as-judge role, use a different reviewer model + rubric.
- **Verification reads are mandatory here** (see Part IV): every load-bearing claim ("we already have a retry helper in `net/`") must be confirmed against live code, not the knowledge layer alone.

**Durable outputs — plan + ADRs.** Persist as files in the repo, agent-optimized:
```
docs/plans/<slug>/plan.md            # the executable plan: milestones, task list w/ deps
docs/adr/NNNN-<decision>.md          # one decision per file: Title, Status, Context, Decision, Consequences, Alternatives
```
ADRs should be written for an *agent reader*: "the same decision, restructured so a machine can find it, scope it, follow it, and check it." They are the durable half of context engineering — "the deliberate, stable decisions, as opposed to the throwaway instructions you type into a single session" (Actual AI, "ADRs for Coding Agents"). The MADR template is a good starting schema.

**Model economics for these phases.** Use `opusplan`-style routing conceptually: Opus-tier + high/xhigh effort for research, requirement critique, and architecture; drop to Sonnet-tier for the mechanical decomposition of an approved plan into tickets. The evidence that this is worth it: the Opus/Sonnet planning-quality gap is large while the execution gap is small (Codely), and structured planning converts compute into resolution gains where unstructured effort is wasted (Probe-and-Refine, arXiv 2606.20512).

### Part III — Ticket decomposition & the research→planning→ticketing handoff

Decompose the approved `plan.md` into beads (`bd`) tickets. Each ticket must be a self-contained briefing so no downstream stage re-derives understanding:
- Links to `research.md`, `plan.md`, and the governing ADR(s).
- INVEST-clean acceptance criteria (testable).
- **A pre-computed relevant-file list and repo-map slice** generated at ticket-creation time (see Part IV) — this is the artifact that lets the per-ticket pipeline start without a cold exploration.
- Dependencies expressed in `bd` so the ready-queue scheduler can parallelize.

**Bidirectional flow.** Ticketing is not one-way. If implementation reveals the plan was wrong, that learning must flow back: update the ADR (status → superseded), amend `plan.md`, and regenerate affected tickets. Treat plan/ADR files as living documentation (the OpenSpec "specs live in your code" model — "we preserve the functional requirements behind your code as living documentation") rather than write-once scaffolding. Spec Kit's documented weakness is instructive here: it "gets you a clean spec and a first generation, then leaves you on your own" — your harness must own the whole lifecycle, not just the first generation.

### Part IV — The persistent knowledge layer (eliminating re-reading *noise*)

**The two-tier pattern (this is the heart of question B).** A cheap continuously-running maintainer builds and refreshes the knowledge layer; the frontier model consumes distilled briefs.

**Layer 1 — deterministic, script-maintained artifacts (no LLM needed):**
- **Repo map** via Aider's tree-sitter + PageRank algorithm (files = nodes, symbol references = edges, personalized PageRank ranks what matters, binary-search to fit a token budget, SQLite-cached). Use the standalone RepoMapper MCP fork (github.com/Cryect/RepoMapper) so it runs outside Aider.
- **Symbol index / navigation** via Serena (github.com/oraios/serena — LSP-backed, symbol-level `find_symbol`/`find_referencing_symbols`, ~40 languages) exposed as an MCP server — far more token-efficient and precise than grep for "who calls this." Note the token-usage debate and onboarding cost the README doesn't lead with.
- **Freshness via hashing.** Adopt Cursor's model: a Merkle tree over file hashes, walk only the branches whose hashes differ, re-index only changed files (Cursor syncs on a ~5–10 minute interval). Wire regeneration into a git post-commit hook and a CI job; store a content hash alongside each artifact for staleness detection.

**Layer 2 — LLM-maintained artifacts (cheap/local model via LiteLLM):**
- **Architecture docs / codebase wiki** — either self-hosted auto-doc generation or DeepWiki (Cognition/Devin, deepwiki.com) which "treats the source code itself as the ground truth and generates documentation directly from it"; it exposes an MCP server for Claude Code. Regenerate on a schedule or on significant diffs.
- **CLAUDE.md hierarchy** — the "agent's constitution," loaded into every session; keep it factual (project conventions, invariants) and *small*.

**Context assembly / injection (deterministic, by the environment):**
- Use a **SessionStart hook** to inject a "context pack" (the relevant repo-map slice, the ticket brief, the governing ADR) — its stdout is added to context. Note the documented gotcha: write injected context as *factual statements* ("The deployment target is production"), not imperative system commands, or Claude's prompt-injection defenses will surface it to the user instead of using it. SessionStart hooks re-run on resume/fork, so they can refresh context.
- Use **UserPromptSubmit hooks** for just-in-time enrichment per turn (stdout is injected as context; but note replayed values like timestamps go stale on `--resume`).
- Prefer **structured briefs over raw file dumps.** Given context rot (Chroma's finding that recall degrades as tokens grow; the ~40% context-usage degradation threshold cited in OpenSpec write-ups; the ~1M-token performance ceiling), the goal is "the smallest set of high-signal tokens," not maximal inclusion.

**Subagent retrieval pattern (keeps interactive phases clean):** dispatch Claude Code's built-in **Explore** subagent (read-only, runs on Haiku) for any investigation. Its intermediate reads stay in *its* context; only the summary returns. This is precisely how you keep research/planning discussions free of grep/find/read noise. Caveat: whatever the subagent returns lands in the parent context verbatim, so instruct it to summarize aggressively — "subagents are a great context-isolation primitive, not a magic productivity wand."

### Part V — Critical analysis of the user's premise (question C)

**Verdict: the premise "eliminate codebase reading during planning" is half-right and half-dangerous.**
- **Right:** eliminate *interactive tool-call noise*. There is no reason for the human-facing research/planning conversation to be polluted by 49 irrelevant file reads. Isolation subagents and pre-computed briefs solve this cleanly.
- **Dangerous:** eliminating *verification reads* means plans get built on stale abstractions and hallucinated APIs — the "understanding theater" problem where a tidy summary hides load-bearing details. The DOCER 23%-of-repos stale-reference rate, and the "confidently wrong" failure mode, mean an unverified knowledge layer will eventually mislead the planner with high confidence.

**Where live inspection is non-negotiable:** any architecture decision that depends on a specific current interface, data model, or invariant; anywhere the plan asserts "we already have X"; anywhere the knowledge layer's content hash is older than the last commit touching the relevant files. Build a cheap **doc-code drift gate**: before finalizing a plan, diff the knowledge-layer artifacts' hashes against current file hashes; force a spot-check read for any load-bearing file that is stale. (This mirrors the merge-triggered doc-drift loops emerging in 2026 tooling like Mintlify Workflows and Augment's self-updating docs.)

**Should planning update the knowledge layer as a side effect? Yes.** Learnings discovered during research/planning (a newly understood invariant, a corrected mental model) should flow back into the architecture docs and ADRs. This is the "continuous context" ideal — treat context quality like data quality, with freshness SLAs and drift detection.

### Part VI — Recap & integration of the prior report (the per-ticket pipeline, tooling, routing, parallelism)

**Per-ticket pipeline (unchanged core, now fed by the knowledge layer):** fresh session per stage — write tests → implement via TDD → review → address review → PR. Fresh sessions per stage is the correct context-hygiene choice (avoids context rot accumulation). Each stage starts from the ticket brief + context pack, not a cold read.

**Deterministic gates:** lint, typecheck, tests, coverage — enforced by the harness, not the model. Use **PreToolUse hooks** to block edits to test files during the implement stage (anti-reward-hacking: the RHB concern about models weakening tests to pass). Keep a held-out test set the implementer never sees; use an opaque test runner. PreToolUse hooks fire even under `--dangerously-skip-permissions`, so they are the one reliable enforcement point.

**Reward hacking & judge bias defenses (from prior report, still apply):** different reviewer model + explicit rubric for the review stage (LLM-as-judge biases); block test-file edits; hold out tests; make the test runner opaque.

**Orchestration substrate:** a thin custom Python state machine over beads remains the right call versus LangGraph/Temporal/CrewAI — you need determinism, inspectability, and a state store you already have (`bd`), not a heavyweight framework. MAST's multi-agent failure taxonomy argues for fewer moving parts; the Agentless / "simple-scaffolds-beat-complex" line of research argues the same.

**Local model routing via LiteLLM:** route cheap subtasks (repo-map summarization, doc regeneration, retrieval distillation, commit-message drafting) to local models (e.g., Qwen3-Coder-Next, Devstral-2, Qwen 3.6-class) behind the LiteLLM proxy; reserve Claude for reasoning-heavy stages. Prompt caching on the stable prefix (CLAUDE.md + context pack) cuts cost materially. (Aider itself routes all providers through LiteLLM, a useful precedent.)

**Parallelization:** `bd` ready-queue → git worktrees (one per in-flight ticket) → optional container-use for isolation. Only independent tickets (no unmet deps) enter the parallel pool.

### Model / effort routing table

| Phase | Model tier | Effort | Rationale |
|---|---|---|---|
| Research (interview) | Opus-tier | high/xhigh | Cheapest in tokens, highest leverage; reasoning-dominated |
| Requirement critique / red-team | Opus-tier (different model than planner if possible) | high | Break anchoring; ambiguity detection |
| Architecture / plan authoring | Opus-tier | xhigh | Large planning-quality gap justifies frontier cost |
| Plan → ticket decomposition | Sonnet-tier | medium | Mechanical; small quality gap |
| Write tests (TDD) | Sonnet-tier | high | Correctness-sensitive |
| Implement | Sonnet-tier | high | Execution gap between Opus/Sonnet is small |
| Review | Different model + rubric | high | Judge-bias mitigation |
| Explore / retrieval | Haiku-tier or local (LiteLLM) | low | Isolation subagents; volume work |
| Knowledge-layer maintenance | Local model / script | n/a | Continuous, cheap tier |

**Rough pricing anchors circa mid-2026** (per million tokens, input/output; re-verify at build time): Opus-tier ~$5/$25; Sonnet-tier ~$3/$15 (intro $2/$10 through Aug 2026); Haiku-tier ~$1/$5; the top "Fable" tier ~$10/$50. Note Claude 4.7+ use a new tokenizer producing ~30–35% more tokens for the same text, so cross-generation per-token comparisons understate real cost.

**Set `effort` explicitly** in the SDK rather than relying on defaults — there is a community-reported bug (claude-agent-sdk-typescript issue #214) where a feature flag silently injected `effort: "medium"`, collapsing multi-turn agentic workflows to single-turn; pass `effort: "high"` (or the phase-appropriate level) explicitly, or set `CLAUDE_CODE_EFFORT_LEVEL`.

### Observability & failure handling
- Emit per-stage usage (tokens, cost, turns) from the SDK's usage reporting; log to the `bd` ticket.
- Persist every plan to a plans directory for audit ("check past plans to understand why specific decisions were made"; Claude Code's default is `~/.claude/plans`).
- Periodic **plan reminders** injected mid-execution measurably reduce plan drift (arXiv 2604.12147) — re-inject the plan/ADR summary at each fresh stage. The mechanism: as trajectories grow, the initial plan "must compete with an increasingly long history… which can make the plan less salient later in execution."
- On gate failure: bounded retries, then park the ticket back in `bd` with a failure note for human triage rather than infinite-looping (mirror the "fail-open" hook discipline and avoid Stop-hook infinite loops).

## Recommendations

**Stage 0 — Knowledge layer first (week 1–2).** Stand up Layer 1 (Aider repo map / RepoMapper + Serena) with a git post-commit hook and content-hash staleness detection. This is the foundation everything else consumes. *Benchmark:* a SessionStart context pack assembles in <5s and a stale-artifact gate correctly flags files changed since last index.

**Stage 1 — Research + Planning phases (week 2–4).** Implement `research.md` and `plan.md`/ADR artifact generation with Opus-tier + high effort, INVEST + premortem + devil's-advocate critique passes, and a *mandatory verification-read gate* before plan finalization. *Benchmark:* on 5 real features, planning catches ≥1 stale-abstraction or ambiguity per feature that would otherwise have surfaced in implementation.

**Stage 2 — Ticket handoff (week 4).** Wire plan→`bd` decomposition with pre-computed relevant-file lists per ticket, and bidirectional writeback (superseded ADRs). *Benchmark:* ≥90% of downstream stages start without a cold codebase exploration.

**Stage 3 — Integrate with existing per-ticket pipeline (week 5+).** Feed context packs into the existing test→implement→review→fix→PR stages; add plan-reminder re-injection and PreToolUse test-edit blocking. *Benchmark:* first-attempt gate pass-rate improves vs the no-plan baseline; measure rework tickets.

**Thresholds that change the plan:**
- If knowledge-layer maintenance cost (tokens for Layer 2 regeneration) exceeds the retrieval savings, cut Layer 2 to on-demand-only and keep Layer 1 (deterministic, ~free).
- If verification reads catch stale-context errors in <5% of plans, you may safely widen reliance on the knowledge layer; if >20% (near the DOCER baseline), tighten the drift gate and shorten the re-index interval.
- If Opus-at-plan-time cost isn't justified by reduced execution rework, fall back to Sonnet for planning and reserve Opus for only architecture decisions.

## Caveats
- **Alpha/fast-moving tooling.** DeepWiki, Serena, RepoMapper, and Claude Code's subagent/hook surfaces are evolving rapidly; several details here come from 2026 community write-ups and vendor blogs, not stable specs. Pin versions and re-verify hook stdout/injection semantics against the official Claude Code hooks reference before relying on them.
- **Model/version churn.** Specific model names and prices (Opus/Sonnet/Haiku/Fable tiers, `opusplan`) shift frequently; the Anthropic model-config page itself carries stale version numbers (it still references Opus 4.1/Sonnet 4 in examples). Treat the *routing pattern* as durable and re-check the *specific models* at build time.
- **Sycophancy is only partially mitigable.** Devil's-advocate and multi-model critique reduce but do not eliminate agreement bias; sycophancy is described in the literature as "a fundamental characteristic of current LLM architectures," so a human must still own the final architecture decision on high-stakes calls.
- **Stale context is the dominant residual risk.** No knowledge layer is ever perfectly fresh between commits; the verification-read gate is a mitigation, not a guarantee. Budget for the failure mode where a plan is built on an abstraction that changed underneath it.
- **Evidence hygiene.** The cited +7–10 pp (Probe-and-Refine) and +10.33 pp (CodeR) figures are from primary academic sources. Some widely-circulated blog "success rate" figures (e.g., a 23%→61% claim) appear to be conflated marketing numbers and are deliberately excluded from the evidence base above.