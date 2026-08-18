# flux-harness — status & next task

Updated: 2026-08-18 (T3 done: runner spine — checkpoints, transition fn, run_ticket)

## Current state

- Planning complete: `plan.md` (v2.1), `design.md` (mechanism contracts), ADRs 0001–0010.
- **T1 done.** Substrate spikes run hands-on (Archon 0.9.0 live end-to-end, Gas City 1.4.1
  to the orchestration layer); decision memo at `substrate-memo.md`: **keep custom Python**,
  adopt beads molecules as the pipeline container (at M4/D2), steal Archon's per-node
  event-log shape for A2 metrics. beads (bd) 1.2.1 installed via Homebrew, pin `1.x`.
- **T2 done.** Package scaffolded (`uv`, Python ≥3.12, ruff + pyright *strict* + pytest, all
  green). `src/flux/executor/` holds the ADR 0007 seam (`Executor` protocol, `ExecConfig`,
  `ExecResult`, `PromptPack`, `ClaudeAgentSDKExecutor`, `StubExecutor`) and the ADR 0010
  billing preflight; `src/flux/metrics/` holds the JSONL store + `flux metrics` report.
  `flux` CLI has stubs for init/index/research/plan/tickets/run/status, plus working
  `metrics` and a new `doctor`. 126 tests; live round-trip verified on subscription auth.
- **T3 done.** `src/flux/runner/` holds the whole spine: `context.py` (`TicketContext`,
  `RunnerConfig`), `artifact.py` (`ArtifactSpec` + runner-side validation + retry nudge),
  `stage.py` (`Stage`/`Gate` protocols, `Outcome`), `checkpoint.py` (atomic checkpoint +
  `run.json` store), `transition.py` (`Pipeline`, pure `next_stage`), `loop.py` (`run_ticket`).
  Crash-safe writes live in `src/flux/fsio.py`. 203 tests, all four T3 proofs covered.
- **Executor is usable now.** `ClaudeAgentSDKExecutor().run(pack, cfg)` works end to end and
  writes correct metrics lines. The runner drives any `Executor`; tests use fakes in
  `tests/fakes.py` (`FakeStage`/`FakeGate`/`FakeExecutor`) and never touch the SDK.
- **What T4 plugs into.** Implement `Stage` (five of them) and `Gate` (subprocess wrappers),
  hand `run_ticket(ticket, Pipeline(stages=...), executor)` the result. Nothing in the loop
  needs to change to add a stage.
- Open decisions: repo-map tool choice (repowiki map vs RepoMapper, part of T4/M0).

## Task queue — do the first unchecked item

