# flux-v2 — status & next task

Updated: 2026-08-21 (first full lifecycle run: kiosk phase 01 shipped as PR #66, CI green)

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
    **And refreshing needs a version bump** — `claude plugin update` compares versions,
    not commits, so it will report "already at the latest version" over a stale cache.
    See the adopt-run entry in the task queue; the plugin is now 2.1.0.

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
- [x] **`/flux:adopt` shipped (user request, 2026-08-20).** Plan + outcome in
      `03-adopt.md`. Any repo carrying prior knowledge can be brought into flux:
      `flux init --scan` inventories 15 known state sources (PAUL, agent-os,
      taskmaster, openspec, kiro, specstory, cursor, windsurf, copilot, CLAUDE.md,
      AGENTS.md, hand-kept ROADMAP/STATE/TODO/DECISIONS), sized and largest-first,
      **parsing none of them**; plain `flux init` prints a routing line when it finds
      any. `skills/adopt/SKILL.md` does the judgment: live vs history (only live
      reaches the five state keys), read a huge state file from its ends via
      flux-explorer rather than whole, trust the tree over the framework's own claims,
      then verify by reading `flux prime` back as a stranger.
      **Retirement is opt-in, archives rather than deletes** (`git mv` into
      `.flux/archive/<framework>/`), requires a clean tree, treats the state dir and
      the framework install as separate decisions, and leaves machine-level installs
      to the user. The skill recommends adopt → run one real phase → *then* retire.
      Design note worth keeping: `flux init` stays **non-interactive** (it is called
      from hooks and scripts, where a prompt would hang), so the CLI detects and
      routes while the skill does the asking. And no framework-format parser may enter
      `bin/flux` — that is the per-project fork plan.md rules out.
      plan.md amended: `/flux:adopt` added to the roster with its ledger metric
      (median context per request), `--scan` added to the CLI surface.
- [x] **Phase 02 — `/flux:adopt` run end-to-end on kiosk. Done 2026-08-20.**
      `.paul/` (7.4 MB / 427 files) left in place as frozen history; nothing archived,
      per the skill's own adopt → run a phase → then retire order.
      **Ledger datapoints:** kiosk's PAUL state is 300 KB (`STATE.md`) + 149 KB
      (`ROADMAP.md`) + 89 KB (`PROJECT.md`); the flux pack that replaces it as the
      session opener is **1282 bytes**. Its gate emits 946 lines; `flux check` prints 1.
      **What adoption caught that a copy would have carried forward:** `STATE.md` is
      append-layered, so it leads with a current 2026-08-14 position while its
      *Git State*, *Session Continuity* and *Blockers* sections still describe
      2026-05-18 (Phase 19, PRs #29–32, a branch that no longer exists). Step 4 —
      trust the tree — is what caught it. Corrections written into the pack: the branch
      is 2 commits ahead of main, not 1; and `DEV-T-READER-RECONNECT-SINGLE-SHOT` was
      **re-verified against source** (`StripeTerminalProvider.tsx:633` — one timer, and
      a failed discovery never re-arms it), so it now carries a file:line instead of a
      claim.

      **Three defects the run surfaced — two fixed here, one is a live gotcha:**
      1. **Directory-source plugins refresh on version bump, not on new commits.**
         `claude plugin update flux@flux-market` reported "already at the latest
         version (2.0.0)" while the cache lacked *all six* skills shipped since.
         Bumped `plugin.json` to **2.1.0**; the update then took, and
         `~/.claude/plugins/cache/flux-market/flux/2.1.0/skills/` now holds all twelve.
         **Standing rule: every skill or CLI change that hooks depend on needs a
         version bump before it can be tested live.** This supersedes the weaker
         "the install is a COPY" note above — the copy is the mechanism, the version
         is the trigger.
      2. **Fixed — adopt's "read from the ends" was byte-blind.** These state files
         have enormous lines (kiosk's `STATE.md`: 300 KB over 631 lines, longest line
         17 KB), so a plain `head -60` returned 100 KB — the exact cost adoption
         exists to avoid. Step 3 now says to map with `grep -n '^#\{1,3\} '` and read
         sections through `cut -c1-300`: **cap line length, not line count.**
      3. **Fixed — `flux state set` wrote silently.** Over-budget writes were loud but
         successful ones said nothing, so there was no way to see how close the pack
         sat to its cap. It now prints `flux state: wrote N keys, N/8000 bytes`,
         guarded by a test that asserts the reported size equals the file on disk.
         65 tests green.
- [x] **Done 2026-08-20 — derived facts now live in prime's header, not in stored prose.**
      Found at adopt's read-back step: `position` said "2 commits ahead of main", and
      the commit that *wrote* it made that 3. Ahead/behind now joins branch and
      dirty-count as a live-derived header field: `## flux prime — kiosk @ chore/x,
      2 ahead of main, clean`. Base is `@{upstream}` when the branch has one, else the
      first existing of `origin/HEAD` / `origin/main` / `origin/master` / `main` /
      `master` that isn't the current branch; **nothing is printed when the branch
      hasn't diverged**, so the header stays quiet in the common case. All of it goes
      through the existing `git()` helper (returns "" on any failure), so prime's
      never-fail contract is untouched. Also fixed the "1 dirty files" plural on the
      same line. `wrap` and `adopt` now say in as many words that `position` must not
      repeat what prime derives. **Four tests** (ahead / behind / quiet-when-synced /
      dirty singular+plural). 69 tests green. Plugin bumped to **2.2.0** — prime is
      hook-invoked, so the cache needs the version to take.
- [x] **Phase 02 — one full real phase (plan → audit → apply → wrap) in kiosk. Done
      2026-08-21.** The five lifecycle skills' first end-to-end run. Phase
      `01-ship-codegraph-and-flux` in `zaps/kiosk/.flux/plans/`: pushed
      `chore/retire-gitnexus-for-codegraph` and opened **PR #66** with CI green
      (`ci` pass, 2m7s). Not merged — the repo's own rule is that the user signs off.

      **The audit is the part that earned its keep.** Three blocking findings, nine
      recommended, four deferred — on a plan I'd have called obviously fine:
      1. AC-4 pinned `c5842e7` as `origin/main` (it's the *parent*; the tip is
         `a6577b1`) and justified itself with "this repo merges through PRs, never
         directly" — falsified by that very tip, pushed straight to main with no PR,
         on a repo with no branch protection.
      2. "The local gate is a superset of CI" — false. CI also runs
         `nx run-many -t build --exclude=@zaps/kiosk`; kiosk's `flux check` is
         lint/typecheck/test and never builds. Worse, every target in that gate is an
         Nx **cache hit** for this diff (nothing it touches lives inside a
         `projectRoot`), and `flux check` prints the same pass line for a replay as for
         a real run.
      3. The plan told the executor to write into the PR body that `.paul/` was
         "untouched" — the branch amends `DECISIONS.md` and `PROJECT.md`. A false
         statement, headed for a reviewer, with no AC that could catch it.
      Folding them in took the plan from 4958 → 11910 bytes, all `<!-- audit -->`
      marked, one file, no second artifact. Verdict: ready with conditions.

      **Ledger datapoints:** kiosk's gate emits **946 lines; `flux check` printed 1**
      (twice — T1 and wrap). The audit subagent burned ~71k tokens reading the repo
      and returned only findings; none of that reading entered the executing session.

      **What the skills got right in the wild:** apply's qualify step (the four AC-2
      greps came from the audit, and re-running them fresh is what made "DONE"
      mean something), and wrap's reconcile-against-the-tree (it's what surfaced the
      deviation below).

      **Honest deviation, recorded in the plan's outcome:** T1's gate ran in *parallel*
      with the audit to save wall-clock, so the order was plan → (audit ∥ T1), not
      plan → audit → T1. It passed, and the audit then rewrote what that pass meant.
      Also: CI passed first try, so T3's re-trigger and fix-forward paths were never
      exercised — they're in the plan untested.

- [ ] **Candidate — prime hides drift-vs-main once a branch has an upstream.**
      Surfaced at the wrap read-back of this very run. Before the push, kiosk's header
      read `3 ahead of origin/main` — the useful number. After `git push -u`, the
      branch has its own upstream, is in sync with it, and `_drift_base` prefers
      upstream, so the header now says **nothing**. For a feature branch, "in sync with
      my own remote" is the boring fact; "3 ahead of main" is the one worth a line.
      Fix shape: when the upstream is the same-named remote branch *and* a distinct
      default branch exists, report drift against the default branch too (or instead).
      Shipped 2026-08-20 in the same session; caught by using it the next day.
- [ ] Phase 03 — generalize (zaps/api), retire PAUL/mattpocock installs, first
      ledger before/after.

## Session-close checklist (execute at the end of EVERY working session)

1. `flux check` green (or the failure documented here).
2. `flux state set` — phase/position/next reflect reality.
3. Update this file: current state, queue, anything a fresh session must not re-derive.
4. Commit (docs included). Never leave the repo dirty across sessions.
