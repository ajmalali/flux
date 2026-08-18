# 0005 — Deterministic gates + environment hardening over LLM judgment

Status: accepted

## Context
Pre-written tests + "make these pass" is a known reward-hacking target. LLM-as-judge carries
self-preference, verbosity, and position bias. RHB (arXiv 2605.02964) shows simple environmental
hardening cuts exploit rates ~88% with task success statistically unchanged.

## Decision
- Lint/typecheck/test/coverage gates are subprocess calls run by the harness; the model never
  self-certifies anything a machine can check.
- Hardening: opaque test runner (pass/fail + minimal diagnostics), `PreToolUse` hook (exit 2)
  blocks test-file edits during implement, held-out tests the implementer never sees, red-step
  confirmation that new tests fail for the right reason.
- The LLM reviewer is advisory, runs on a *different model* with a structured rubric, judges only
  what machines cannot (design, readability, edge-case coverage), and sits downstream of gates.
- Bounded loops everywhere: max 3 review iterations, then park the ticket for human triage.
- CI on the branch is the merge authority; never auto-merge on agent say-so.

## Consequences
- Slightly more plumbing (opaque runner, hook scripts) in exchange for structural — not
  behavioral — safety against test-gaming and judge bias.
