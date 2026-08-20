# flux-v2 — status & next task

Updated: 2026-08-20 (v2 pivot session: v1 retired at tag `v1-final`, Phase 01 built)

## Current state

- **The pivot is executed.** v1 (Python orchestration harness) is archived: tag
  `v1-final`, docs under `.flux/archive/v1/`, rationale in ADR 0012 there. This repo
  is now the flux v2 plugin + self-marketplace described in `plan.md`.
- **Phase 01 core is in and green.**
  - `bin/flux` — single-file stdlib CLI (Python ≥3.9, tomllib fallback parser):
    init/prime/state/check/handoff/run, budgets enforced (tokens ≈ bytes/4),
    prime is hook-safe (never fails, silent no-op without `.flux/`, cold->1h note).
  - Plugin scaffold: `.claude-plugin/plugin.json` + `marketplace.json` (self-market
    via `"source": "./"`); `hooks/hooks.json` SessionStart → `${CLAUDE_PLUGIN_ROOT}/bin/flux prime`.
  - `agents/flux-explorer.md` (haiku/low), `agents/flux-verifier.md` (sonnet/low).
  - Vendored skills: wayfinder, to-spec, to-tickets, ask-matt, review, grill
    (grill = wrapper + grilling/domain-modeling as `references/`), synced by
    `scripts/sync-vendored.sh`, pinned to mattpocock-skills 1.2.3
    (claude-plugins-official commit 2ab9580…), MIT attributed in `skills/VENDORED.md`.
  - 23 tests, `python3 -m unittest discover -s tests`, all passing; dogfooded on
    this repo (`.flux/flux.toml` check = the unittest run; prime/state/check verified live).
- **Not yet done in Phase 01:** installing the plugin (`/plugin marketplace add`)
  on this machine and adopting in zaps/kiosk; Phase 00 global-config quick wins are
  the user's, outside this repo.

## Task queue

- [ ] Install the plugin from this repo (`/plugin marketplace add ~/Dev/flux` or
      push + `ajmalali/flux`), restart, confirm SessionStart prime fires here and
      fast-no-ops in a non-flux repo.
- [ ] Adopt in zaps/kiosk: `flux init`, set state from current PAUL position; PAUL
      untouched (prime replaces the `/paul:resume` read).
- [ ] Phase 02 — write the five lifecycle skills. **Source needed:** PAUL originals
      live in zaps/kiosk (not in ~/.claude); read them there before writing
      plan/audit/apply/wrap; resume is thin and can be written from plan.md alone.
- [ ] Phase 02 — migrate kiosk PAUL state into `.flux/`, archive `.paul/`.
- [ ] Phase 02 — one full real phase (plan → audit → apply → wrap) in kiosk.
- [ ] Phase 03 — generalize (zaps/api), retire PAUL/mattpocock installs, first
      ledger before/after.

## Session-close checklist (execute at the end of EVERY working session)

1. `flux check` green (or the failure documented here).
2. `flux state set` — phase/position/next reflect reality.
3. Update this file: current state, queue, anything a fresh session must not re-derive.
4. Commit (docs included). Never leave the repo dirty across sessions.
