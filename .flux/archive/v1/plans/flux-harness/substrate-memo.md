# Substrate decision memo (T1 / Pre-M0, plan.md §5)

Date: 2026-08-17 · Spikes executed hands-on (option a) · Revisit **only at phase gates**.

## Decision

**Keep custom Python** as the orchestration substrate (thin state machine per design.md),
with two adoptions from the spikes:

1. **beads molecules are adopted as the per-ticket pipeline container** (positive B2
   assessment, below) — the 5-stage pipeline is poured from a bd formula at ticket-creation
   time; the flux runner drives ready→claim→execute→close. This complements, not replaces,
   the `.flux/state/` checkpoint layer (ADR 0002 amendment candidate at M4/D2).
2. **Steal Archon's run-logging model for A2** (metrics): an append-only per-run event log
   where every `node_completed` event carries `{duration_ms, tokens{input,output},
   cost_usd, num_turns, node_output-preview}` — this maps 1:1 onto the planned
   per-(ticket, stage) JSONL metrics store, and validates the design.

Neither Archon nor Gas City is adopted as the substrate. Both are credible and both were
run hands-on; both fail the same scorecard point the default hypothesis predicted (dynamic
per-ticket exec config), and each fails an additional fit test (below).

## Spike setup (what was actually run)

- **Archon 0.9.0** (Homebrew, compiled binary + `CLAUDE_BIN_PATH`): two-stage workflow
  `flux-spike.yaml` in a scratch repo — bash node reading `bd show <ticket> --json`
  metadata → implement (prompt node, per-node `model`/`effort`) → deterministic pytest
  gate (bash node, JSON verdict) → `when:`-guarded bounded fix loop (`until` signal,
  `max_iterations: 2`, fresh context) → `when:`-guarded review stage. **One full live run
  end-to-end on subscription auth**, including a genuine gate failure (missing pytest)
  that triggered the fix loop, which repaired the environment, emitted the completion
  signal after 1 iteration, and handed off to review (APPROVE). Plus a zero-token
  workflow proving `when:` false → node skipped.
- **Gas City 1.4.1** (Homebrew; requires tmux+dolt+bd+flock, installs a **launchd
  supervisor service**): city initialized (minimal template + Claude Code), scratch repo
  adopted as a rig (`gc rig add --adopt`), v2 formula with `[steps.check]` pytest gate
  (`max_attempts: 2`), `condition`-guarded review stage, `--var` parameterization.
  Verified: compile preview both var settings, cook into real beads, readiness gating in
  the shared bd store, check-gate config on the step bead. Live run slung to the mayor —
  see runtime observation below.
- **beads (bd) 1.2.1** (Homebrew, pin `1.x`): ticket carrying exec-config metadata
  (`{"model": …, "effort": …, "skip_review": …, "max_fix_iters": …}`) read by both
  substrates; molecules assessed hands-on (below).

## Scorecard (plan.md §5 Pre-M0, B1)

| # | Criterion | Archon 0.9.0 | Gas City 1.4.1 | Custom Python (design.md) |
|---|---|---|---|---|
| 1 | Per-ticket config from beads | **Partial.** A bash node reads `bd show --json`; `when:` can branch on any metadata field. But YAML config fields are *not* substitution surfaces: `model: "$read-config.output.model"` is sent to the API as a literal string (404 `model_not_found`, observed). Per-ticket model/effort requires one duplicated `when:`-guarded node per model, or generating YAML per ticket. | **Partial.** `--var` at sling time parameterizes titles/descriptions/metadata (enum-validated, stamped as `gc.var.*` on beads — clean). But model/effort attach to *agents* (`option_defaults`), selected via per-step `gc.run_target` routing — per-ticket model = pre-provisioned agent per model tier. And `check.max_attempts` is a typed int: var substitution rejected at parse (observed). | **Yes by construction** — `ExecConfig` is computed per ticket in Python; model/effort/max_iters are just values. |
| 2 | Conditional stage skip | **Yes.** `when:` on upstream JSON output; skip observed both directions (`when_condition` skip + fix-loop trigger on gate fail). | **Yes.** `condition` + vars, resolved at instantiation (= ticket-dispatch time); skipped step dropped from the graph and downstream `needs` rewired (observed in compile preview). | **Yes** — `next_stage()` transition function. |
| 3 | Bounded fix loop | **Yes.** Loop node: `until` completion-signal + `max_iterations` hard cap; exhaustion **fails** the node/workflow (flux wants *park*; `workflow resume` exists but park-with-note is not native). Observed live: loop entered on gate fail, exited on signal after 1/2 iterations. | **Yes (strongest design).** `[steps.check]`: orchestrator (never the agent) runs an exec script after each attempt; fail + budget → next iteration bead; exhaustion → step failed, downstream blocked. Bound is static per formula (typed int, not per-ticket). Verified to the bead level: `gc.check_mode/check_path/max_attempts` on the step, iteration scaffolding compiled. | **Yes** — loop keyed on beads state, `max_review_iters` from ticket config, park-with-note per design.md. |
| 4 | Per-stage cost surfacing | **Yes.** Per-node `tokens{input,output}`, `cost_usd`, `num_turns`, `duration_ms` in the run event store (sqlite) + dashboard; `maxBudgetUsd` per-node cap. Not printed by the CLI text output — DB/dashboard only. USD-denominated (ADR 0010 wants tokens+window; tokens are present). | **Yes (design).** `gc costs` aggregates `.gc/usage.jsonl` (model tokens + compute wall-seconds) per run, flags unpriced runs; pricing overrides configurable. Not observed live (run did not complete within the spike timebox). | **Yes by construction** — metrics JSONL per (ticket, stage) is M0 scope (ADR 0008), token-denominated per ADR 0010. |

