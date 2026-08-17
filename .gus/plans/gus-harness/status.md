# gus-harness — status & next task

Updated: 2026-08-17 (planning session; no code written yet)

## Current state

- Planning complete: `plan.md` (v2.1), `design.md` (mechanism contracts), ADRs 0001–0009.
- **No code exists.** No `pyproject.toml`, no package, beads not installed, no tooling set up.
- Open decisions: substrate memo (T1), repo-map tool choice (repowiki map vs RepoMapper, part
  of T4/M0).

## Task queue — do the first unchecked item

- [ ] **T1 — Substrate decision (pre-M0).** Either (a) run the timeboxed spikes: implement a
  two-stage flow with a gate between them in Archon and in Gas City, score each on the 4-point
  scorecard in plan.md §5 Pre-M0, assess beads-1.0 molecules; or (b) if the user opts to skip
  spiking, adopt the default hypothesis (custom Python wins). **Either way**, write the decision
  memo to `.gus/plans/gus-harness/substrate-memo.md` (decision, scorecard or "not spiked —
  default hypothesis adopted", molecules note, revisit-at-phase-gates rule) and check this box.
- [ ] **T2 — M0 step 1: package skeleton + Executor + metrics.**
  Scaffold: `uv init` (package `gus`, Python ≥3.12), ruff/pyright/pytest configured, `gus` CLI
  entry point (`cli.py`) with stub subcommands. Implement `src/gus/executor/` (the `Executor`
  protocol, `ExecConfig`, `ExecResult`, `PromptPack`, `ClaudeAgentSDKExecutor`) and
  `src/gus/metrics/` (JSONL writer + `gus metrics` report) per design.md §1/§3.
  **Billing (ADR 0010):** executor preflight asserts subscription auth and strips
  `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN` from the child env; no API-fallback code paths yet
  beyond detect-and-park.
  **Done when:** one real `Executor.run()` round-trip **on subscription auth** with explicit
  model/effort completes and writes a correct metrics line (billing mode recorded); a test
  proves API keys are stripped from the child env; unit tests cover config validation and
  metrics aggregation with the executor stubbed; gates green.
- [ ] **T3 — M0 step 2: runner spine, no LLM.**
  `src/gus/runner/`: checkpoint store (atomic tmp+rename under `.gus/state/<ticket>/`),
  transition function, `run_ticket()` loop with artifact validation + one-retry-then-park, per
  design.md §1. Executor stubbed throughout.
  **Done when:** pytest proves — completed stages skip on rerun; kill-mid-stage resumes
  cleanly; review↔fix loop parks after `max_review_iters`; a missing required artifact parks
  after exactly one retry.
- [ ] **T4 — M0 step 3: gates + first end-to-end ticket.**
  `src/gus/gates/` subprocess wrappers (Python target first: ruff/pyright/pytest + coverage),
  `gus init` scaffolding `.gus/` + `.gitignore` in a target repo, minimal implement-stage using
  the real executor, repo-map tool chosen and wired (`repowiki map` vs RepoMapper — pick
  whichever ranks the test repo better, note choice here).
  **Done when:** M0 exit benchmark (plan.md §5): a trivial hand-written ticket flows through one
  implement stage + gates end-to-end in a scratch target repo; `gus metrics` prints per-stage
  cost/time.
- [ ] **T5 — M1: full five-stage pipeline + hardening + A/B baseline** (expand into subtasks
  when reached; specs in plan.md §5 M1 and the design.md stage I/O table).

## Session-close checklist (execute before ending any working session)

1. Gates green (`uv run ruff check . && uv run pyright && uv run pytest`) — once T2 exists.
2. Commit with a descriptive message.
3. Update this file: current state, check off / re-scope queue items, add a log entry with any
   surprises, deviations from design.md, or decisions made (new ADR if load-bearing).

## Log

- 2026-08-17 — ADR 0010: subscription-first billing. Executor rides logged-in subscription
  auth; API billing only behind the approved fallback ladder; economics reframed to tokens +
  usage-window; caps in turns/tokens not USD; limit-hit → park + resume at window reset.
- 2026-08-17 — Repo created. Plan v1 written, then revised to v2.1 (change doc incorporated:
  metrics+A/B as P0, executor interface, buy-not-build knowledge layer, beads 1.x, re-sequenced
  milestones). design.md written. ADRs 0001–0009. CLAUDE.md + this status file added as the
  fresh-session bootstrap. No code yet.
