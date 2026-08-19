# 0011 — Benchmark before machinery: re-sequenced scope and an amended A/B quality axis

Status: accepted

## Context
A 2026-08-19 review scored the repo against the six goals flux exists to serve: (1) automate
the deterministic layers of the workflow; (2) offload and rehydrate context between sessions,
keeping state on disk; (3) chunk work to the model's smart zone, continuing in a fresh
hydrated session when a chunk exceeds it; (4) route each ticket to the right model and effort;
(5) token efficiency and speed with quality held; (6) benchmarks proving the harness beats
vanilla Claude Code.

Findings: the substrate (gates, runner-verified evidence, checkpoints, hydration, executor
seam) serves goals 1–2 well. Goals 3–4 were scheduled last (M4, behind knowledge and planning
layers) and exist only as static per-stage routing. Goal 5 is structurally at risk: every
ticket pays five fresh sessions and three gate-suite reruns regardless of size, and the only
live pairing cost 1.41x vanilla's tokens. Goal 6 has infrastructure but no data, and its
quality axis is flawed: the ordinal is over the repo's gate suite, so a vanilla arm that
implements nothing keeps the suite green, scores maximum quality at near-zero cost, and can
win the pairing — the kill-criterion can fire against a harness that delivered. Separately,
the cross-stage prompt-cache benefit claimed for `PromptPack.stable_prefix` is mostly
illusory: the system prompt varies per stage and precedes user content, and stages run on
different models.

## Decision
1. **T5.5 (review bake-off) is cut.** Optimizing a stage whose existence has no supporting
   data is building ahead of evidence. Revisit only if the benchmark shows the review loop
   earning its cost.
2. **M2 (knowledge layer) and M3 (research/planning) are frozen.** Neither opens until the M1
   benchmark names the problem it solves as the binding constraint.
3. **The A/B quality axis is amended (refines ADR 0008):** both arms are judged by the same
   per-ticket held-out acceptance tests, written before either arm runs and stored outside
   both worktrees. "Repo gates green" alone is not quality.
4. **The M1 exit benchmark expands to 5–10 paired real tickets** on a real repo, on the model
   actually used for real work. The resulting table decides which stages and features survive.
5. **The pipeline becomes per-ticket configuration** (stage-list routing — goal 4 extended
   beyond model/effort): the five-stage pipeline is the default, not a constant.
6. **Smart-zone continuation is pulled forward as a runner feature** (goal 3 in minimal form):
   a stage that hits its token budget checkpoints partial progress into its artifact and
   continues in a fresh hydrated session; parking is the second resort, not the first.
7. **No cross-stage cache-hit claim may justify a design decision until it is measured.**

## Consequences
- Work order: T5.5a (quality axis) → T5.6 (expanded benchmark) → T5.7 (pipeline routing) →
  T5.8 (continuation). M4's decomposition follows; M2/M3 stay frozen until data reopens them.
- The likely end-state this sequencing accepts: gates + checkpoints + metrics + a configurable
  1–5 stage pipeline with per-ticket routing — and the wiki/research/planning layers possibly
  never built. Smaller than plan v2.1, closer to the goals.
- ADR 0008's kill-criterion stands, but no verdict computed before T5.5a lands is trusted.
