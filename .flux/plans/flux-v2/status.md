# flux-v2 — status & next task

Updated: 2026-08-20 (later session: the five lifecycle skills written — 55 tests green)

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
  - 36 tests, `python3 -m unittest discover -s tests`, all passing; dogfooded on
    this repo (`.flux/flux.toml` check = the unittest run; prime/state/check/run verified live).
  - **Check-candidate flow shipped (2026-08-20):** `flux init` writes
    `verified = false` under `[check]` and prints "check candidate: … run `flux check`
    once to validate"; the first full `flux check` pass flips the stamp in place
    (byte-preserving regex edit), failures while unverified warn that the command has
    never passed here, and `flux prime` shows `[unverified — run it once]`. Configs
    without the key (legacy) are untouched. This repo's own flux.toml stamp flipped
    live on this session's gate run.
  - **`flux run --filter` shipped (2026-08-20):** `flux run [--tail N]
    [--filter elide|failures|tail:N|raw] -- <cmd>`. `elide` is run's own head+tail
    squeeze (the previous, still-default behaviour); `failures`/`tail:N`/`raw` are
    `check`'s filters reused verbatim (`apply_filter`), so a scoped test run costs
    the same context as the gate. Default comes from `[run].filter` (new key in the
    init template, `"elide"`); the flag beats config; an unknown flag value is a
    usage error (exit 2), an unknown config value warns on stderr and falls back to
    elide. Summary line now reports the mode: `[flux run: 200 -> 40 lines,
    filter=failures, exit 0]`.
  - **Plugin installed & prime verified live (2026-08-20):** installed as
    `flux@flux-market` v2.0.0 from a **directory-source** marketplace
    (`known_marketplaces.json` → `{"source": "directory", "path": "/Users/ajmalali/Dev/flux"}`).
    After restart the SessionStart hook fired in this repo and rendered the prime pack
    (phase/position/next/routing/check); run from a directory with no `.flux/` it
    printed nothing and exited 0 — the hook-safe no-op holds in the real harness.
    The `flux:` namespace also resolves (skill `flux:review`, agents
    `flux:flux-explorer` / `flux:flux-verifier` appear in the session roster).
  - **Gotcha — the install is a COPY, not a symlink.** Despite the directory source,
    the plugin lives at `~/.claude/plugins/cache/flux-market/flux/2.0.0`, pinned to
    `gitCommitSha` 98193b1, and `CLAUDE_PLUGIN_ROOT` points there. `diff -rq` against
    the repo is clean today, so edits to `bin/flux` here do **not** reach the running
    hook until the plugin is updated/reinstalled. When changing CLI behaviour that
    hooks depend on, refresh the install before trusting a live test.

  - **Detection generalized (2026-08-20)** — the goal the user set is "works for
    any repository, any project type", so detection was rebuilt as a rule table
    (`CHECK_RULES` in `bin/flux`) covering nx, turbo, bazel, cargo, go, mix,
    swift, deno, dart/flutter, gradle (+wrapper), maven (+wrapper), dotnet
    (glob markers), uv, poetry, pytest, bare unittest, bundler, composer, npm/
    pnpm/yarn/bun, and make/just. Two properties matter more than the breadth:
      - **Rules may decline.** A builder returns None when the marker can't yield
        a runnable command (a `package.json` with no test script, a `Makefile`
        with no test target, a `test/` dir holding no Python), and the next rule
        gets a turn. Proposing a command that cannot work is worse than silence.
      - **Universality never depended on the table.** `[check].command` is an
        opaque string run under `shell=True`, and the no-detection path writes a
        working config with an actionable message. Detection is a convenience;
        the guarantee is the config model.
    Verified empirically against every repo under ~/Dev — and `flux init` now
    reproduces flux's own gate (`python3 -m unittest discover -s tests`) exactly.
  - 49 tests green.

- **Not yet done in Phase 01:** nothing — Phase 01 is closed. Phase 00
  global-config quick wins are the user's, outside this repo.

## Decisions from the check-command review (2026-08-20, user-confirmed)

- `flux check` stays, and stays **unmodifiable**: no args, no agent-side narrowing —
  "check passed" must always mean the full configured gate, or it means nothing.
- Subset/iterative runs go through `flux run --` (the escape hatch); `flux check` is
  the only thing apply/wrap accept as "verified".
- The check command is per-repo config (`[check].command`), set once at adoption;
  `flux check` itself contains no repo knowledge.

