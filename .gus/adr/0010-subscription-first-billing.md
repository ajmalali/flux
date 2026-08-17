# 0010 — Subscription-first execution; API billing only via approved fallback

Status: accepted

## Context
The user runs gus on their normal Claude subscription (Claude Code CLI already logged in). The
Agent SDK spawns the Claude Code CLI, so it can ride the logged-in subscription auth. API-key
billing is metered per token and must not be engaged silently. Known policy risk: `--bare` mode
for `claude -p` requires an explicit API key and has been slated to become the `-p` default —
programmatic-use policy for subscriptions can shift under us.

## Decision
- The executor runs on subscription auth. **Preflight before every run:** verify the CLI is
  authenticated with the subscription and that no `ANTHROPIC_API_KEY` / `ANTHROPIC_AUTH_TOKEN`
  is being passed into the executor environment (strip them defensively).
- API billing is a fallback permitted only when one of:
  a. subscription auth is unusable (login broken, account issue);
  b. Anthropic policy changes break programmatic subscription use (e.g. `-p`/SDK starts
     requiring an API key) — detected by preflight, never assumed;
  c. the subscription usage limit is reached mid-run.
- **In every case the switch requires explicit user approval.** Default behavior on any trigger:
  stop, park in-flight tickets with a note, and surface the condition. `gus.toml` may carry
  `billing.allow_api_fallback = true` as durable pre-authorization (default `false`); condition
  (c) additionally always prompts unless that flag is set.
- On usage-limit hit (c) without approval: park tickets and schedule resume at the usage-window
  reset — the state machine makes this free (resume is rerun).

## Consequences
- Primary cost metrics are **tokens and usage-window consumption**, not dollars; `total_cost_usd`
  is recorded but demoted to an estimate that only matters in API-fallback mode.
- Per-stage/per-run caps are expressed as `max_turns` + token budgets, not `max_budget_usd`
  (that cap applies only when API fallback is active).
- "Different-model reviewer" means a different Claude tier within the subscription (e.g.
  implement on Sonnet, review on Opus). Cross-vendor review via LiteLLM is API-billed and sits
  behind the same approval gate.
- The A/B kill-criterion compares tokens + wall-clock + quality rather than dollar cost.
