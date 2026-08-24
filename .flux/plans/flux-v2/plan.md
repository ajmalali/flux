# flux v2 — plan

Source of truth distilled from the Flux v2 Blueprint artifact (2026-08-20) and the
Session Ledger baseline (76 sessions, ~$1,292 est., Jun 30 – Aug 19). The pivot from
the v1 harness is recorded in `.flux/archive/v1/adr/0012-plugin-pivot.md`.

## What flux v2 is

A lean personal harness for Claude Code, shipped as ONE git repo that is both a
plugin and its own marketplace: deterministic machinery (a dependency-free CLI wired
to hooks) for everything that runs the same way every time, plus a small skill set —
five PAUL-derived lifecycle skills and a vendored mattpocock subset — for judgment
work. Observability is a SEPARATE ledger CLI that reads session transcripts from
outside; flux's only obligations to it are machine-readable state and unobstructed
transcripts.

## Design principles (binding)

1. **Deterministic-first.** Same-every-time steps are scripts invoked by hooks or
   thin skills; the model sees only filtered results. Skills hold judgment, never
   procedures a script could own.
2. **Budgets are enforced, not aspirational.** Everything flux injects has a hard
   byte budget the CLI itself refuses to exceed (tokens ≈ bytes/4).
3. **CLI over MCP.** One binary called via Bash. No MCP server, ever — MCP was the
   least reliable measured surface (26–46% error rates) and bloats the cached
   tool-definition prefix.
4. **Repo-agnostic via one adapter file.** All project specifics live in
   `.flux/flux.toml`; `flux init` detects Nx/Turbo/npm/cargo/uv. Nothing in the
   plugin knows about any particular repo.
5. **Every feature is falsifiable.** Each capability names the ledger metric it must
   move; two reporting cycles with no movement ⇒ delete it.

## Architecture

- **CLI** (`bin/flux`, single-file stdlib Python ≥3.9, on PATH while the plugin is
  enabled): `init` (+ `--scan`: inventory prior project state, write nothing) ·
  `prime` (SessionStart pack, ≤2k tokens, cold->1h warning, silent
  no-op without `.flux/`) · `state get|set|log|compact` (budget-enforced; an
  append-only `state.jsonl` union-merged by git — ADR 0002, 2026-08-24, replacing
  the rewritten `state.toml` that conflicted on every branch) · `check`
  (configured verification, failures-only) · `handoff` (generated, capped) ·
  `run -- <cmd>` (dedupe/elide output filter).
- **Hooks**: SessionStart → `flux prime`. Later, optional PostToolUse(Edit) →
  touched-project typecheck; a Stop hook only if a metric demands it.
- **Lifecycle skills** (Phase 02, PAUL-derived, all `disable-model-invocation: true`):
  `/flux:plan` (self-contained phase plan; stamps `routing: design|mechanical`),
  `/flux:audit` (adversarial pre-apply review in a subagent), `/flux:apply`
  (execute; delegate exploration; verify via `flux check` only), `/flux:wrap`
  (reconcile plan vs actual, state set, handoff, PR — one exit ceremony),
  `/flux:resume` (thin: read the primed pack, state next action, go).

  **Amendment, 2026-08-22 — the default path is `prime → apply → check`, one
  session.** Principle 5 fired on the four-session lifecycle: two reporting cycles,
  no movement. meridian-003 (4 tasks) and meridian-004 (m5, written specifically so
  a single pass would get it wrong) both ended with every arm delivering identical
  results, the lifecycle costing 2.8x and 2.9x, and its audit correctly catching a
  planted false claim that changed no outcome. `/flux:plan`, `/flux:audit` and
  `/flux:wrap` are **not deleted and not deprecated** — they become deliberate, for
  work that spans sessions, takes an irreversible step, or is still being argued
  about. `/flux:apply` no longer requires a plan path; `/flux:resume` routes to
  apply by default and to plan only on those three conditions.

  Two things this amendment does not claim. The ceremony's only real-work datapoint
  is positive (kiosk Phase 02's audit: three blocking findings on a plan that looked
  fine), and the benchmark **cannot** represent that case — its fairness rule forces
  complete briefs, and a complete brief is exactly where planning has nothing to
  recover. Full argument and the one experiment still available:
  `.flux/analysis/2026-08-22-ceremony-two-cycles.md`.
