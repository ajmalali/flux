# flux

**F**ast **L**oop **U**nified e**X**ecution — a deterministic orchestration harness around
Claude Code (Python CLI, run inside target repos).

Status: M0 complete; M1 in progress — executor seam, metrics store, runner spine, gates, repo
map, the A/B baseline, and the `tests` + `implement` stages are in. Review, fix and pr are not.

## Session bootstrap (do this first, in order)

1. Read `.flux/plans/flux-harness/status.md` — current state, task queue, session-close checklist.
   Do the first unchecked task unless the user says otherwise.
2. Before writing runner/stage/executor code, read `.flux/plans/flux-harness/design.md` — it pins
   the binding contracts: state machine, `Executor` protocol, artifact-handoff rules, stage I/O
   table.
3. `.flux/plans/flux-harness/plan.md` (v2.1) holds milestones and exit benchmarks.
   `.flux/adr/` holds binding decisions — never contradict an ADR silently; amend or supersede it
   with a new ADR.

Only pull `.flux/research/` files when a task's rationale is genuinely unclear; they are source
material, not instructions.

## Conventions (binding)

- Everything flux generates or tracks as project docs lives under `.flux/` (ADR 0006). Code in
  `src/flux/`, tests in `tests/`.
- Python ≥3.12, `uv`-managed. Gates on this repo: `uv run ruff check .`, `uv run pyright`,
  `uv run pytest`. All three must pass before any commit.
- Only `src/flux/executor/` may import `claude_agent_sdk` (ADR 0007). Stage/runner code depends
  on the `Executor` protocol only.
- Model and effort are always explicit in `ExecConfig` — never rely on SDK defaults.
- flux runs on the user's logged-in Claude **subscription**. Never configure or suggest API-key
  billing except through the approved fallback ladder in ADR 0010 (requires user approval).
  Executor code must strip `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN` from child environments.
- Milestone exit benchmarks (plan.md §5) gate advancement: do not open new scope while the
  current milestone's benchmark is unmet.
- End every working session by executing the session-close checklist in status.md — status.md is
  the handoff artifact that makes the next fresh session possible; an unupdated status.md means
  the session's knowledge is lost.
