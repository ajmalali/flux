# flux-v2 — status & next task

Updated: 2026-08-26 (**the execution-index (ADR 0001) revival is DRAFTED as a design doc — nothing built**. `.flux/analysis/2026-08-26-execution-index-revival-design.md`, queued at the top of the task queue. A design conversation about how to run big multi-phase features settled a **division of labor** (= Principle 1): mattpocock `grill`/`wayfinder` do the **planning** (and `wayfinder` *invokes* grilling — they are not chained); **flux** does the **decomposition + execution**, breaking a spec into a task DAG **once** and carrying `routing` + `files` that mattpocock tickets have no slot for. So `to-tickets` leaves the execution path (kept only as a human-facing tracker view), and you decompose once, not twice. The revival honors ADR 0001's binding ruling — **the frontier justification is spent** (ramp 5.7%, `flux prime` already eats it) and may not be re-used — so it rests instead on **declared-files (code-bucket ramp)** + **per-task routing**, with build **gated behind the real-work pre-registration**: run the next live feature on the thin `status.md` queue, log `[pack-miss]`/`[want]`, build only if the pain shows on data. **beads stays rejected** as a dependency; its one useful verb (`bd ready`) is the topo sort, ~50 lines of stdlib. Storage reuses ADR 0002 verbatim (`tasks.jsonl` op-log, `merge=union`, replay, `blocked` computed on read). Two decisions left to the user in the doc: which store is canonical, and id assignment across parallel branches. **184 tests green, gate clean; no code changed this session.**)

Previously — 2026-08-25 (**the ceremony's quality question is answered and it is a null — all three arms wrote the same two lines**. `meridian-007` ran m6, the corpus's only bug-report task, against vanilla / flux / flux-full: every arm delivered, every arm 10/10, and every arm inserted the *same* `_reject_conflicts` call into `confirm_hold` — vanilla and flux-full byte-identical. flux-full paid $2.22 against $0.78/$0.81 and 4 sessions against 1 for it; its apply session alone ($0.46) beat vanilla's whole run, and the other $1.76 bought nothing the suite could see. Getting there needed a new `--from-reference` flag (`62a3fff`): m6's defect is latent in the *corpus* reference tree, so under the cumulative protocol each arm would have been graded on a tree it wrote itself — the flag pre-supplies m1–m5's references so all arms start from the identical broken tree, refuses without explicit `--tasks`, and announces itself above the report table. Cycle 3 written up in `.flux/analysis/2026-08-22-ceremony-two-cycles.md`; that file's "one legal route left" is now closed. **184 tests green.** NEXT is a judgment call, not a measurement: whether principle 5 fires on the shipped lifecycle skills — see the DECIDE item at the top of the queue.)

Previously — 2026-08-24, later (**the append-only state format is BUILT and dogfooded** — `.flux/state.toml` is gone from this repo, replaced by `.flux/state.jsonl`, one JSON record per key per write, union-merged by git via `.flux/.gitattributes` and resolved by replay. ADR **0002**. `updated` is now derived from the newest record rather than stored — it was one guaranteed-divergent line per session on a file every branch rewrote. New: `flux state log [N]` (the superseded value survives a bad write — the 2026-08-22 silent-corruption defect had no recovery path) and `flux state compact` (auto-fires past 8x the pack budget, because CLAUDE.md forbids uncapped stored state and an append-only file is uncapped by construction). The budget still prices the **rendered pack**, not the log — checked before appending, so an over-budget write leaves the log untouched. **18 new tests, 171 green**, and the two that matter run real `git merge`: two branches touching the same key merge clean and the newer wins, while the same two sessions against the old `state.toml` conflict — the control is in the suite. Plugin **2.10.0**. **ADOPTED IN KIOSK the same day** (`728adf8`, pushed to `zaps-io/kiosk` main): the `state.toml` line is out of kiosk's `.flux/.gitignore`, the 5 live keys migrated one-way on first write, and `state.jsonl` + `.gitattributes` are committed on `main` in a **101-branch** repo — so the conflict metric has a denominator and cycle 1 of 2 starts now. A live two-branch merge there came back clean: 0 unmerged paths, both records kept, replay returned the newer. NEXT: nothing to build on this line — let ordinary kiosk work accrue and read the count next cycle.) **Also 2026-08-24: `meridian-005` gave PAUL its first fair numbers** — 4/4 at 82/82, and **6.0x vanilla's cost** on the four tasks both scored, so the ceremony tax reproduces on the framework flux was distilled from. meridian-003's `paul 1/4` is withdrawn as our own arm bug. A live harness defect was found and fixed in the process: a transport failure reported without a status code slipped every check in the void machinery and graded five untried speckit sessions 0/19. 177 tests green. speckit and agentos remain unmeasured after three runs.

Previously — 2026-08-24 (**the agent roster failed the same bar at zero and both agents are deleted** — 505 B = 126 tok/session, 0 invocations in 273 billed sessions and 0 in all 537 transcripts; trim and merge cannot clear a zero denominator so deletion was the only rung, pre-registered in `88ce1a8` before the read. Corrected: the roster is 505 B = 126 tok, not the 473 B = 118 tok published in `6c9a8f6`. Capability given up, reported as loss: flux-verifier's pre-existing-failure check and flux-explorer's haiku/low cost pin; the rest was already done in code by `flux check`/`flux run --filter` and by the built-in `Explore` (invoked 13x in the same corpus where flux-explorer was invoked 0). **flux now injects nothing model-visible except `prime`** — 0 of 14 skills listed, 0 agents. Every uncapped always-on path it ever had has now met the bar and every one failed. Plugin 2.9.0, 153 tests green. NEXT: stop auditing context; build the append-only JSONL-in-git state format.)

Previously — 2026-08-23 (Phase 03's api line closed as a **pre-registered null**: prime's ceiling in zaps/api is ~1.1k tokens of a ~50k ramp, and the gate bar — written down before the number — was missed at 2,166 vs 5,000. api is NOT adopted. Five competing frameworks retired there instead: 193 files / −32,927 lines on a branch. Binding finding: **flux's value is repo-shaped** — it needs a bloated state artifact read whole and a fan-out gate; adoption is a measurement, not a rollout. Phase 03 rescoped to "establish where flux pays". 153 tests green. Later the same day: **kiosk PR #66 merged** (`e8a3199`), the codegraph hook guard homed on main (`f293528`), and the open `.flux/state.toml` question decided — **untracked in kiosk** (`19861ee`), because a wholesale-rewritten file across ~100 branches conflicts on every one of them. Later still: **the mattpocock install is RETIRED** — reopened on a
utilisation bar derived from flux's own 2,000-token prime budget (≤2,000 tok per
session-of-use), pre-registered in `ecfcffb` before a fresh number was read, and failed
at **21,110 — 10.6x** on 9 invoking sessions out of 287. Trim was tried first and also
failed. `research` and `writing-for-agents` were vendored with
`disable-model-invocation: true` so the retirement costs no capability; plugin 2.7.0.
The rule it settles: **carrying a skill is nearly free; listing it is not.** It leaves
one thing open by design — the same bar points at **flux's own uncapped skill
listing**, unmeasured. Measured the same day, and it fails harder: **`flux:review`,
flux's only listed skill, has 0 invocations in 520 transcripts** while costing 109
tok in every session, so utilisation is exactly zero on both denominators and the
pre-registered trim empties the listing. `review` now carries
`disable-model-invocation: true` — in `sync-vendored.sh`, not just the file, since
upstream has no such key — so **no flux skill is model-visible any more**; a session
hears about flux once, from the capped `prime` hook. Capability cost measured at 0
autonomous calls. Plugin 2.8.0. Also corrected: the mattpocock bar failed by 6.3x,
not 10.6x — `/mattpocock-skills:ask-matt` was missed by the earlier scan. Still open:
the **agent** roster, 118 tok/session, 0 post-install uses, no dmi equivalent.)

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
    **Both DELETED 2026-08-24** on the utilisation bar (0 invocations, 0.00% util);
    there is no `agents/` directory any more. See the RESULT entry near the end.
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

  - **Superseded 2026-08-23 — the install is no longer a copy, and the manifest's
    `hooks` key is now a load error.** `known_marketplaces.json` records
    `flux-market.installLocation` as `/Users/ajmalali/Dev/flux` itself, so a
    directory-source plugin loads from the working tree; the stale
    `~/.claude/plugins/cache/flux-market/flux/{2.0.0,2.1.0,2.3.0}` copies are
    leftovers. **The version bump is still required** — `claude plugin update`
    compares versions — but a bumped version now publishes the tree, not a snapshot.
    And on Claude Code 2.1.234 `hooks/hooks.json` is loaded automatically, so
    `plugin.json`'s `"hooks": "./hooks/hooks.json"` made the plugin fail to load
    outright (*"Duplicate hooks file detected"*), silently reverting the session to
    no flux skills at all. The key is removed; `manifest.hooks` may only name
    *additional* hook files. Plugin **2.6.0**, `claude plugin list` green.
    Also: `claude plugin update flux` is "not found" — the argument is
    `flux@flux-market`, marketplace suffix included.

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

## Benchmark (`bench/`) — added 2026-08-21

`fluxbench` exists and is validated end to end: six arms, two projects, 97 tests
in the repo gate. See `bench/README.md` for the fairness rules and `plan.md` for
why it is part of the plan.

Four things it established that were not known before, each of which would have
corrupted a result:

1. **`--setting-sources project` is the isolation lever.** A bare session's
   cached prefix is ~6.5k tokens with it; without it every one of the operator's
   installed plugins rides along in every arm and drowns the differences.
   `--plugin-dir <repo>` loads flux from the working tree and fires its
   SessionStart hook — so the bench always measures checked-out flux, no version
   bump needed.
2. **An unresolved slash command exits successfully.** `is_error=false`,
   `subtype=success`, zero turns, zero cost. Recorded naively it makes a
   misconfigured arm look like a cheap efficient one. A zero-turn zero-cost
   session is now a hard failure that abandons the arm. Found live: two agentos
   steps had been scoring as "ok" at $0.000.
3. **Project skills resolve headlessly, but are not advertised.** Asking the
   model "do you have skill X" returns a confident NO; invoking `/X` works.
   spec-kit ships skills, so the wrong answer would have made that arm run four
   sessions of nothing.
4. **Acceptance tests need a reference implementation to be trustworthy.** The
   first smoke run had every arm fail the same test on a boundary the brief never
   pinned down — the corpus author's bug scored against the arms. `verify` now
   proves each task red-on-seed and green-on-reference before it may judge.

5. **Red/green cannot catch a shared assumption.** m2's tests bound to
   `refund_cents(price_cents, gap)`; the brief named only the module. Vanilla
   wrote `refund_cents(booking, cancelled_at)` — valid, and it lost a task it had
   delivered. The reference is written by the same person as the tests, so they
   agree by construction. Corpus rule now in `bench/README.md`: *if an acceptance
   test calls it, the brief must name it, signature included.* `verify` enforces
   the name half; only the rule covers signatures. `meridian-001` was killed over
   it (records kept at `~/.flux-bench/runs/meridian-001-aborted-unfair-m2`).

**In flight:** `meridian-002` — 6 arms x 4 tasks on sonnet, $40 cap, launched
2026-08-21, detached (`nohup`). Log `/tmp/meridian-002.log`, records
`~/.flux-bench/runs/meridian-002/`. Arms run control-first
(vanilla, flux, flux-lite, paul, speckit, agentos) so a budget cut-off costs the
least decision-relevant arm.

**Read it with:** `./bench/run.py report meridian-002` — works on a partial run,
and ends with a verdict naming every metric `flux` loses and to whom.

**meridian-002 was spoiled by a rate limit, and the harness scored it as arm
failure.** Read 2026-08-21. Mid-run the account hit its limit; 32 sessions came
back in under a second with `api_error_status: 429`. The report then stated that
`paul` and `flux-lite` delivered **0/4** — four of six arms graded on work that
never ran, in a table indistinguishable from one where they had genuinely failed.
This is the same class as the unresolved-slash-command lie (#2 above), and worse:
that one made a broken arm look cheap, this one made an untried arm look broken.

**Fixed in the harness (see `bench/README.md`, "Why a rate limit is void"):**
- `driver.run_session` retries `RETRYABLE_API_STATUSES` (429/5xx/529) on a
  60s/180s/600s backoff — but **only when the failed attempt cost nothing**. A
  billed attempt may already have written to the repo, and re-running it would
  judge the arm against a tree its own abandoned attempt had moved.
- What survives the retries raises `ArmVoided`: the task is recorded `void` and
  the arm abandoned rather than graded.
- The report excludes void tasks from every denominator, renders an arm with no
  scored tasks as `void` (not `0/4`), prints `—` instead of a ✓ in the targets
  table for it, and states in the verdict that the run is incomplete. It applies
  the rule to records written before it existed, so old runs re-read correctly.
- Where arms scored different task sets, the verdict no longer claims
  "out-delivered"; it compares them on the tasks each pair **both** attempted —
  usually the only real evidence a spoiled run produced.
- **12 new tests** (`TransportFailureTests`, `VoidTaskTests`). 114 green.

**What meridian-002 actually established**, once re-read honestly — vanilla and
flux both ran m1, m2, m3 clean, so this much is a like-for-like comparison:

| | vanilla | flux |
|---|---|---|
| delivered (m1–m3) | **3/3** | 2/3 |
| $/task | $1.11 | $2.83 |
| wall/task | 198s | 509s |
| sessions/task | 1.0 | 4.0 |
| ctx p50 | 59,202 | **50,016** |
| bash out/task | **15,518** | 49,672 |

flux lost m3 **on merit** (20/28 acceptance, gate green — not a transport
failure). It wins ctx p50 and nothing else that matters. Everything else in the
run — flux-lite, paul, speckit, flux's m4 — is void and says nothing.

**So the falsifiability rule has a real reading now, on 3 tasks:** the
four-session lifecycle costs 2.6x the dollars, 2.6x the wall-clock and 4x the
sessions of a single vanilla session, and delivered *less*. That is the finding
to act on — but n=3 against one control, and `flux-lite` (the arm that separates
machinery from ceremony) never ran. **The decisive missing evidence is
flux vs flux-lite vs vanilla over the same four tasks.**

**In flight:** `meridian-003` — the same 6 arms x 4 tasks on sonnet, $40 cap,
launched 2026-08-21 on the fixed harness, detached (`nohup`). Log
`/tmp/meridian-003.log`, records `~/.flux-bench/runs/meridian-003/`. meridian-002
was killed at $16.93 rather than finished: its speckit arm was already void, so
nothing it produced from there could be compared. Its records are kept.

**Read it with:** `./bench/run.py report meridian-003`. If a rate limit hits
again the run now waits it out, and anything it still cannot reach comes back as
`void` rather than as an arm that failed to deliver — so a partial report is
safe to read at face value.

**meridian-003 — the run that answered the question. 2026-08-21.**

| arm | delivered | accept | $/task | ctx p50 | bash out | sessions | tokens |
|---|---|---|---|---|---|---|---|
| vanilla | **4/4** | 82/82 | **$1.05** | 58,598 | 13,415 | 1.0 | **5.6M** |
| flux (full lifecycle) | **4/4** | 82/82 | $2.92 | **49,930** | 38,712 | 4.0 | 15.6M |
| flux-lite (prime + apply) | **4/4** | 82/82 | **$1.05** | 62,047 | **9,003** | 1.0 | 6.0M |
| paul | *invalid — see below* | | | | | | |
| speckit / agentos | void (429) | | | | | | |

**1. The ceremony is the cost, and it buys nothing.** flux-lite delivers 4/4 at
$1.05/task — vanilla's cost to the cent — while the full plan→audit→apply→wrap
lifecycle costs **2.8x** for the same 4/4 and the same 82/82 acceptance. It also
loses re-reads (1.2 vs 0.0), bash out (4.3x), wall-clock (2.2x) and total tokens
(2.8x). It wins exactly one column: ctx p50.

**2. That one win is a measurement artifact, and the targets table should say
so.** flux's ctx p50 is lower because it splits the same work across four
sessions, each carrying a smaller context — while spending 2.8x the total
tokens. **`ctx p50` is a per-request metric that session-splitting games.** Any
arm can win it by cutting the work into more sessions. It cannot be read without
`tokens` and `sessions` beside it.

**3. meridian-002's "flux lost m3 on merit" did not reproduce** — 28/28 here vs
20/28 there. That was variance. Do not carry the old headline forward.

**4. The retry/void machinery was validated in production on its first run.** The
rate limit returned during speckit and agentos. agentos retried 3x
(60s/180s/600s) and then voided the whole arm before any task; speckit's billed
attempt was correctly *not* retried and voided too. Both render as `void`, not as
`0/4`. Exactly the behaviour the fix was written for.

**5. PAUL's 1/4 is an arm bug and must not be published.** Its arm ended each
phase with `/paul:verify` — "guide manual user acceptance testing" — instead of
`/paul:unify`, "reconcile plan vs actual and close the loop". So PAUL's state
never closed a phase, and from m2 on every plan session hit its own precondition
check ("the previous loop isn't closed — UNIFY has not run"), asked which way to
proceed, and ended. Four billed sessions and a zero-line diff, three times over.
The driver denies AskUserQuestion, so a headless arm needing an answer just
stops. **Fixed** in `bench/arms/paul.toml` (step 4 is now `unify`, which also
makes the arm a true mirror of flux's plan→audit→apply→wrap). PAUL has never yet
been measured fairly — meridian-002 voided it, meridian-003 misconfigured it.

**New guard, 3 tests (117 green):** the report now flags any arm with undelivered
tasks whose diff is empty — "check before publishing" — because the harness
cannot distinguish an arm that stalled from a framework that does nothing, and
guessing is how meridian-001 died.

**Next session — the falsifiability rule now has a verdict to act on.** The
lifecycle ceremony (plan/audit/wrap) costs 2.8x and moves no ledger metric it
does not also lose. Per CLAUDE.md the options are to delete it, or to name the
metric it is supposed to move and show it moving. **Recommendation: keep the
machinery (`prime`, `apply`, `check`, `run`, state) — flux-lite proves it is free
— and put plan/audit/wrap on notice with one named metric each.** Before acting,
consider that the corpus no longer discriminates: three arms scored 82/82. A
verdict that plan/audit/wrap are worthless on four tasks nobody fails is weaker
than it looks — the audit earned its keep on kiosk's real phase (three blocking
findings). The honest next move is a harder corpus, or a task class where being
wrong is expensive.

Also pending: **rerun PAUL alone** on the fixed arm to get its first fair
number. The question it
has to answer is the one meridian-002 could not: **flux vs flux-lite vs vanilla
over the same four tasks** — whether the 2.6x cost is the machinery or the
ceremony.

## meridian-003 and the regime problem — 2026-08-22

**The run.** `flux` 4/4 at $2.92/task over 4 sessions · `flux-lite` 4/4 at $1.05 in 1 ·
`vanilla` 4/4 at $1.05 in 1 · `paul` 1/4 · `speckit`/`agentos` void (429, never
attempted). `flux` lost every efficiency column to `flux-lite` and won only ctx p50.
Read at face value the falsifiability rule deletes the four-session lifecycle.

**Why that reading is incomplete — and why this is not a rescue.** Every arm that ran
scored **82/82 acceptance tests**. A corpus on which everyone is perfect cannot
discriminate on quality; it can only rank cost, and on cost ceremony always loses.
Every meridian task also fits comfortably inside one session — the regime where
decomposition machinery has nothing to decompose and can only appear as overhead. The
benchmark measured the regime flux's thesis is inert in and correctly reported flux
cost more there. It has never measured the regime flux exists for.

This is exactly what someone would say to save a feature the evidence killed, so ADR
0001 pins four falsifiers with explicit delete conditions instead of leaving it
unfalsifiable.

**The structural finding (independent of the above).** `plan.md` declares the
big-feature altitude — wayfinder → to-spec → to-tickets → `/flux:plan` per ticket —
and it has no spine:

- `/flux:plan` writes the **first** phase and says split the rest into sequential
  plans; the decomposition of everything after it lived in the planning session's
  context and died with it.
- `state.toml` carries five prose fields under a 2000-token cap — no ledger of done,
  no edges, no remainder. A sentence cannot express thirty tasks and their order.
- `bin/flux` **cannot read a single ticket file** `to-tickets` writes.

So every cold session re-derives the frontier by reading. That is where the context
goes, and it is the opposite of deterministic. Choosing *what* the tasks are is
judgment and belongs to skills; choosing *which is next* is a topological sort — the
most procedural operation in the system, and the only one never moved into the CLI.

**Written this session (design only — nothing built):**

- `.flux/adr/0001-execution-frontier.md` — opens the v2 ADR line. Local execution
  index + `flux task add|start|done|block|next|list`; task size **refused** not advised;
  ceremony scales with size (small task ⇒ apply-only, converging on `flux-lite` where
  it wins); done recorded, not asserted. Four ledger metrics with delete conditions.
- `.flux/plans/flux-v2/plan.md` — amendment before Phases; "ticket store" in Out of
  scope **qualified, not deleted** (tracker still out; local execution index in).
- `bench/realworld/` — design + 30-metric spec for a human-driven, five-arm run
  (`DESIGN.md`), and a corpus (`corpus/plan.md`, `corpus/AMENDMENT-M3.md`) for a
  full-stack app. **Superseded in shape by the finding above**: that corpus
  pre-decomposes the work into four milestones, which hands every arm the
  decomposition for free and tests decomposition machinery not at all. If it is used,
  the plan must be handed over whole, each arm left to decompose it, and grading run
  continuously so the output is a quality-per-context curve rather than one cell.

**The prerequisite, and it is binding.** The size budget assumes quality decays as
context grows. That is asserted in the targets table and in `/flux:plan`'s own wording
and has **never been measured on this account's data**. Before building it, mine the
existing transcripts (~83 in this repo, several hundred under `~/.flux-bench/runs`)
for context-at-request against tool error rate, redundant re-reads and file churn.
Proxies, not quality — but if no relationship appears there, the budget is a guess and
ADR 0001's second rule is reconsidered before any code is written.

## The decay premise, measured — 2026-08-22

ADR 0001's rule 2 (refuse an oversized task) rested on "quality decays as context
grows", asserted in plan.md's targets table and in `/flux:plan`'s wording and never
measured here. It has now been measured on 414 transcripts / 16,909 main-chain tool
calls / 344 sessions, and **the premise did not survive**. Full write-up and method:
`.flux/analysis/2026-08-22-context-decay.md`.

**There is no knee.** No context size at which anything falls off a cliff.

- **Correctness is flat.** The only proxy that is about the model's picture of the
  code being wrong — Edit/Write failing on *"String to replace not found"* or *"File
  has not been read yet"* — runs 0.91% / 0.89% / 0.73% / 0.85% / 1.37% across the
  75k → 300k+ bins inside one model family.
- **The 2.9x that looked real is Simpson's paradox.** Pooled across all models it is
  0.51% → 1.48% at Fisher p=0.0038. Sonnet and haiku sessions never exceed 200k and
  sit near zero, so they drag the low cell down; within opus it is 1.38x at p=0.52.
- **What does rise is re-orientation, and the step is at ~100k, not 200k.** Reading a
  file already among the last five files read: 10.7% / 9.2% below 100k, then 26.6% /
  28.9% / 32.6% above. Same direction within-session at every cut (sign-test p=0.09 at
  200k, p=0.22 at 100k). Suggestive at the strength this data supports, not proven.
- **Churn does not rise.** The naive metric (re-touch any already-touched file) climbs
  26% → 76%, but that is arithmetic: the touched set only grows. Normalised to a fixed
  window it is flat, and within-session it *falls*.
- **57% of raw tool errors are permission friction**, clustered at session start.
  Counted naively the tool-error rate falls fivefold with context and reads as proof
  that context helps. This is also a live defect in `bench` — see the task queue.
- **Everything reverses above 300k.** Only 26 sessions get that far. Survivorship plus
  a shift in what those sessions do; not evidence of a ceiling.

**So a long context costs re-reading, not correctness** — dollars and wall-clock, not
failed acceptance tests. Which is exactly what `meridian-003` showed from the other
end, where every arm scored 82/82 and only cost separated them.

**Acted on, this session:**

- ADR 0001 rule 2: **refuses → warns**, with the reasoning recorded inline. Its ledger
  metric changes from held-out acceptance pass rate (unmeasurable on this corpus) to
  **re-read rate above the threshold**. Rules 1, 3, 4 untouched — none depends on decay.
- `plan.md`: the same amendment to the ledger metrics paragraph, the Prerequisite
  section replaced with the result, and a footnote under the targets table warning
  that Tool error rate is friction rather than quality as currently computed.
- `bench/fluxbench/decay.py` + `./bench/run.py decay` + 15 tests (132 green). It exists
  so the next reporting cycle re-runs the check instead of re-deriving it.

**Defect found and fixed while doing it (2026-08-22).** `flux state set` takes bare
key/value pairs, so `flux state set --phase "..."` wrote a key literally named
`--phase` beside the real one, **printed "wrote 11 keys" as if it had succeeded**, and
left `flux prime` rendering the previous session's phase/position/next. Silent
corruption of the one file that carries a project across sessions, and it happened in
this session. `bin/flux` now refuses any key starting with `-` (exit 2, whole write
refused, old state untouched), guarded by two tests. **Plugin bumped 2.3.0 → 2.4.0** —
a `bin/flux` change does not reach the installed cache without it.

**What is still open, and cannot be closed by mining.** Detecting the observed
correctness difference at 80% power needs ~18,700 Edit calls per side; there are
~1,300 — underpowered by 14x, and only 65 sessions on this account ever pass 200k. The
correctness question needs a **designed** run: the same task executed at deliberately
different context loads, graded on acceptance. Until one exists, no document here may
assert that quality decays with context.


## Task queue

- [ ] **Execution index (ADR 0001) revival — DRAFT design filed, nothing built.
      2026-08-26.** Design doc at
      `.flux/analysis/2026-08-26-execution-index-revival-design.md`. Proposes reviving
      the suspended ADR 0001 as `flux task add|start|done|block|next|list` over a
      `tasks.jsonl` op-log (ADR 0002's union-merge mechanism reused verbatim; `blocked`
      computed on read). **Division of labor pinned** (= Principle 1): mattpocock
      `grill`/`wayfinder` plan; flux decomposes **once** + executes, carrying `routing`
      and `files` the mattpocock tickets have no slot for — so `to-tickets` leaves the
      execution path (stays only as a human-facing tracker view). **Binding constraint
      honored:** ADR 0001's frontier justification is *spent* (ramp = 5.7%, prime
      already eats it) and may not be re-used; the revival rests on declared-files
      (code-bucket ramp) + per-task routing instead. **Gated behind the real-work
      pre-registration** — build only if the next live multi-phase feature logs
      `[pack-miss]`/`[want]` and `./bench/run.py ramp` shows a code-bucket worth
      attacking. Two decisions left to the user in the doc: which store is canonical
      (recommend `tasks.jsonl`), and id assignment across parallel branches. Beads
      stays rejected (dependency); its one useful verb is the topo sort. On validation
      this graduates into an ADR 0001 amendment (or ADR 0003), not before.

- [x] **`meridian-007` — the ceremony's last open question is answered, and the
      answer is that all three arms wrote the same two lines. 2026-08-25.** m6 —
      the corpus's only bug-report task, written 2026-08-24 as the one experiment
      the fairness rule still permitted — run against vanilla / flux / flux-full.
      Records `~/.flux-bench/runs/meridian-007/`, $3.81 of a $15 cap. Full write-up
      appended to `.flux/analysis/2026-08-22-ceremony-two-cycles.md` as cycle 3.

      | arm | delivered | accept | $/task | ctx p50 | wall/task | sessions |
      |---|---|---|---|---|---|---|
      | vanilla | 1/1 | **10/10** | **$0.78** | 58,459 | **130s** | 1.0 |
      | flux | 1/1 | **10/10** | $0.81 | 54,194 | 134s | 1.0 |
      | flux-full | 1/1 | **10/10** | $2.22 | **46,788** | 263s | 4.0 |

      **1. Identical mechanism, not just identical score.** Every arm inserted
      `space = self.repos.spaces.get(hold.space_id)` +
      `self._reject_conflicts(space, hold.interval, ignore_id=hold.id)` into
      `confirm_hold` after the liveness check — vanilla and flux-full byte-identical,
      flux with `Interval(hold.start, hold.end)` for the same value. Two fixes were
      legal and the tests are mechanism-blind; all three chose the same one and each
      named the hold-claims-less-than-a-booking asymmetry in a docstring. flux-full's
      155-line plan and its audit session produced the same edit one pass did.
      Session costs: plan $0.46 + audit $0.83 + apply $0.46 + wrap $0.47 — **the
      apply session alone beat vanilla's whole run** ($0.46 vs $0.78), as in cycle 2,
      and the remaining $1.76 bought nothing the suite could see.

      **2. It needed a harness change, and the change is the honest one.** m6's
      defect is latent in the *corpus reference tree*; under the cumulative protocol
      each arm would have been graded on a tree it wrote itself, so the run would
      have measured which arm happened to reproduce the bug rather than which one
      finds it. New `--from-reference` (commit `62a3fff`) pre-supplies the reference
      implementation of the preceding tasks so every arm starts from the identical
      broken tree. It refuses without explicit `--tasks`, refuses if a preceding task
      has no reference, prints the protocol change above the report table, and a test
      pins the property the experiment rests on: m6 is red 5/10 on the pre-supplied
      tree with only the over-correction guards passing. **184 tests green.**

      **3. What it does not settle.** n=1 per arm, one task, one model — the null is
      "ceremony did not help here". The pre-supplied tree removes compounding by
      construction, so if the lifecycle pays by keeping a multi-task project coherent
      this run was blind to it (meridian-003, 4 tasks cumulative, was not, and found
      nothing either). The kiosk Phase 02 audit datapoint still stands and still
      points the other way — n=1, self-authored plan with wrong premises, the case
      meridian cannot represent. Every negative result on this line is about
      *briefed* work.

      **What changes:** there is no pending experiment left behind which the
      ceremony's quality claim can wait. Three cycles, the last two written to favour
      it, identical delivery and acceptance each time, 2.8-2.9x the cost. **The
      decision this hands the user is whether principle 5 now fires on the shipped
      lifecycle skills (plan/audit/wrap), which is a capability deletion and so is
      not taken unilaterally** — see the next queue item.

- [x] **DECIDE resolved 2026-08-25 — KEEP all three, pending a real-work bar.**
      The three options were: delete the lifecycle skills; keep-but-status-quo; or
      keep and pre-register a real-work bar for the one case still unmeasured. The
      resolution is the third, and the reasoning is the asymmetry the item already
      named. The utilisation deletions (mattpocock listing, flux:review, the agent
      roster) all failed a bar at *zero* utilisation while costing tokens every
      session — deletion bought context back. plan/audit/wrap carry
      `disable-model-invocation: true`, so they cost 0 tokens in a session that does
      not invoke them; deleting them reclaims nothing and only removes an option.
      And that option holds the *only* positive real-work datapoint in the whole
      corpus (kiosk Phase 02, audit caught three false plan premises), in the exact
      case the benchmark cannot represent. Paying a real cost (losing the one tool
      that has ever paid on real work) to buy nothing is a bad trade regardless of
      the three benchmark nulls — which measured *briefed* work, where planning and
      auditing have nothing to recover by construction. wrap in particular is not
      ceremony at all: it is the only carrier of cross-session state, and the
      benchmark scored it as tax only because fluxbench runs one task per fresh tree,
      so there is no next session for it to serve. **What the nulls DID settle stays
      settled:** on well-specified single-session work, reach for `/flux:apply`, not
      the lifecycle — the plan skill says so in its own first paragraph. The
      lifecycle earns its cost only when work spans sessions, is irreversible, or its
      shape is unsettled. The real-work bar that could still move this is
      pre-registered in `.flux/analysis/2026-08-25-realwork-preregistration.md`
      (dogfood flux on a live multi-phase project; keep/remove/add read from a
      pre-committed question set, not post-hoc). Also decided: **grill stays a
      separate skill, not folded into plan** — merging a divergent interrogation
      loop into a convergent one-file planner would uncap plan's cost and fork the
      vendored copy away from `sync-vendored.sh`; the convention is grill → plan when
      a phase's shape is unsettled, documented in the pre-registration note.

- [x] **`meridian-006` — every framework now has real numbers, and the ranking is
      monotone in ceremony. 2026-08-24.** agentos and speckit ran to completion for
      the first time in four attempts; no voids, $34.19 of a $40 cap. Records
      `~/.flux-bench/runs/meridian-006/`.

      Combined with `meridian-005` (same corpus, same model, same harness revision;
      vanilla is the shared yardstick):

      | arm | sessions/task | delivered | accept | $/task |
      |---|---|---|---|---|
      | vanilla (005) | 1 | **5/5** | 109/109 | **$1.10** |
      | flux = prime+apply (003/004) | 1 | 4/4, 1/1 | 100% | $1.05 / $1.75 |
      | agentos (006) | 2 | **5/5** | 109/109 | $1.68 |
      | flux-full (003/004) | 4 | 4/4, 1/1 | 100% | $2.92 / $5.03 |
      | speckit (006) | 4 | **3/5** | 103/109 | $5.16 ($8.60/delivered) |
      | paul (005, m1–m4) | 4 | 4/4 | 82/82 | $5.38 |

      **1. Session count predicts cost; nothing predicts quality.** One-session arms
      cost ~$1.10, two ~$1.68, four $2.92–5.38 — across four independent frameworks
      and flux's own two configurations. Not one of the four bought a delivery or an
      acceptance point with the extra sessions. The trim to prime+apply put flux in
      the cheap band, and this is the widest evidence yet that the band is the whole
      story.

      **2. speckit is the first arm to lose tasks on merit under a fair brief.**
      m2 12/16: every tier boundary and rounding case passes, but
      `meridian/domain/policy.py` was never created — the brief names the module
      (line 26) and the signature `refund_cents(price_cents: int, gap: timedelta)
      -> int` (line 32), so the corpus rule written after meridian-001 died on this
      exact task is satisfied and the loss is fair. m3 26/28, independently:
      `series_id` defaulted to `None` where the brief says `""` (line 8), and
      `GET /series/{series_id}` (line 52) returns 404. **Checked, not assumed** — the
      m3 failures are not a cascade from m2's missing module.
      The shape is the same both times: the behaviour is right, the *stated details*
      of the spec are not honoured. The spec-driven framework is the one that missed
      explicit spec points, while agentos and vanilla scored 100% on the same briefs.

      **3. What this does not establish.** It separates arms on **spec compliance**,
      which is what a complete brief can test — not on the judgment m6 was written
      for. And two tasks is suggestive, not settled: meridian-002's "flux lost m3 on
      merit" did not reproduce. If speckit's pattern matters it will repeat.

- [x] **`m6` — the corpus's first bug report, and the only quality experiment the
      fairness rule permits. Written 2026-08-24.** meridian-004 established that
      **fluxbench cannot measure what ceremony is for**: its rule that tests may bind
      only to seed symbols or briefed API forces complete briefs, and a complete
      brief is the case where planning and auditing have nothing to recover. One
      route was left open — "the check constrains symbols, not behaviour, so a terse
      bug report pinned through seed API only would leave the invariant discoverable
      in the code and nowhere else." m6 is that task.
      **The defect is real and was latent in the corpus's own reference tree, not
      injected.** `confirm_hold` grows a hold's claim from its bare interval to
      interval-plus-changeover, and never re-applies the collision rule. So an
      ordinary three-call sequence — hold 09:00–10:00, book 10:00–11:00, confirm the
      hold — lands two confirmed bookings inside each other's changeover with nothing
      raising anywhere. Reproduced against the post-m5 tree before a line was written.
      No brief covers it: m5 §3 explicitly puts confirmed-vs-confirmed overlap out of
      scope, and m5's acceptance suite sets no buffer at all.
      **The brief names the symptom and nothing else** — 41 lines against m5's 120,
      no file, no function, no rule, no invented symbol. It says outright: "the rule
      this violates is already in this codebase and is already enforced everywhere
      else; find it, and find the path that gets around it."
      **The tests are blind to the mechanism**, which is what keeps it fair. Two
      fixes are legal — refuse the booking that would be trapped, or refuse the
      confirmation that springs it — so the suite pins the *invariant* (no two
      confirmed bookings inside each other's changeover, computed with m1's own
      formula) plus "something refused", never a particular call. That is the
      meridian-001/m2 lesson applied before the fact rather than after.
      **Verified:** `red ok (5/10 before) green ok (10/10 after)`, and the 5 that
      already pass on the unfixed tree are the over-correction guards — a zero-buffer
      space still books back to back, a live hold still claims only its own interval
      (m5, unchanged), released and expired holds still trap nothing. m1/m3/m5
      acceptance all still green under the reference fix (115 tests). 177 repo tests
      green.
      **What it still cannot do:** prove ceremony pays. It creates the *possibility*
      of a quality difference where five runs had none; whether plan/audit finds the
      invariant and one-shot does not is the open question, and m6 is the first task
      that can answer it either way. Run it against vanilla / flux / flux-full when
      the account has headroom.

- [x] **`meridian-005` — PAUL measured fairly at last, and the ceremony tax
      reproduces on someone else's framework. 2026-08-24.** Killed early on the
      account's rate limit (user's call) after the decision-relevant part was banked.
      Records `~/.flux-bench/runs/meridian-005/`, log `/tmp/meridian-005.log`.

      | arm | delivered | accept | $/task | sessions | wall/task | tokens |
      |---|---|---|---|---|---|---|
      | vanilla | **5/5** | 109/109 | $1.10 | 1.0 | 189s | 8.0M |
      | paul | **4/4** (+1 void) | 82/82 | $5.38 | 4.0 | 911s | 31.1M |
      | speckit | void | — | — | — | — | — |
      | agentos | never reached | | | | | |

      **Like-for-like on m1–m4, the four tasks both arms scored:** paul costs
      **6.0x** the dollars ($21.23 vs $3.53), **5.8x** the wall-clock, **6.5x** the
      tokens and 4 sessions per task against 1 — for **identical acceptance**, 82/82
      each. Its diffs run 5–8x larger (m2: 24 files/+1038 against vanilla's 12/+90),
      most of it PAUL's own state artifacts.

      **1. The arm fix is vindicated and meridian-003's `paul 1/4` is formally
      withdrawn.** m2 is exactly where 003 collapsed, and it cleared it 16/16. That
      run was measuring our own misconfiguration (`/paul:verify` where
      `/paul:unify` belonged), never PAUL. **Do not cite the 1/4 again.**

      **2. The ceremony tax is not a flux artifact.** flux's own lifecycle measured
      2.8–2.9x against a one-shot arm; PAUL — the framework flux was distilled from,
      same plan→audit→apply→close shape — costs 6.0x for the same output on the same
      corpus. The finding the trim to prime+apply acted on reproduces on an
      independent implementation. Same caveat as ever, and it is load-bearing: this
      corpus cannot see quality (everyone scores 100%), so this ranks cost and
      nothing else.

      **3. A harness defect that would have republished meridian-002's lie —
      found live, fixed, 6 tests, 177 green.** When the limit returned, the CLI
      reported `terminal_reason: api_error` with an **empty** `api_error_status`.
      Every check in the void machinery keyed on the status code, so nothing
      matched: five speckit sessions that never reached a model were graded as an
      arm delivering **0/19**. `driver.is_transport_failure` now keys on *did this
      reach a model*, not *did it name a code* — covering both shapes — and
      `report._api_status` back-fills the same rule over stored records, so
      meridian-005 re-renders speckit as `void`. Retry still requires a free
      attempt; a billed one voids without a rerun.

      **4. Still unmeasured, third attempt running: `speckit` and `agentos`.** Both
      have now been 429-voided in 002, 003 and 005 without ever attempting a task.
      `paul/m5` also voided (billed 429, correctly not retried). Relaunch
      `--arms speckit,agentos` plus `paul` on `--tasks m5` when the limit clears;
      vanilla's m1–m5 numbers here are the yardstick to read them against.

- [ ] **Decided 2026-08-22: do not adopt `beads` (`bd`).** Investigated at the user's
      request; `bd` 1.2.2 is installed on this machine and used in no repo. It is not
      a backend for flux, it is a peer: `bd prime`, `bd remember/recall`, `bd hooks`,
      `bd setup` and its own `claude-plugin/` overlap flux's session-boundary
      ownership, and only `bd ready` maps to what ADR 0001 asked for. Depending on it
      breaks the binding "no dependencies, no install step, ever" (Go binary + Dolt,
      per machine, per repo) and makes the falsifiability rule expensive — deleting
      300 lines of Python is an afternoon, migrating off a Dolt database is not.
      **Two things worth stealing regardless**: JSONL-in-git rather than a rewritten
      TOML file (which is the answer to the open `.flux/state.toml` conflict problem in
      kiosk's 49-branch repo), and computing `blocked` on read rather than storing it
      (`bd recompute-blocked` exists because stored blocked-flags go stale after a
      pull). Revisit only if the user relaxes the zero-install constraint.
- [ ] Decide whether `bench/realworld/` runs at all, and in which shape — see the
      supersession note above. Cheapest useful version is a one-milestone pilot on
      three arms (vanilla, flux, flux-lite), ~6 sessions, to check the corpus has
      teeth and the analyser works before committing 25–50 operator hours.

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

- [x] **Fixed 2026-08-21 — prime reports drift as two independent legs.** The
      candidate below was found by using yesterday's feature the next day: after
      `git push -u`, kiosk's header went from `3 ahead of origin/main` to **silence**,
      because `_drift_base` preferred the upstream and the branch was in sync with it.
      One base was the wrong model. The upstream answers *"have I pushed?"*; the
      default branch answers *"how far has this branch come?"* — and a feature branch
      needs both. `_ahead_behind` now emits up to two legs, each omitted when zero:

        kiosk  @ chore/retire-gitnexus-for-codegraph, 4 ahead of origin/main
        kiosk  @ chore/...,  1 unpushed, 5 ahead of origin/main
        flux   @ main, 14 unpushed

      The upstream leg says **"N unpushed"** rather than "N ahead of origin/main" —
      shorter, and it's what the number actually means. The default-branch leg is
      skipped when its base *is* the upstream (standing on `main`), so nothing is
      double-reported. `_default_base` never returns the branch you're standing on.
      **Four new tests**, all against a real bare-repo remote: pushed-and-in-sync still
      reports default-branch drift (the regression), unpushed and default drift appear
      as separate legs, `main` reports only `unpushed`, and behind-your-own-upstream
      renders. 73 tests green. Plugin **2.3.0**.

- [x] **Fixed 2026-08-21 — a rate limit is void, not a zero.** Found by reading
      meridian-002's report: it credited `paul` and `flux-lite` with 0/4 deliveries
      when neither arm had reached a model. Retry-then-void in the driver/runner,
      void-aware tables and verdict in the report, shared-task comparison when arms
      scored different sets, and the rule applied retroactively to old records.
      12 tests, 114 green. Full write-up in the benchmark section above.
- [~] **`meridian-003` launched 2026-08-21** on the fixed harness — 6 arms x 4
      tasks, sonnet, $40. meridian-002 answered only flux-vs-vanilla over 3 tasks,
      and the arm that matters most (`flux-lite`, machinery vs ceremony) never ran.
      **Read the report first thing next session.**
- [x] **Done 2026-08-22 — meridian-003 read, and cycle 2 (`meridian-004`) run.
      The lifecycle ceremony has now had its two reporting cycles and moved
      nothing.** Full write-up: `.flux/analysis/2026-08-22-ceremony-two-cycles.md`.

      meridian-003: vanilla / flux / flux-lite all 4/4 at 100% acceptance;
      flux $2.92/task against $1.05 for the other two; paul 1/4 at 31%. speckit
      and agentos void (429s). But **every arm that ran scored 100%**, so that run
      could not have seen a quality difference in principle.

      So `m5` was written to be the case that could: a real feature (holds) whose
      ticket carries a **false claim about the code**, whose rule must land in two
      places that already disagree, and whose "released hold" collapses into
      `CANCELLED`. 27 acceptance tests, verified satisfiable from both the
      cumulative tree and the bare seed before it was allowed to judge anyone.

      meridian-004: **all three arms 27/27, identical fix** (`if not
      booking.is_active: continue`). flux $5.03/task vs $1.75 flux-lite, $1.81
      vanilla. The audit *did* catch the false claim, in as many words, and it was
      worth $0 — the single-pass arms read the brief carefully and got there too.
      Session split: plan $0.94 + audit $1.34 + apply $1.68 + wrap $1.07, where
      **the apply session alone matched the whole one-shot arms**.

      **The structural finding is the important one: fluxbench cannot, by
      construction, measure what the ceremony is for.** Its fairness rule (tests
      may only bind to seed symbols or briefed API) forces complete briefs, and a
      complete brief is exactly the case where planning and auditing have nothing
      to recover. One legal route remains — the check constrains symbols, not
      behaviour, so a terse bug report pinned through seed API only would leave the
      invariant discoverable in the code and nowhere else. That, not m5, is the
      experiment worth running if the question is reopened.

      Against deletion: the ceremony's only real-work datapoint is **positive** —
      kiosk Phase 02's audit returned three blocking findings on a plan that looked
      fine (parent SHA pinned as tip; "local gate is a superset of CI", false; a PR
      body claim the branch contradicted). n=1, unblinded, same model as author.
      And flux's one consistent win in both cycles is **21% lower ctx p50**.

      **Decided and executed 2026-08-22 (user's call): trim to prime+apply, with
      plan/audit/wrap opt-in.** What changed:
      - `skills/apply` no longer requires a plan path — the task as stated is a
        valid spec, and the no-plan path is named as the normal one. It closes with
        `flux state set` rather than `/flux:wrap` when there is no phase to close.
      - `skills/resume`'s routing table leads with `/flux:apply`; `/flux:plan` is
        reached only when work spans sessions, cannot be undone, or is unsettled.
      - `skills/plan` opens by asking whether to plan at all, and routes to apply
        when none of the three conditions holds.
      - Bench arms swapped to match: **`flux` is now prime+apply** (what `flux-lite`
        was) and the lifecycle survives as **`flux-full`**, kept because the case it
        claims is one this corpus cannot represent.
      - `plan.md` amended in place (not contradicted) with the reasoning and the two
        things the amendment does not claim.
      - Plugin **2.5.0** — skills changed, so the cache needs the bump to see them.
- [x] **Fixed 2026-08-23 — the plugin had been failing to load since some Claude
      Code update, and the 2.5.0 skills never reached any session.** `claude plugin
      list` showed `flux@flux-market 2.3.0 ✘ failed to load: Duplicate hooks file
      detected`. Cause and fix in the superseded-install note above. Nothing in the
      suite guarded the manifest, and nothing surfaced the failure — a plugin that
      fails to load is invisible unless you list it. **Two guard tests added**
      (`TestPluginManifest`): the manifest may not reference the auto-loaded
      `hooks/hooks.json`, and `hooks/hooks.json` must still register `flux prime` on
      SessionStart. **153 green.**
- [x] **Phase 03's api line — CLOSED AS A NULL, 2026-08-23. api is not adopted, and
      the boundary is the finding.** Measured before installing anything, because the
      pre-prime corpus cannot be re-measured later. Write-up:
      `.flux/analysis/2026-08-23-api-preprime-baseline.md`.

      Baseline, 19 sessions / 15 reaching an edit, 2026-06-30 → 2026-08-12: median
      ramp **28 calls / 49,769 tok**; per session **frontier 2 calls / 1,111 tok**,
      **code 14 / 16,926**, other 7 / 941, docs 0 / 0.

      **api is not kiosk.** The kiosk win (6 frontier calls / 15,770 tok → 1 / 51)
      came from a 299 KB `.paul/STATE.md` read whole. api's is **33 KB and mostly
      unread**: of 19 transcripts, 2 mention it heavily (both Jul 24–25, the oldest),
      6 mention it once, 11 never. Prime's ceiling in api is ~1.1k of a ~50k ramp — 2%.
      The null was **pre-registered in plan.md before the install**, so it could not
      drift into a claimed win.

      **The gate got the same discipline, with the bar written down first**
      (*median > 5,000 tok of lint/test output per session ⇒ install for `flux check`
      alone*), because reaching for a fresh justification the moment the old one dies
      is the failure mode ADR 0001 already fell into. Result: **median 2,166 tok**
      among the 8 of 19 sessions that ran the gate, **median 0** over all 19. **Not
      cleared.** api's jest/eslint are terse — no gate run is in the corpus's fifteen
      largest Bash results — while kiosk's `nx run-many` emits ~950 lines over 31
      projects regardless. The filter pays against a fan-out runner, not `npm test`.

      **Structural finding, now binding in plan.md ("Where flux pays"): flux's value
      is repo-shaped.** Both measurable surfaces need a specific shape — a bloated
      state artifact read whole, and a fan-out gate. api has neither: its project
      state lives in **GitHub Issues** (`gh issue view`, already frontier-classified,
      and landing after the first edit as work), and its gate is quiet. **Adoption is
      a measurement, not a rollout.** Phase 03 rescoped from "package & generalize"
      to "establish where flux pays".

      Recorded but not acted on: api's Bash volume is **~62.8k chars/session** against
      plan.md's <25k target, and the top of it is `gh issue view` plus **mattpocock
      skill files read whole from the plugin cache** (3 of the 15 largest results,
      18.7k/14.0k/9.7k chars). Instruction loading is the second-largest line item in
      the repo. Neither is a prime problem; both are a claim for a later cycle.
- [x] **Retired the competing frameworks in zaps/api, 2026-08-23** — branch
      `chore/retire-competing-frameworks`, commit `ea3ae6b`, **193 files /
      −32,927 lines, no source touched. Not pushed; `main` untouched.** api had been
      carrying five overlapping context systems: **PAUL** (`.paul/`, 170 files,
      1.8 MB — retirement evidence-backed at 1/4 delivered, 31% acceptance in
      meridian-003), **GitNexus** (`AGENTS.md` was wholly its generated block, the
      same block duplicated atop `CLAUDE.md`, 6 skill files, nav rules in
      `.claude/CLAUDE.md`, plus a 74.8 MB derived `.gitnexus/` index deleted locally —
      no hook regenerates it, `npx gitnexus analyze` rebuilds if ever wanted),
      **CARL** (one orphaned session file), **beads** (`bd init` was at HEAD and had
      been reverted in the working tree without being committed — this completes it),
      and **flux v1 remnants** (a `<!-- flux -->` block naming dead commands
      `/flux:plan`, `/flux:tickets`, `/flux:build`, plus its statusline and gitignore
      entries). Kept `CONTEXT.md` (the domain glossary — the only context doc with
      content nothing else carries), `docs/adr/`, `docs/agents/`, and the stack /
      commands / file-structure / entry-point tables in `.claude/CLAUDE.md`; fixed
      three references the deletions would have orphaned (`docs/agents/domain.md`,
      `.dockerignore`, `.gitignore`). **api was already flux-installed once (v1)** —
      Phase 03 there was a re-install after an abandoned removal, not a fresh one.
- [x] **kiosk PR #66 merged 2026-08-23** (`e8a3199`), and its two loose ends closed
      straight on main at the user's call (one-line, already verified — no PR):
      - `f293528` **the codegraph guard is homed.** `.claude/settings.json`'s
        UserPromptSubmit hook ran `codegraph prompt-hook` unconditionally, so every
        prompt returned 127 for a contributor without the binary. Now
        `command -v codegraph >/dev/null 2>&1 || exit 0; codegraph prompt-hook || exit 0`
        — re-verified to exit 0 with codegraph off PATH, JSON re-parsed before commit.
        This was the task the n=1 prime experiment session was given; the fix it
        produced spent two days uncommitted because writes to `.claude/settings.json`
        were denied in that session.
      - `19861ee` **`.flux/state.toml` is no longer tracked in kiosk** — the open
        question is decided, option (1) of two. It is rewritten wholesale every
        session, and kiosk carries ~100 branch refs, so tracking it guarantees a
        conflict on a file nobody edits by hand. Added to `.flux/.gitignore` with the
        reasoning inline; `git rm --cached`. Verified after: `flux prime` still renders
        the full pack, and a subsequent `flux state set` (6 keys, 1165/8000 bytes)
        left `git status` clean — which is the whole point.
      **Not done, and deliberately: the append-only state format (option 2, the
      JSONL-in-git idea stolen from `bd`) is still the better long-term answer** and
      is unbuilt. Untracking is reversible; the format change is the one that would
      let state travel between clones without conflicting. Revisit if state-per-clone
      turns out to matter.
      Also refreshed kiosk's own state to post-merge reality (phase/position/next/open),
      dropping the three items this session resolved.
- [ ] Phase 03 — remaining: **the first ledger before/after, taken in kiosk**, where a measured delta exists (api cannot
      supply one). Status 2026-08-23: **the after-side is still n=1** — a fresh
      `./bench/run.py ramp` reads kiosk before = 40 sessions / 27 ramp calls / 6
      frontier / 15,770 tok against on/after = 1 / 6 / 1 / 51. There is nothing to
      *take* here on demand: the after-median accrues one datapoint per real
      interactive kiosk session, and the before-corpus keeps eroding under the CLI's
      30-day transcript cleanup. Now that main carries flux, ordinary kiosk work
      feeds it. Re-run `ramp` when a handful more have landed rather than treating
      this as an action.
- [x] **The mattpocock install is RETIRED, 2026-08-23** — reopened the same day on a
      pre-registered *utilisation* bar and uninstalled. Write-up:
      `.flux/analysis/2026-08-23-mattpocock-utilisation-bar.md` (bar committed in
      `ecfcffb`, before a fresh number was read; result in the commit after).
      **The bar, derived not chosen:** `DEFAULT_STATE_BUDGET_TOKENS = 2000`
      (`bin/flux:23`, Phase 01) is the price flux charges *itself* for a permanent
      context slot, and `flux prime` pays off every session — so the rate flux holds
      itself to is **≤2,000 tok per session-of-use**. That anchor predates the question
      and has no view on Matt's skills, which is what makes it a bar after the previous
      write-up published 917/1.6%. The one free choice (raw cost, which passes, vs
      utilisation-adjusted, which fails) is decided *in* the write-up with the losing
      reading named, so disagreement lands on the reasoning, not the arithmetic.
      **Result: fails every cell.** Corpus re-scanned: 517 transcripts, 287
      real-interactive. **9 sessions** had a mattpocock invocation — 3.14% real /
      1.74% all. At the measured 662 tok/session listing that is **21,110 tok per
      session-of-use, 10.6x the bar**; the least favourable cell is 52,734.
      Both denominators agree, which the bar required.
      **Trim was tried first, as pre-registered, and also fails**: all-5-invoked
      = 10,382/session-of-use (5.2x); unvendored-only = 7,388 (3.7x). Hence uninstall.
      **Two corrections to the numbers this repo had published.** (1) The listing is
      **11** advertised skills = **662 tok**, not 15/918 — the four `misc/` skills
      never reach the roster and nothing in their frontmatter explains it.
      (2) Usage attribution had to be tightened to `mattpocock-skills:`-namespaced
      invocations only: bare `/code-review` in `subagents` is the **built-in**, not
      Matt's. That also found `research` (2 calls), which the prior write-up had
      recorded as never invoked. Final tally: grilling 3, writing-for-agents 2,
      research 2, code-review 2, domain-modeling 1; ten skills never invoked once.
      **`claude plugin details` disagrees, and is wrong.** It projects ~1,620 tok
      always-on for mattpocock and ~1,246 for flux — because it bills every skill
      including `disable-model-invocation: true` ones. Direct evidence it over-counts:
      this session's roster contains exactly **one** of flux's 14 skills (`flux:review`,
      the only one without the key). It is a static inventory projection, not a
      measurement. Recorded because it is what a reader running that command sees; the
      verdict is the same either way (10.6x vs 25.8x).
      **The retirement is capability-neutral, as pre-registered.** `research` and
      `writing-for-agents` were the only invoked skills flux did not already carry, so
      both are now **vendored** (`scripts/sync-vendored.sh`, same pin 1.2.3 /
      `2ab9580…`, MIT) with `disable-model-invocation: true` — the bar applies to
      flux's copies too, so they are carried but **not listed**. Dangling `/research`
      and `/writing-for-agents` refs in `wayfinder`/`ask-matt` now rewrite to
      `/flux:research` and `/flux:writing-for-agents`. grilling/domain-modeling/
      code-review were already covered by `/flux:grill` and `/flux:review`.
      **The one real loss**: those two can no longer be model-invoked on the agent's
      own initiative — 4 autonomous calls in 287 sessions is the price. Plugin bumped
      to **2.7.0** so the two new skills publish. Reversible:
      `claude plugin install mattpocock-skills@claude-plugins-official`.
      Note: `claude plugin uninstall` removes the install record but **not** the
      marketplace cache, so `sync-vendored.sh`'s `$SRC` still resolves today — but it
      is orphaned and `claude plugin prune` may take it; pass a checkout as `$1`.
      **The finding worth keeping — carrying a skill is nearly free; listing it is
      not.** The prior write-up said vendoring and the install are alternatives, not a
      stack; this is the proof, executed. "Which of the two owns this skill" and "does
      the model need to see it" are two questions. Ownership went to flux for
      everything with recorded use; visibility went to nobody.
      **Open, and handed to flux:** the bar came from flux's own budget, so it applies
      to **flux's own skill listing** — uncapped, unmeasured, and not contemplated by
      CLAUDE.md's no-uncapped-output rule. Deliberately not settled here; deciding it
      on the back of this session, with no flux-skill utilisation measured, would be
      the exact mistake the pre-registration exists to prevent.
      Superseded note follows (kept for the reasoning that led here):
      **The duplication bar, 2026-08-23 — a pre-registered null.** Write-up:
      `.flux/analysis/2026-08-23-mattpocock-install-cost.md`. Retire if **(a)** the
      unvendored skills were invoked in < 5% of sessions **and (b)** the *duplicated*
      description text costs > 500 tok/session. (a) cleared at 0.5%; **(b) failed at
      113 tok**, because the duplication was mostly imaginary — one genuinely
      duplicated pair (`code-review`, 452 B). The 917-tok utilisation number was
      recorded there and deliberately not used as a bar; this entry is the honest
      reopening it demanded.
      Superseded note follows (kept for the reasoning that led here):
      On the mattpocock retirement: **measure first.** `VENDORED.md` already
      pre-decided that the eight unvendored skills (`/tdd`, `/research`, `/prototype`,
      `/codebase-design`, and the rest) degrade to no-ops on retirement, so the cost
      is known and the case for pulling it is context — api's mining put whole-file
      skill reads from the plugin cache at 18.7k/14.0k/9.7k chars, three of the
      fifteen largest Bash results. Get that number for a session with both plugins
      installed before uninstalling anything.

- [x] **Measure flux's OWN skill listing against the same bar. Done 2026-08-23 —
      it fails by division by zero, and `flux:review` is delisted.** Write-up:
      `.flux/analysis/2026-08-23-flux-listing-utilisation.md`. The bar was not
      re-derived (that would be the tuning the pre-registration forbids); it is
      `ecfcffb`'s, applied verbatim.
      **The numerator is now measured, not projected.** Transcripts record the rendered
      roster directly as an `attachment` of `{"type":"skill_listing","content":…}`. In
      all 52 post-install real sessions flux contributes **exactly one line, 436 B =
      109 tok** (`- flux:review: …`) — 3.1% of a median 12,063 B listing. Under v1 it
      was 5 lines / 1,061 B. The other 13 skills appear in **no** listing in any of the
      520 transcripts: `disable-model-invocation` really does cost zero.
      **`flux:review` has never been invoked — 0 times in 520 transcripts**, by the
      model or the user, and it is the only skill flux advertises. Post-install: 79
      real-interactive sessions, 52 billed, **0** flux skill invocations of any kind.
      Of 54 sessions with any flux invocation, **exactly one** invoked a skill its own
      listing contained (a v1-era `flux:plan`, when the listing was 5 lines). The rest
      are 41 bench sessions (`apply`/`audit`/`plan`/`wrap`, all dmi:true, typed by the
      fluxbench arms) and 12 real v1-era sessions (`build`, `flux-init`, `show-work`,
      `pause`, `sync`) — commands of a retired product.
      **The bar turned out to be ambiguous here in a way it was not for mattpocock, and
      the ambiguity decides the verdict — read the write-up before reusing this.** "Per
      session in which one of its skills is invoked" reads two ways, and mattpocock
      never had to choose because all five of its used skills were also listed. flux
      breaks them apart. **Reading A (any skill in the namespace): post-install
      all-corpus 276 = PASS, real-interactive ∞ = FAILS — which trips the
      pre-registered "if the denominators disagree the bar does not fire" escape, and a
      reader who takes that off-ramp should re-list review (a one-line revert).**
      **Reading B (only the skills it lists) governs and fails everywhere**: 0% both
      denominators post-install, 1.00%/0.65% (9.1x/12.0x) all-time. The tie-break is
      quoted from the pre-registration, not invented after the fact — *"a budget is a
      price for a thing, not a number floating free of what it buys"* (109 tok buys the
      model seeing `flux:review`, nothing else), plus the same *proves-too-much* test
      that killed the raw-cost reading (under A, fifty dead listed skills pass on one
      live unlisted one). Reading A's passing cells are also carried entirely by bench
      self-dealing and by v1 commands that no longer exist.
      **Escalation step 1 (trim to skills with ≥1 invocation) yields the empty set**,
      i.e. `disable-model-invocation: true` on `review`: 109 → **0 tok/session**, bar
      cleared, step 2 (uninstall) not reached and wrong anyway — what flux sells is the
      capped `prime` hook and a CLI on PATH, neither of which is a listing.
      **Capability cost is zero and this time it is measured**: retiring mattpocock
      cost 4 autonomous calls; this costs **0**. `/flux:review` is unchanged.
      Two things checked before accepting non-use as dead rather than benign:
      it was **not substituted** (the built-in `/code-review` ran in 1 real session
      ever, 0 post-install — nobody reviews with a review skill here), and its
      visibility was **never chosen** — upstream `code-review` has no dmi key and
      `sync-vendored.sh` only hid `research`/`writing-for-agents`, so the fix lands in
      the **script** (`hide_skill review`) as well as the file, or the next re-sync
      silently re-lists it. Plugin **2.8.0**, 153 tests green.
      **Reverses on one datapoint**: a single model-initiated `flux:review` call that
      happened *because the line was there*. 109 tok/session buys a slot at 5.45%
      utilisation — one use per 18 sessions. It had 52 and delivered none.
      **The rule this sharpens:** flux passed "carrying is free, listing is not" 13
      times out of 14 and failed on the one skill whose visibility it inherited instead
      of choosing. A listing slot is not a default; it is a falsifiable claim that the
      model needs to see the thing. flux's answer for all 14 is now no — a session
      hears about flux exactly once, from `flux prime`, which is capped and
      load-bearing every time.
      **Re-runnable, unlike last time**: `scripts/skill-utilisation.py <prefix>
      [--since]`, stdlib-only, prints **both readings side by side** so the crux is
      visible to whoever runs it next instead of being resolved silently.
      **Three corrections to the mattpocock entry above, all found by building that
      tool, none changing its verdict.** (1) Count **both** invocation paths — the old
      scan missed `/mattpocock-skills:ask-matt`, 7 calls / 6 sessions, all user-typed:
      15 sessions, not 9. (2) Only sessions that **carried** the listing are a
      denominator — 213 real-interactive, not 287 (and the measured listing is 630
      tok/session, confirming the 662 read off one roster). (3) Reading B applied back
      to it removes ask-matt, to-spec, to-tickets, wayfinder, implement, handoff —
      invoked but never listed. **So that bar was missed by 6.7x (13,421), not 10.6x.**
      Note the governing reading is the *harsher* of the corrected ones, so this is not
      a retreat from the retirement. Appended to the write-up rather than patched in.
      **Left open, same bar, deliberately not settled here — now queued as the next
      task, see the entry below:** the **agent** roster —
      `flux:flux-explorer` + `flux:flux-verifier`, **473 B = 118 tok/session**,
      uncapped, **0** real invocations post-install. Bigger than the skill listing was,
      and agents have no `disable-model-invocation` equivalent, so the trim step may
      not exist. Measuring it is its own task.

- [x] **DONE 2026-08-24 — measure the AGENT roster against the same bar** — the last uncapped
      always-on path flux has, and the one the skill-listing measurement handed on
      (`.flux/analysis/2026-08-23-flux-listing-utilisation.md`). Do not re-derive the
      bar: it is `ecfcffb`'s, 2,000 tok per session-of-use, both denominators, applied
      verbatim. What a fresh session must not spend time rediscovering:
      **The numerator cannot be corpus-measured, and that is the whole methodological
      difference from last time.** Transcripts carry 493 `skill_listing` attachments and
      **zero** agent equivalents; the string `Available agent types` appears in **no**
      transcript. The roster goes into the system prompt, which is not logged. So the
      numerator is either computed from `agents/*.md` or read off one live session —
      i.e. a projection or an n=1 observation, which is **the same weakness this repo
      just used to dismiss `claude plugin details`**. Say so in the write-up rather than
      presenting it as measured. Current computed figure: **473 B = 118 tok/session**
      (flux-explorer 267 B + flux-verifier 206 B), assuming a `(Tools: …)` tail — the
      live rendering names the actual tools, so read the exact line off a live session
      before trusting the byte count.
      **The denominator is solid**: `Task`/`Agent` tool calls whose `subagent_type`
      starts `flux:` are logged and countable. Post-install real-interactive: **0**.
      v1 era: 3 (`chore`, `build`, `deep`) — v1 agent names, a retired product, and
      disqualified for the same reason v1 skill commands were.
      **No ambiguity this time, unlike the skill listing.** Both flux agents are listed,
      so Reading A and Reading B coincide; the crux that decided the skill verdict does
      not arise here. Do not import the argument, just note it does not apply.
      **Pre-register the escalation before writing any fresh number**, reusing
      `ecfcffb`'s ladder verbatim — *the cheapest change that clears the bar, in order* —
      because agents have **no `disable-model-invocation` equivalent**, so the "carry it
      but don't list it" move that saved every skill is unavailable and the ladder has to
      be respecified: plausibly (1) merge flux-explorer + flux-verifier into one agent,
      (2) delete. Honesty caveat that must be stated: this session already published
      118 tok and 0 invocations, so the *direction* of the verdict is visible in advance
      — the pre-registration's value is in fixing **what action follows**, not whether,
      and a bar tuned after the fact would be worthless here.
      **Enumerate the capability cost before acting**, as the bar requires: flux-verifier
      overlaps `flux check` / `flux run --filter` (which already keep raw output out of
      context) and flux-explorer overlaps the built-in `Explore` agent. If the overlap is
      total the deletion is capability-neutral; if not, the loss gets reported as a loss.
      **Tooling**: `scripts/skill-utilisation.py` does skills only. It needs either an
      agent mode or a sibling; its `scan()` already parses `Task`/`Agent` subagent_type.
      **Then stop auditing context.** Two sessions running have been context accounting;
      the falsifiability rule applies to measurement machinery too. The standing build
      item is the append-only JSONL-in-git state format (see the `bd` entry above), which
      is the answer to the `.flux/state.toml` conflict problem and is UNBUILT.

- [x] **Pre-registration (honoured) — the agent roster's escalation ladder, written before any
      fresh number (2026-08-24).** The bar is not re-derived: `ecfcffb`'s, verbatim —
      an always-on injection may cost at most **2,000 tok per session-of-use**,
      `cost = tokens injected per session / share of billed sessions with >=1 invocation`,
      and it must fail on **both** denominators (all-corpus, real-interactive) to fire.
      **The ladder had to be respecified, because agents have no
      `disable-model-invocation`.** Every skill retirement so far was capability-neutral
      because the skill could be carried and not listed; that move does not exist here.
      What replaces it, cheapest change first:
      1. **Trim** — shorten the two `description:` fields so the injected roster costs
         fewer tokens. **Registered as unavailable at zero utilisation**: with 0
         invocations the denominator is 0 and *any* positive cost fails, so trim can
         only be tried if the fresh number finds >=1 real invocation. Stating this now,
         not after, is the point of pre-registering.
      2. **Merge** flux-explorer + flux-verifier into one agent — roughly halves the
         cost. Same constraint: clears the bar only if invocations >= 1.
      3. **Delete both** — the only step that clears a zero-utilisation reading, because
         it is the only one that takes the cost to 0.
      **So the ladder is honestly a two-branch conditional, fixed now:**
      - fresh number finds **>=1 real invocation** and cost/session-of-use <= 2,000 on
        *either* denominator → **PASS, keep both, no action**;
      - **>=1 invocation but fails both** → try (1), then (2), re-measure, then (3);
      - **0 real invocations** → (1) and (2) are arithmetically incapable of clearing it,
        so the action is **(3) delete**, conditional on the capability audit below.
      **Capability cost is enumerated before acting, and a loss is reported as a loss.**
      Registered hypothesis: `flux-verifier` overlaps `flux check` / `flux run --filter`,
      which already keep raw output out of context; `flux-explorer` overlaps the built-in
      `Explore` agent. If either overlap is partial, the deletion still happens but the
      residue is written down as capability given up, not argued away.
      **Two method weaknesses registered in advance, both of which weaken the numerator
      and neither of which is a reason to skip the measurement:**
      (a) the roster is injected into the system prompt and **not logged** — 493
      `skill_listing` attachments exist, zero agent equivalents — so the numerator is a
      projection from `agents/*.md` or an **n=1 read off one live session**, exactly the
      weakness this repo used to dismiss `claude plugin details`. It is reported as such.
      (b) there is no per-session record of *carrying* the roster either, so "billed"
      cannot be tested the way `bytes > 0` tested it for skills; it is proxied by
      **install date** (user-scoped plugin ⇒ every project after it). The denominator
      itself — `Task`/`Agent` `subagent_type` — **is** logged and is solid.
      **Not imported from the skill measurement:** its Reading A / Reading B ambiguity.
      Both flux agents are listed, so the two readings coincide here.
      **Honesty caveat.** `473 B = 118 tok, 0 invocations` was already published in
      `6c9a8f6`, so the *direction* of this verdict is visible before the measurement.
      The pre-registration buys the **action**, not the suspense — and a ladder written
      after the number would be worth nothing at all.

- [x] **RESULT 2026-08-24 — the agent roster FAILS at zero; both agents are deleted.**
      Full write-up: `.flux/analysis/2026-08-24-agent-roster-utilisation.md`. Re-runnable:
      `python3 scripts/skill-utilisation.py flux: --agents --since 2026-08-20 --roster-bytes 505`.
      **The number:** 505 B = **126 tok/session** injected into every session in every
      repo; **0** invocations of either agent in **273** billed sessions (89
      real-interactive); **0.00% utilisation on both denominators**; cost per
      session-of-use **undefined, because the denominator is zero**. Harder than the
      skill listing's failure — there is no multiple to quote. And it is not "0 since
      install": it is **0 across all 537 transcripts**. The only `flux:` agent calls ever
      logged are 3 from 2026-08-11 (`flux:chore`/`build`/`deep`) — v1 names, retired
      product, disqualified as the v1 skill commands were.
      **Correction to publish:** the figure carried in `6c9a8f6` and the previous
      analysis, **473 B = 118 tok, is wrong — it is 505 B = 126 tok**. The earlier count
      omitted the `flux:` namespace prefix the harness prepends. 7% understated; verdict
      unaffected.
      **Method, stated as the weakness it is (the pre-registration required this).** The
      numerator cannot be corpus-measured — 493 `skill_listing` attachments exist and
      **zero** agent equivalents, because the roster is injected into the system prompt
      and never logged. So it was both **projected** from `agents/*.md` and **read off
      one live session**, which agreed exactly at 505 B. Agreement of a projection with
      an n=1 observation is not a corpus, and this is the same class of evidence the repo
      used to dismiss `claude plugin details`. "Billed" is a proxy too — nothing records
      a session as *carrying* the roster, so agent mode assumes a user-scoped plugin
      bills every session after install (`--since`), and now warns if run without it.
      **The half that decides it is solid**: `subagent_type` on `Task`/`Agent` calls is
      logged, and the zero is measured. A weak numerator can only set how badly it fails,
      and at a zero denominator that is undefined anyway.
      **Why the ladder had to be rewritten, which is the transferable finding:** at zero
      utilisation, **trim and merge are arithmetically incapable of clearing the bar** —
      any positive cost over a zero denominator fails. Deletion was not the harshest rung
      here, it was **the only rung that exists**. Registered in `88ce1a8` before the read.
      **Capability given up, reported as loss, not argued away:** (a) flux-verifier's
      pre-existing-failure check (reproduce on a clean stash, say so) — `flux check`
      cannot do that, and it is gone; its main job was already done in code by
      `apply_filter`. (b) flux-explorer's `model: haiku, effort: low` cost pin, which the
      built-in `Explore` does not offer. Its format rule is largely duplicated by
      `Explore`. Corpus settles the preference: in the same 537 transcripts,
      `general-purpose` 47 / `Explore` **13** / `flux-explorer` **0**.
      **The one assumption that could reopen it:** that no frontmatter key hides an agent
      from the roster while keeping it invocable. Inherited, not re-verified here.
      **Changed:** `agents/` deleted entirely; `apply`/`adopt`/`plan` rerouted to the
      built-in `Explore` and to `flux check` / `flux run --filter`; plugin **2.9.0**;
      `scripts/skill-utilisation.py --agents` added (labels its numerator `projected`
      everywhere it prints it). 153 tests green — and the 6,000 B skill budget caught the
      first `apply` rewrite at 6,169 B and forced it back down, unprompted.
      **The line this closes: flux now injects nothing the model can see except `prime`.**
      0 of 14 skills model-visible, 0 agents. Every uncapped always-on path flux ever had
      has now met the same pre-registered bar and **every one failed** — mattpocock 6.7x,
      `flux:review` zero, the agent roster zero. **A listing slot is not a default, and
      neither is an agent**: both were bought by inheritance (upstream frontmatter;
      a scaffold's `agents/` directory), neither ever carried a falsifiable claim that
      the model must see the thing, and when one was demanded none survived.

- [x] **BUILT 2026-08-24 — the append-only state format. `.flux/state.toml` is
      retired; state is `.flux/state.jsonl` and git merges it.** ADR
      `.flux/adr/0002-append-only-state.md`. This is the standing build item the last
      three sessions kept deferring, and the second of the two ideas the `bd` entry
      above marked worth stealing without taking the dependency.
      **The format:** one record per key per write — `{"ts","k","v"}`, appended, never
      rewritten. `flux init` writes `.flux/.gitattributes` with
      `state.jsonl merge=union`, so two branches that appended both keep their
      records; **replay resolves it last-write-wins and git never has to decide.**
      **Three things fall out, each the point rather than a side effect:** `updated`
      is now **derived** from the newest surviving record instead of stored (stored, it
      was one guaranteed-divergent line per session on a file every branch rewrote —
      the conflict in miniature); an **empty value clears a key**, which the rewritten
      file could only do by hand-edit; and `flux state log [N]` shows the **superseded
      value**, which is the one thing an append-only format buys that a rewrite cannot
      — the 2026-08-22 silent-corruption defect (`--phase` written as a key) had no
      recovery path at all.
      **The cap, because CLAUDE.md forbids uncapped stored state and an append-only
      file is uncapped by construction:** `flux state compact` collapses to one record
      per live key, and `state set` fires it automatically past **8x the rendered
      budget** (64 KB at the 2,000-token default). Compaction is deterministic — same
      records in, byte-identical file out — so two clones that compact independently
      agree rather than diverging on the fix for divergence.
      **The budget prices the pack, not the log**, checked *before* appending, so an
      over-budget write leaves the log exactly as it was (the guarantee the rewritten
      file gave). Billing storage would have strangled the format on day one; a test
      pins it — ten rewrites of one key grow the log and not the pack.
      **Migration is one-way on first write** and **removes `state.toml`**: leaving it
      leaves a stale second copy of the file a human reads to learn where a project is.
      Before that first write `read_state` still renders the TOML — every adopting repo
      has one and `prime` must not go blank waiting for a `set`. Run live here: 5 keys
      migrated, `prime` renders identically, `git status` shows the swap.
      **18 tests, 171 green. The two that matter run a real `git merge`**: same-key
      writes on two branches merge clean and the newer wins — and the **control is in
      the suite**, the same two sessions against the old `state.toml` conflicting. Also
      guarded: an unparseable line (conflict marker, truncated write) is skipped and
      `prime` still renders, because this is the file that carries the project.
      Plugin **2.10.0** — `bin/flux` is hook-invoked.
      **Ledger metric (ADR 0002): merge conflicts touching `.flux/state.*` per
      reporting cycle, target 0, measured in kiosk** — the only adopting repo with the
      branch count to produce one. **Delete condition:** if after two cycles
      `state.jsonl` is still untracked everywhere, the format bought nothing untracking
      did not, and it reverts.
      **The adoption step — DONE in kiosk 2026-08-24, `728adf8`, pushed to
      `zaps-io/kiosk` main.** The
      `state.toml` line is out of kiosk's `.flux/.gitignore` (it had been added by
      `19861ee`), `flux state set` migrated the 5 live keys one-way and removed the
      TOML, and `.flux/state.jsonl` + `.flux/.gitattributes` are committed on `main`
      in a repo with **101 branches**. Two checks in the real checkout, not the suite:
      `git check-attr merge -- .flux/state.jsonl` reports `union`, and a live test —
      two branches off `main`, each `flux state set next <...>`, merged — came back
      **clean: 0 unmerged paths, both records kept, replay returned the newer**
      (temp branches deleted, `main` left at the adoption commit). Kiosk's `position`
      was rewritten in the same write to describe the log rather than the untracking.
      **Cycle 1 of the two-cycle delete condition starts here**; the count is now 0
      for the right reason, and the next move is to read it, not to build.
      **UNVERIFIED, and it decides what the metric measures:** the clean merge above
      was a *local* `git merge`, which reads `.flux/.gitattributes` from the checkout.
      Kiosk lands work through **GitHub PRs**, and whether GitHub's server-side merge
      honours `merge=union` is untested here — if it does not, a two-branch same-key
      write conflicts in the PR and the local result says nothing about the ledger.
      Settle it the first time two live kiosk branches both write state (or with one
      throwaway PR), before reading cycle 1. Branches cut before `728adf8` are not the
      risk: they have no `state.jsonl`, so taking main is an add, not a merge.
      **Not claimed:** conflict-*free* (a rebase or a hand-edit can still conflict —
      replay survives it), merge semantics (it is last-write-wins; the loser is
      preserved and visible in `flux state log`), or any context saving — the pack
      `prime` renders is byte-identical to before. This buys durability across clones,
      not tokens.

## Session-close checklist (execute at the end of EVERY working session)

1. `flux check` green (or the failure documented here).
2. `flux state set` — phase/position/next reflect reality.
3. Update this file: current state, queue, anything a fresh session must not re-derive.
4. Commit (docs included). Never leave the repo dirty across sessions.