- **Adoption skill** `/flux:adopt` *(amendment, 2026-08-20 — not in the original
  blueprint)*: migrate whatever project knowledge a repo already carries (PAUL,
  agent-os, a hand-kept STATE/ROADMAP, or just a CLAUDE.md) into `.flux/`, then
  optionally retire the old framework by archiving it. Run once per repo. The split is
  the usual one: `flux init --scan` finds and sizes prior state deterministically and
  parses none of it; the skill decides what is still true. A framework-format parser in
  `bin/flux` is forbidden — that is the per-project fork this plan rules out.
  **Ledger metric:** median context per request. Adoption is what replaces a
  299 KB resume read with a ≤2k-token pack; if adopted repos don't move that number,
  the skill is theatre and goes.
  Retirement is opt-in, archives rather than deletes (`git mv` into
  `.flux/archive/<framework>/`), requires a clean tree, and is recommended only after
  one real phase has run on flux in that repo.
- **Vendored skills** (in, synced by `scripts/sync-vendored.sh`, pinned):
  wayfinder, to-spec, to-tickets, ask-matt, grill, review, and — added 2026-08-23 —
  research, writing-for-agents. Big-feature altitude:
  wayfinder → to-spec → to-tickets → /flux:plan per ticket.
  *(Amendment, 2026-08-23.)* The mattpocock-skills **install is retired**: it failed a
  pre-registered utilisation bar at ≥10.6x
  (`.flux/analysis/2026-08-23-mattpocock-utilisation-bar.md`). research and
  writing-for-agents were the only upstream skills with recorded use that flux did not
  already carry, so they were vendored to make the retirement capability-neutral, with
  `disable-model-invocation: true`. The rule this settles, and the one to reuse:
  **carrying a skill is nearly free; listing it is not** — so the case for keeping a
  capability is not the case for advertising it, and vendoring is what separates them.
  *(Amendment, 2026-08-23, later the same day.)* That open consequence is now closed by
  measurement (`.flux/analysis/2026-08-23-flux-listing-utilisation.md`). flux's listing
  was **one line, `flux:review`, 436 B = 109 tok/session**, and `flux:review` had been
  invoked **0 times in 520 transcripts**. Utilisation zero on both denominators, and the
  pre-registered trim empties the listing. **Caveat that must travel with this**: the bar
  is ambiguous for flux in a way it was not for mattpocock — read on a "any skill in the
  namespace" reading it would pass on the bench-inclusive denominator and trip the
  disagreement escape. The governing reading is "the skills it lists", tie-broken on the
  pre-registration's own words; the write-up names the off-ramp and the one-line revert. So `review` now carries
  `disable-model-invocation: true` too — applied in `sync-vendored.sh`, since upstream
  has no such key and a re-sync would otherwise re-list it. **Binding consequence:
  flux ships no model-visible skills.** All 14 are user-invocable only, and the only
  always-on context flux buys is `flux prime`, which is capped at 2,000 and pays off
  every session. A future skill gets a listing slot only with a written, falsifiable
  claim that the model must see it — the slot is not a default.
  Re-runnable at `scripts/skill-utilisation.py <namespace-prefix>`, which prints both
  readings; it also corrected the mattpocock figure to 6.7x (from 10.6x).
  Closed the same way, 2026-08-24: the **agent** roster (flux-explorer +
  flux-verifier, corrected to **505 B = 126 tok/session**) took the same bar and
  failed at **0.00% utilisation on both denominators** — 0 invocations in 273 billed
  sessions, and 0 in the whole 537-transcript corpus. With no
  `disable-model-invocation` equivalent, and trim/merge arithmetically unable to clear
  a zero denominator, **deletion was the only rung on the ladder**; both agents are
  gone (`--agents` mode, `.flux/analysis/2026-08-24-agent-roster-utilisation.md`).
