# ADR 0012: flux v2 — plugin + CLI, harness retired

Date: 2026-08-20
Status: Accepted (closes the v1 ADR line; v2 decisions live in `.flux/plans/flux-v2/plan.md`)

## Decision

The v1 orchestration harness — a Python state machine that drove Claude Code through
fresh-session stages via the Agent SDK — is retired at tag `v1-final`. flux v2 is a
Claude Code **plugin** (skills + hooks + agents) wrapping a **dependency-free CLI**,
built to the Flux v2 Blueprint (2026-08-20). This repo is rewritten in place; v1
survives in git history and under `.flux/archive/v1/`.

## Why

1. **Wrong competition.** A full harness re-implements the agent loop that Anthropic
   ships and improves weekly. flux's edge was never the loop; it was determinism around
   the loop — priming, verification, state, handoffs. That layer needs no SDK.
2. **The evidence pointed the same way.** ADR 0011's direction review found the
   sequencing wrong and goal 5 (token efficiency) structurally at risk: five fresh
   sessions + three gate reruns per ticket, 1.41x–4.49x vanilla token cost on live
   pairings. The Session Ledger baseline (76 sessions, ~$1,292 est.) showed 85% of
   spend is context traffic — fixed by smaller, stabler prefixes and deterministic
   filtering, not by more orchestration.
3. **The kill-criterion spirit applies to the harness itself.** ADR 0008 promised to
   freeze feature work when vanilla wins. Rather than wait out the streak, the
   conclusion is taken now, at the architectural level.

## What carries forward

- ADR 0006: everything flux owns lives under `.flux/`; single `flux` namespace.
- ADR 0010: subscription-first; flux never configures API-key billing.
- ADR 0005's spirit: deterministic verification is the authority (`flux check`).
- The measurement discipline of ADR 0008/0011: every v2 feature names the ledger
  metric it must move, and is deleted after two unmoved reporting cycles.

## What is dropped

Executor seam, stage pipeline, checkpoint/transition machinery, A/B arms, metrics
store, repo-map packs, beads/ticket coupling, MCP anything. Observability moves to a
separate ledger CLI that reads session transcripts from outside.