## Task queue

- [x] Install the plugin from this repo (`/plugin marketplace add ~/Dev/flux`),
      restart, confirm SessionStart prime fires here and fast-no-ops in a non-flux
      repo. **Done 2026-08-20** — see the install note above, including the
      copy-not-symlink caveat.
- [x] Adopt in zaps/kiosk. **Done 2026-08-20** (kiosk commit 9dc00e3, on branch
      `chore/retire-gitnexus-for-codegraph`). `flux init` detected `nx.json`;
      candidate was corrected (see the defect below) to
      `npx nx run-many -t lint,typecheck,test`; ran green first try across
      31 projects / 83 tasks, so `verified` stamped true. `[check].filter` left at
      `failures` — the gate emits ~950 lines raw, one line filtered. State seeded
      from PAUL (v0.6 complete 19/19, phase 22.5 closed) plus branch reality, with
      the three unverified hardware gaps + DEV-T-READER-RECONNECT-SINGLE-SHOT in
      `open`. `.paul/` untouched; `prime` verified live there.
      Datapoint for the ledger: kiosk's `.paul/STATE.md` is **299 KB**; the prime
      pack that replaces it is capped at 2000 tokens.

- [x] **Defect fixed — the nx detector no longer proposes a scoped gate.**
      `nx affected --base=main` → `npx nx run-many -t lint,typecheck,test`.
      Guarded by two tests, one of which sweeps *every* marker in the rule table
      and fails if any candidate contains `affected`/`--base=`/`--changed`/
      `--onlyChanged`/`--since`. The invariant is now enforced by the suite, not
      by memory.
- [x] **Phase 02 — the five lifecycle skills are written.** Done 2026-08-20.
      `skills/{plan,audit,apply,wrap,resume}/SKILL.md`, distilled from the PAUL
      workflows in `zaps/kiosk/.claude/paul-framework/workflows/`
      (plan-phase, audit-plan, apply-phase, transition-phase, resume-project).
      **17.9 KB for all five vs PAUL's 62 KB** for the same five — and PAUL's number
      excludes the references/ and templates/ each workflow `@`-included.
      What was kept (judgment): apply's Execute/Qualify loop, the four escalation
      statuses, the "if you're thinking..." self-check table, and the
      intent/spec/code diagnosis before patching; plan's size classification and
      falsifiable ACs; audit's no-rubber-stamp stance and severity classes;
      wrap's reconcile-against-the-tree step; resume's exactly-one-next-action rule.
      What was dropped (procedure the CLI or flux's design already owns): the
      STATE/ROADMAP/PROJECT triple-file sync (now `flux state set`), paul.toml +
      ledger.toml sync (the ledger CLI reads transcripts from outside), loop-position
      ASCII diagrams and progress bars, milestone ceremony, handoff lifecycle
      management (now `flux handoff` + prime), and the numbered `[1]/[2]/[3]` menu at
      every step. Audit runs in a subagent and folds findings into the plan file
      itself — no second AUDIT.md artifact.
      Conventions the skills now bind: one plan file per phase at
      `.flux/plans/<NN-slug>.md` (or `<effort>/<NN-slug>.md`), which wrap appends its
      `## outcome` to rather than writing a separate SUMMARY; iterate with
      `flux run --filter failures`, close only with `flux check`.
      **Six new tests** guard it: all five exist, frontmatter name matches directory,
      `disable-model-invocation: true` on all five, each file ≤ 6000 bytes (the
      leanness is a budget, not a preference), apply/wrap name the gate and apply
      names the scoped-iteration command, and no skill anywhere documents
      `flux check` **with arguments** — the unmodifiable-gate decision, enforced by
      the suite instead of by memory. 55 tests green.
      **Not yet exercised end-to-end** — the kiosk phase below is their first real run.
- [ ] Phase 02 — migrate kiosk PAUL state into `.flux/`, archive `.paul/`.
- [ ] Phase 02 — one full real phase (plan → audit → apply → wrap) in kiosk.
- [ ] Phase 03 — generalize (zaps/api), retire PAUL/mattpocock installs, first
      ledger before/after.

## Session-close checklist (execute at the end of EVERY working session)

1. `flux check` green (or the failure documented here).
2. `flux state set` — phase/position/next reflect reality.
3. Update this file: current state, queue, anything a fresh session must not re-derive.
4. Commit (docs included). Never leave the repo dirty across sessions.