- [x] **T1 — Substrate decision (pre-M0).** Either (a) run the timeboxed spikes: implement a
  two-stage flow with a gate between them in Archon and in Gas City, score each on the 4-point
  scorecard in plan.md §5 Pre-M0, assess beads-1.0 molecules; or (b) if the user opts to skip
  spiking, adopt the default hypothesis (custom Python wins). **Either way**, write the decision
  memo to `.flux/plans/flux-harness/substrate-memo.md` (decision, scorecard or "not spiked —
  default hypothesis adopted", molecules note, revisit-at-phase-gates rule) and check this box.
- [x] **T2 — M0 step 1: package skeleton + Executor + metrics.**
  Scaffold: `uv init` (package `flux`, Python ≥3.12), ruff/pyright/pytest configured, `flux` CLI
  entry point (`cli.py`) with stub subcommands. Implement `src/flux/executor/` (the `Executor`
  protocol, `ExecConfig`, `ExecResult`, `PromptPack`, `ClaudeAgentSDKExecutor`) and
  `src/flux/metrics/` (JSONL writer + `flux metrics` report) per design.md §1/§3.
  **Billing (ADR 0010):** executor preflight asserts subscription auth and strips
  `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN` from the child env; no API-fallback code paths yet
  beyond detect-and-park.
  **Done when:** one real `Executor.run()` round-trip **on subscription auth** with explicit
  model/effort completes and writes a correct metrics line (billing mode recorded); a test
  proves API keys are stripped from the child env; unit tests cover config validation and
  metrics aggregation with the executor stubbed; gates green.
- [x] **T3 — M0 step 2: runner spine, no LLM.**
  `src/flux/runner/`: checkpoint store (atomic tmp+rename under `.flux/state/<ticket>/`),
  transition function, `run_ticket()` loop with artifact validation + one-retry-then-park, per
  design.md §1. Executor stubbed throughout.
  **Done when:** pytest proves — completed stages skip on rerun; kill-mid-stage resumes
  cleanly; review↔fix loop parks after `max_review_iters`; a missing required artifact parks
  after exactly one retry.
- [ ] **T4 — M0 step 3: gates + first end-to-end ticket.**
  `src/flux/gates/` subprocess wrappers (Python target first: ruff/pyright/pytest + coverage),
  `flux init` scaffolding `.flux/` + `.gitignore` in a target repo, minimal implement-stage using
  the real executor, repo-map tool chosen and wired (`repowiki map` vs RepoMapper — pick
  whichever ranks the test repo better, note choice here).
  **Done when:** M0 exit benchmark (plan.md §5): a trivial hand-written ticket flows through one
  implement stage + gates end-to-end in a scratch target repo; `flux metrics` prints per-stage
  cost/time.
- [ ] **T5 — M1: full five-stage pipeline + hardening + A/B baseline** (expand into subtasks
  when reached; specs in plan.md §5 M1 and the design.md stage I/O table).

## Session-close checklist (execute before ending any working session)

1. Gates green (`uv run ruff check . && uv run pyright && uv run pytest`) — once T2 exists.
2. Commit with a descriptive message.
3. Update this file: current state, check off / re-scope queue items, add a log entry with any
   surprises, deviations from design.md, or decisions made (new ADR if load-bearing).

## Log

- 2026-08-18 — **T3 done.** Runner spine landed; gates green; 203 tests (was 126). All four
  acceptance proofs are in `tests/test_run_ticket.py`. Decisions and refinements worth
  carrying (design.md §1 amended in place, no ADR needed):
  - **`done(stage)` = checkpoint exists *and* `ok=True`.** design.md said "checkpoint
    exists". A stage that ran but did not stand (gate failure, self-park) would then be
    skipped on resume, which is the wrong reading — so a not-ok checkpoint is kept for
    triage and the stage reruns once unparked.
  - **The review-loop counter moved out of `review.done.json`** into
    `.flux/state/<ticket>/run.json`, because turning the loop means *deleting* the review
    checkpoint. `run.json` also holds `open_findings`, `human_accepted`, `stage_runs`, and
    the park record. `review_iterations` increments when a review pass completes, so
    `max_review_iters=3` = three reviews and two fixes, then park.
  - **`human_accepted` continues to `pr`** rather than terminating the ticket (design.md's
    sketch returned `None`). Signing off on findings should not skip the PR stage.
  - **Two hard stops bypass the retry and park immediately:** a usage-window rejection
    (ADR 0010) and a session that blew `ExecConfig.max_tokens` — this is where T2's
    flux-side token budget is actually enforced. Retrying either costs more and fixes
    nothing.
  - **A failed session (`ok=False`) takes the same path as a missing artifact:** one retry
    with a nudge, then park; the park reason distinguishes them (`session-failed` vs
    `artifact-invalid`).
  - **One metrics line per executor call, failed attempts included.** Dropping the failed
    attempt would understate what a ticket cost, which is the one thing the store exists for.
  - **A crash is not a park.** Unexpected exceptions propagate; no checkpoint is written so
    the stage reruns. `stage_runs` is persisted *before* the stage runs, so a crash loop
    still terminates. `max_stage_runs` (default 40) is the backstop for a stage that
    completes without ever checkpointing.
  - `flux status <ticket>` now works — a pure read of the checkpoint files, as design.md
    said it would be. It does not print the *next* stage: that needs the concrete pipeline,
    which arrives with T4. `flux run` stays stubbed until there are real stages to run.
  - New shared module `src/flux/fsio.py` (tmp → fsync → `os.replace` → fsync dir). T4's
    stages should write their artifacts through it too.
  - Tests import `tests/fakes.py` as a top-level module (pytest's rootdir insertion);
    `[tool.pyright] extraPaths` was **not** needed — pyright resolves it from the file's
    own directory.

- 2026-08-18 — **Renamed gus → flux** (Fast Loop Unified eXecution). Package `src/flux/`, CLI
  `flux`, artifact namespace `.flux/`, env var `FLUX_LIVE_TESTS`, `FluxError`; docs and ADRs
  rewritten in place. The GitHub repo `ajmalali/flux` — which held an unrelated earlier
  Claude Code plugin of the same name — was replaced with this history; its prior state is
  preserved on the remote branch `archive/plugin-flux`. Gates green after the rename.

- 2026-08-18 — **T2 done.** Skeleton + executor seam + metrics store landed; gates green;
  one live round-trip on subscription auth (Haiku, effort=low) wrote a correct metrics line
  and `flux metrics` printed per-stage tokens/time. Findings that shape later work:
  - **Preflight primitive found:** `claude auth status --json` returns
    `{loggedIn, authMethod, apiProvider, apiKeySource, subscriptionType, email}`. `apiKeySource`
    appears **only** when an API key is overriding the subscription login (and blanks out
    `email`/`subscriptionType`) — that field is the ADR 0010 check.
  - **Credential strip must happen in the parent.** The SDK spawns the CLI with
    `{**os.environ, **options.env}` (`_internal/transport/subprocess_cli.py`), so `options.env`
    can *set* but never *unset* an inherited var. flux therefore deletes
    `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN` from `os.environ` before spawning; a test asserts
    on the reproduced merge, and a second test pins the SDK behaviour that forces this.
  - **Deviation from design.md §1 (`max_tokens`):** the SDK's `task_budget` → `--task-budget` is
    model-gated. Haiku 4.5 rejects it with `400 This model does not support user-configurable
    task budgets`. So `ExecConfig.max_tokens` is now a **flux-side** budget (recorded, enforced by
    the runner) and sending it to the API is opt-in via `advertise_token_budget=False`.
    `max_turns` is the cap that always applies. Not ADR-level, but design.md should say so.
  - **The SDK raises on terminal CLI errors** (turn cap, budget cap, API error) — a bare
    `Exception` from the message stream, not an error `ResultMessage`. The executor converts
    those to `ExecResult(ok=False)` so the runner can retry/park, and re-raises typed
    `ClaudeSDKError` (missing CLI, dead process) as genuine environment faults.
  - **Window pressure has a real signal:** `RateLimitEvent` carries
    `{status, rate_limit_type: "five_hour", resets_at, utilization}`. Captured into
    `ExecResult.window` and the metrics line, so ADR 0010's park-on-limit + resume-at-reset has
    its input. `utilization` came back `None` on these runs — status/`resets_at` are reliable,
    utilization may not be.
  - **Billing surface is verifiable per run:** `ResultMessage.model_usage[...]["provider"]`
    reports `firstParty`. Recorded as `MetricRecord.provider` so a silent policy shift shows up
    in the history, not just in a preflight that ran hours earlier.
  - **Stage sessions inherit the target repo's CLAUDE.md** via `setting_sources=["project"]`.
    A context pack that merely *names* files provoked 6 Read calls and blew `max_turns=3`.
    Reinforces design.md §2: the hydrator must resolve slices into the pack rather than pointing
    at paths, and stage `max_turns` needs headroom.
  - Added `flux doctor` (not in plan.md §4's command list) — it runs the preflight and reports
    auth, provider, what was stripped, and any billing redirects.
  - Tooling note: pyright runs in **strict** mode; `ruff format` is used but is not one of the
    three gates.

- 2026-08-17 — **T1 done (spiked, option a).** Both substrates run hands-on in scratchpad.
  Archon 0.9.0: full two-stage-with-gate live run on subscription auth; gate fail → bounded
  fix loop → review worked; `when:` skip verified both ways; per-node tokens/cost_usd in its
  event store. Killer: YAML config fields are not substitution surfaces — `model:
  "$node.output.model"` went to the API as a literal (404). Gas City 1.4.1: v2 formula with
  `[steps.check]` pytest gate compiled/cooked into beads, condition-skip + `--var`
  parameterization verified; `check.max_attempts` is a typed int (no vars); live agent leg
  stalled on unwired provider in the minimal template — timeboxed out, runtime weight
  (launchd supervisor, tmux, dolt) argues against adoption anyway. beads 1.2.1 molecules:
  **positive** — poured the exact 5-stage pipeline (tests→implement→review→fix→pr, human
  gate, dependency-gated readiness) from a bd formula with zero Gas City. Decision: keep
  custom Python; memo at `substrate-memo.md`; revisit only at phase gates. Surprises worth
  keeping: Archon runs cleanly on subscription login and surfaces the five-hour-window
  rate-limit status in run logs (useful for ADR 0010 park-on-limit); bd 1.x formulas live
  in `.beads/formulas/*.formula.toml` (note the double extension).
- 2026-08-17 — ADR 0010: subscription-first billing. Executor rides logged-in subscription
  auth; API billing only behind the approved fallback ladder; economics reframed to tokens +
  usage-window; caps in turns/tokens not USD; limit-hit → park + resume at window reset.
- 2026-08-17 — Repo created. Plan v1 written, then revised to v2.1 (change doc incorporated:
  metrics+A/B as P0, executor interface, buy-not-build knowledge layer, beads 1.x, re-sequenced
  milestones). design.md written. ADRs 0001–0009. CLAUDE.md + this status file added as the
  fresh-session bootstrap. No code yet.