- **Agents**: none. flux ships no agents and no model-visible skills; `prime` is the
  entire model-visible surface, and it is capped. Shipped in Phase 01 as
  flux-explorer (haiku/low) + flux-verifier (sonnet/low), deleted 2026-08-24 on the
  utilisation bar — `flux check`/`flux run --filter` already keep raw output out of
  context in code, and the built-in `Explore` agent was invoked 13 times in the same
  corpus where flux-explorer was invoked 0.
- **Model routing** only at session boundaries (prime surfaces the plan's routing
  stamp) and subagent boundaries. Never `/model` or skill `model:` mid-session.

## The benchmark (`bench/`) *(amendment, 2026-08-21 — not in the original blueprint)*

The falsifiability rule above was unenforceable: no feature could be killed for
failing to move a metric, because the metrics did not exist outside a one-off
ledger read. `bench/` is the rig that produces them — `fluxbench`, a stdlib
harness that runs one multi-task project end to end through several Claude Code
setups and reports the targets table below, per arm, alongside delivery rate.

- **Arms** differ in exactly three ways: seeded files, `--plugin-dir`, and the
  per-task prompt sequence. Model, effort, permission mode, denied tools, the
  starting tree and the grading suite belong to the runner. `Arm` has no model
  field and a test asserts it never gains one.
- **Six arms**: `vanilla`, `flux`, `flux-lite`, `paul`, `speckit`, `agentos`.
  `flux-lite` is the control *within* flux — same machinery, no lifecycle
  ceremony. If it beats `flux`, the four-session lifecycle is overhead and the
  falsifiability rule applies to it.
- **Corpus**: `projects/meridian`, a layered stdlib booking service (20 modules,
  41 tests) and four tasks that build on each other. Sessions are never resumed;
  carrying knowledge across a cold start is the arm's job and most of what flux
  is.