Auxiliary observations:

- **Subscription auth (ADR 0010):** Archon rode the logged-in Claude subscription natively
  (`authMode: global`, five-hour rate-limit window and overage status visible in run logs —
  useful signal to park on limit-hit). Gas City spawns the `claude` CLI in tmux, so it also
  rides subscription auth by construction.
- **Footprint:** Archon = single binary + sqlite in `~/.archon` (worktree isolation needs a
  git remote; `--no-worktree` works). Gas City = tmux + dolt + flock + launchd supervisor
  daemon + controller/API server + agent sessions; `gc init` is wizard-interactive. It is a
  *city* — a persistent multi-agent runtime — not a per-ticket pipeline runner.
- **Archon loop-exhaustion semantics** are fail-the-workflow; flux's park-with-note +
  `bd`-visible resume would have to be built around it (resume exists, park reason doesn't).
- **Both tools are pre-1.0/young** (Archon 0.9.0; Gas City 1.4.1 but the packs/doc canon is
  actively migrating), matching plan.md §6's churn-risk note.

## Why custom still wins (the decision rationale)

The default hypothesis survived contact with both tools, for the predicted reason:
**the flux pipeline is dynamic exactly where declarative substrates are static.** Per-ticket
`ExecConfig` (model, effort, max iterations, stage skip) is first-class data in flux's
design; in both substrates half of it lives outside the declarative surface (Archon: config
fields not templatable; Gas City: model-per-agent-role, typed loop bounds). Both would push
flux into either config-explosion (node/agent variants per model tier) or YAML/TOML
generation — at which point Python generating a DSL is strictly worse than Python running
the loop. Park semantics (ADR 0005: park-with-note, resume from beads) and
artifact-validation-with-one-retry are also custom behaviors neither engine natively has.

What the spikes changed: the runner should treat **beads molecules as its pipeline
container** (B2 below) and adopt Archon's event-log shape for metrics. The executor seam
(ADR 0007) stays — if Archon's engine matures templatable config, swapping the *runner*
for it later touches the runner module, not the stages.

## B2 — beads 1.x molecules assessment: **positive**

bd 1.2.1 (pinned `1.x`, Homebrew) natively expresses the 5-stage pipeline **without Gas
City**: a formula in `.beads/formulas/flux-pipeline.formula.toml` (tests → implement →
review → fix → pr, `{{ticket}}` var, human gate on pr) was written, `bd formula show`
compiled it, and `bd mol pour --var ticket=…` instantiated **7 beads**: root molecule +
5 steps with dependency-gated readiness (only `tests` ready; rest pending) + the human
gate as its own bead. `bd mol current/progress` tracks position; `bd mol ready` finds
gate-resume work; wisp/squash/burn manage ephemeral instances and digests.

Limits: molecules are *state*, not execution — nothing runs steps or evaluates exec-check
gates (bd gate types: human/timer/gh:run/gh:pr/bead — no arbitrary command). The bounded
review↔fix loop and artifact validation remain flux-runner logic. That division (bd = state
+ readiness + gates; flux = execute + validate + park) is exactly ADR 0002's shape.

Feeds D2 (M4): attach the stage molecule at ticket-creation time; the runner's
`next_stage()` can be *derived from* `bd mol current` instead of a parallel checkpoint
file — evaluate at M4, keep `.flux/state/` authoritative until then.

## Gas City runtime observation (timebox note)

The full agent-topology leg (mayor session materialization in tmux, step dispatch through
the controller) **did not complete within the timebox**: the `minimal` init template left the
mayor's provider unwired (`unknown provider: provider is required; set agent.provider or
workspace.provider`), so the slung workflow sat with 0/4 agents running and the mayor
`reserved-unmaterialized`; no tokens were spent. The stall is itself signal — the day-one
config surface (wizard → city.toml → providers → roles → remote packs → supervisor) is
large for a single-developer loop. Within the half-day timebox this was bounded
deliberately: the orchestration-layer evidence (compile, cook, readiness, check-gate
metadata, routing metadata) was sufficient to score all four points, and the runtime is
the part whose weight (supervisor daemon, tmux fleet, dolt) already argues against
adoption for a single-developer per-ticket loop regardless of whether it runs.

## Revisit rule

Per plan.md §5: this decision is revisited **only at phase gates** (milestone exits). The
concrete triggers that would reopen it: (a) Archon ships templatable config fields
(per-ticket model from node output), or (b) flux's scope grows to multi-agent fleets/pools
(Gas City's actual sweet spot), or (c) beads molecules gain exec-check gates that could
replace the runner's gate loop.

## Cleanup / repro

Spike artifacts live in the session scratchpad (`spike-target/`, `spike-city/`), not in
this repo. Gas City's launchd supervisor (`com.gascity.supervisor`) and city registration
were removed at spike end; Archon leaves `~/.archon` (sqlite + workspaces). beads 1.2.1
stays installed and pinned for M0.
