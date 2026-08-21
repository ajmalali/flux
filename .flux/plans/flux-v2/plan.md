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
  no-op without `.flux/`) · `state get|set` (budget-enforced TOML) · `check`
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
  wayfinder, to-spec, to-tickets, ask-matt, grill, review. Big-feature altitude:
  wayfinder → to-spec → to-tickets → /flux:plan per ticket.
- **Agents**: flux-explorer (haiku/low), flux-verifier (sonnet/low).
- **Model routing** only at session boundaries (prime surfaces the plan's routing
  stamp) and subagent boundaries. Never `/model` or skill `model:` mid-session.

## Targets (ledger-measured; baseline = Aug 19 Session Ledger)

| Metric | Baseline | Target |
|---|---|---|
| Median context / request | 148k tok | < 80k |
| Cache-write share of spend | 29% | < 15% |
| Sessions > 150 requests | 19 (62% of $) | 0 |
| Tool error rate | 3.2% | < 1.5% |
| Redundant re-reads / session | 3.4 | < 1 |
| Bash output volume / session | ~74k chars | < 25k |
| Est. $ / completed phase | ~$45 | < $25 |
| Quality guard (PR pass-rate, audit findings, tests) | — | no regression |

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
- **03 — package & generalize**: install via marketplace on every machine; adopt in
  zaps/api and this repo's own sessions (`/flux:adopt`, shipped 2026-08-20); retire
  PAUL + mattpocock install once parity is proven; first before/after ledger
  comparison.

## Out of scope

Observability (separate ledger CLI) · MCP server · ticket store · decision log ·
auto-commit/auto-fix · per-project plugin forks.