- **Quality axis** (inherited from v1's ADR 0011): held-out acceptance tests per
  task, written before any arm runs. An arm delivers only when its acceptance
  tests pass *and* the repo gate still passes, and no arm with zero deliveries
  may win a column. Each task also ships a reference implementation, and
  `run.py verify` asserts red-on-seed / green-on-reference before the corpus may
  judge anyone.
- **Out of the plugin's way**: run artifacts land in `~/.flux-bench/runs`, and
  third-party framework payloads in `~/.flux-bench/frameworks` — never in this
  repo, which ships by being copied.

Ledger metric it must move: all of them. This is the instrument, not a feature.

## Targets (ledger-measured; baseline = Aug 19 Session Ledger)

| Metric | Baseline | Target |
|---|---|---|
| Median context / request | 148k tok | < 80k |
| Cache-write share of spend | 29% | < 15% |
| Sessions > 150 requests | 19 (62% of $) | 0 |
| Model error rate (stale edit / unread file) | — | < 1.5% |
| Redundant re-reads / session | 3.4 | < 1 |
| Bash output volume / session | ~74k chars | < 25k |
| Est. $ / completed phase | ~$45 | < $25 |
| Quality guard (PR pass-rate, audit findings, tests) | — | no regression |

> **The tool-error row used to be friction, not quality** (found 2026-08-22,
> `.flux/analysis/2026-08-22-context-decay.md`): 57% of the errors it counted were
> permission prompts and blocks — the operator's allowlist warming up, not the model
> being wrong — and they cluster at session start. `bench` now classifies every failed
> tool result (`fluxbench.decay.classify_error` → `error_bucket`) and reports two
> columns: **model err**, the failures that are evidence the model's picture of the
> code was wrong (a stale edit string, an unread file), which is the row above and
> carries the target; and **friction**, approval prompts and blocks, which is reported
> without a target because it measures the operator, not the arm. Failing commands (a
> test exiting 1) are in neither. The 3.2% baseline was the old pooled number and is
> withdrawn — the first classified run sets the new one.

## The execution index (`flux task`) *(amendment, 2026-08-22 — not in the original blueprint)*

Recorded in `.flux/adr/0001-execution-frontier.md`, which opens the v2 ADR line.

The big-feature altitude above (wayfinder → to-spec → to-tickets → `/flux:plan` per
ticket) is declared but has no spine. `/flux:plan` writes the *first* phase and says to
split the rest into sequential plans — so the decomposition of everything after it
lived in the planning session's context and died with it. What crosses the boundary is
`state.toml`: five prose fields and a 2000-token budget, with no ledger of what is
done, no edges, and no remainder. Every cold session therefore **re-derives the
frontier by reading**, which is both where the context goes and the opposite of
deterministic. `bin/flux` cannot read a single ticket file `to-tickets` writes.

Principle 1 resolves it. *What the tasks are* is judgment and stays in the skills.
*Which task is next* is a topological sort over a DAG — the most procedural operation
in the system, and the only one never moved into the CLI.

- **CLI surface**: `flux task add|start|done|block|next|list`, over a local store
  under `.flux/`. The model calls verbs; it never hand-edits the file, exactly as with
  `flux state set`. `flux task next` returns the next unblocked task deterministically.
  `flux prime` surfaces the current task and counts — never the graph.
- **Task size is refused, not advised.** `wayfinder` already sizes tickets to "one
  100K token agent session" and nothing checks it; an unenforced budget is a comment.
  `flux task add` estimates context from declared files plus fixed overhead and refuses
  over `[task].budget_tokens` (principle 2).
- **Ceremony scales with size.** A single small task runs apply-only; plan / audit /
  wrap attach to phase and feature boundaries. This is the honest reading of
  `meridian-003`, where `flux-lite` matched `flux` 4/4 at 2.8x less cost **on a corpus
  whose every task fits one session** — the regime where decomposition machinery has
  nothing to decompose and can only appear as overhead.
- **Done is recorded, not asserted.** `flux task done` requires what verified it;
  `/flux:wrap` reconciles claims against records.

**Ledger metrics.** Execution index → cold-start ramp (tokens and tool calls before a
session's first `Edit`/`Write`); if the ramp does not shrink, the frontier was not
where context went and it goes. Size budget → **re-read rate above the threshold**
(`./bench/run.py decay`); if sizing tasks under the budget does not lower it, the
budget goes. *(Amended 2026-08-22 from "held-out acceptance pass rate as a function of
context at execution" — see the Prerequisite below: the corpus cannot measure that.)* Size-conditional ceremony → $ and sessions per delivered task on small work;
must converge to `flux-lite` there. Verified-done → rate of tasks marked done that fail
their own `verify` on replay.

**Prerequisite — done 2026-08-22, and the premise did not survive.**
`.flux/analysis/2026-08-22-context-decay.md`; 414 transcripts, 16,909 tool calls.
**There is no knee.** Correctness (Edit failing on a stale string or an unread file)
is flat within a model family across 75k → 300k+; the pooled 2.9x that looks
significant is Simpson's paradox, since sonnet/haiku sessions never exceed 200k. What
does rise is **re-orientation**: re-reading a file already among the last five read
roughly triples across ~100k, holding within-session at every cut (sign-test p=0.09 at
200k). Naive file churn rises only because the touched set grows, and 57% of raw tool
errors are permission friction that clusters at session start — both proxies are
unusable as originally specified. So a long context costs **re-reading, not
correctness**, the budget **warns rather than refuses** (ADR 0001 rule 2, amended),
and the threshold if one is set is ~100k. The correctness question is deferred to a
designed run: detecting the observed difference needs ~14x the data this account has,
so no amount of further mining answers it. **This targets table must not assert that
quality decays with context until such a run exists.**

**Consequence for `bench/`.** A pre-decomposed corpus tests decomposition machinery not
at all — the flaw that left `meridian-003` unable to speak to any of this. The corpus
must be handed over whole, each arm left to decompose it, and graded continuously so
the result is a quality-per-context curve rather than a single cell.

## Where flux pays *(amendment, 2026-08-23 — not in the original blueprint)*

The blueprint assumed flux was a general win and that adoption was a packaging
problem. Two measured repos say otherwise: **flux's value is repo-shaped.**

| repo | `STATE.md` | median frontier / session | prime's ceiling |
|---|---:|---:|---:|
| zaps/kiosk | 299 KB, read whole | 6 calls / 15,770 tok | large — measured 1 / 51 |
| zaps/api | 33 KB, mostly unread | 2 calls / **1,111 tok** | ~2% of a 49,769-tok ramp |

`flux prime` pays where a repo has **a bloated state artifact that sessions read
whole**. kiosk had one; api did not. Installing into api to capture 2% and then
reporting it as generalization would be the same defect as ticking a target on
missing data — so api gets a clean tree and no install
(`.flux/analysis/2026-08-23-api-preprime-baseline.md`).

**This bounds the product claim**, which is more useful than a forced install: flux
is for repos with a heavy resume read and a noisy gate, not for every repo on the
machine. Adoption is a measurement, not a rollout.

### The one unmeasured surface, and its pre-registered bar

There is a second plausible claim — `flux check`'s **filtered gate** (in kiosk it
turned ~950 raw lines into one). It is genuinely unmeasured: the ramp analysis
structurally cannot see it, because verification output lands *after* the first
edit, outside the ramp window.

It gets the same discipline the frontier got, and the bar is fixed **before** the
number is looked at, because reaching for a fresh justification the moment the old
one dies is exactly the failure mode ADR 0001 already fell into:

- **Metric**: median tokens of lint/test/build tool-result output landing in context
  per api session (the `Bash output volume / session` row above, scoped to the gate).
- **Bar**: **median > 5,000 tokens/session** ⇒ install flux in api for `flux check`
  alone, and report against this metric, never the ramp.
- **Below the bar** ⇒ api stays clean, and Phase 03's conclusion is recorded as
  "flux does not generalize to api, and here is exactly why."
- Either way the frontier claim stays spent. `flux prime` is not re-justified by
  this measurement.

**Measured the same day, and the bar was not cleared.** Gate output per api session:
**median 2,166 tok** among the 8 of 19 sessions that ran it at all, **median 0** over
all 19 (p90 4,410). api's jest/eslint are already terse — no gate run appears in the
corpus's fifteen largest Bash results. kiosk's `nx run-many` fans out over 31 projects
/ 83 tasks and emits ~950 lines regardless; the filter is worth a lot against a
fan-out runner and nearly nothing against a plain `npm test`.

**So api is not adopted, and Phase 03's api line is closed as a null.** flux has two
measurable surfaces and api has the wrong shape for both. Full working:
`.flux/analysis/2026-08-23-api-preprime-baseline.md`.

## Phases

- **00 — baseline & decks** *(user-side, outside this repo)*: freeze the Aug 19
  ledger as baseline.json; global config quick wins (vercel/pyright plugins off by
  default, codegraph hook capped, carl-mcp retired, default model Opus 5).
- **01 — core CLI + plugin scaffold** *(this repo)*: bin/flux, hooks, manifests,
  agents, vendored skills, tests. Adopt in zaps/kiosk (PAUL untouched; prime simply
  replaces the resume read).
- **02 — skills**: write the five lifecycle skills from the PAUL originals
  (in zaps/kiosk); migrate kiosk's PAUL state into `.flux/` (archive `.paul/`);
  run one full real phase (plan → audit → apply → wrap) on flux v2 in kiosk.
- **03 — establish where flux pays** *(rescoped 2026-08-23; was "package &
  generalize")*: install via marketplace on every machine; retire the competing
  framework installs; first before/after ledger comparison, taken **in kiosk**,
  where a measured delta exists. **Adopting zaps/api is no longer part of it** —
  see "Where flux pays" below. The original phase assumed the kiosk win
  generalized; it does not, and the boundary is the finding.

## Out of scope

Observability (separate ledger CLI) · MCP server · ticket store\* · decision log ·
auto-commit/auto-fix · per-project plugin forks.

\* **Qualified 2026-08-22 by ADR 0001.** What stays out is a *tracker*: an artifact
humans plan against, synced to GitHub or Linear, curated by the model, holding
discussion and history. What is now in is a local **execution index** — id, status,
blocking edges, files, verification — that only the CLI and a cold session read, never
synced, written through CLI verbs rather than edited. Tickets for people keep living in
the tracker `to-tickets` and `wayfinder` publish to.
