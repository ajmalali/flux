# flux

Deterministic session machinery for Claude Code — one repo that is both a plugin and
its own marketplace: a dependency-free CLI (`bin/flux`) wired to hooks, plus a lean
skill set. v2, rebuilt 2026-08-20; the v1 orchestration harness is archived at tag
`v1-final` and `.flux/archive/v1/` (pivot rationale: ADR 0012 there).

## Session bootstrap (do this first, in order)

1. Read `.flux/plans/flux-v2/status.md` — current state, task queue, session-close
   checklist. Do the first unchecked task unless the user says otherwise.
2. `.flux/plans/flux-v2/plan.md` pins the binding design: principles, CLI surface,
   skill roster, targets table, phases. Don't contradict it silently — amend it.

## Conventions (binding)

- **`bin/flux` stays single-file, stdlib-only, Python ≥3.9 compatible** (no
  3.10+ syntax; tomllib is optional via fallback). It rides the plugin's PATH and a
  SessionStart hook — no dependencies, no install step, ever.
- **Budgets are enforced in code.** Anything flux emits into model context or stores
  as state has a byte cap (tokens ≈ bytes/4) that the CLI refuses to exceed. Never
  add an uncapped output path.
- **`flux prime` must never fail and never nag**: silent no-op wherever `.flux/`
  is absent (user-scoped hooks fire in every repo).
- **No MCP, no SDK.** flux talks to nothing programmatically; it is invoked by hooks
  and Bash. Skills contain judgment only; procedures live in the CLI.
- **Vendored skills** — `grill` is the only one (the four lifecycle skills
  plan/audit/apply/wrap and `adopt` are flux's own) — are frozen copies, edited only
  through `scripts/sync-vendored.sh` (pin + rewrites), MIT-attributed in
  `skills/VENDORED.md`.
- Gate on this repo: `python3 -m unittest discover -s tests` (also wired as
  `flux check` here). It must pass before any commit.
- Everything flux tracks as project docs lives under `.flux/`; skill frontmatter
  keeps `disable-model-invocation: true` for lifecycle skills.
- flux runs on the user's logged-in Claude **subscription**; never configure or
  suggest API-key billing.
- **Every feature is falsifiable**: name the ledger metric it moves (plan.md
  targets table); two unmoved reporting cycles ⇒ delete it.
- End every working session by executing the session-close checklist in
  `.flux/plans/flux-v2/status.md` — an unupdated status.md means the session's
  knowledge is lost.
