# flux-harness — status & next task

Updated: 2026-08-19 (**direction review → ADR 0011**: T5.5 cut, M2/M3 frozen, the A/B quality axis found flawed. Next: T5.5a, acceptance-judged quality on both arms)

## Current state

- **2026-08-19 direction review (ADR 0011) — read this first.** The repo was scored against
  the six goals flux exists for: (1) automate the deterministic layers; (2) offload/rehydrate
  context, state on disk; (3) smart-zone chunking with fresh-context continuation; (4)
  per-ticket model/effort routing; (5) token efficiency and speed with quality held; (6)
  benchmark vs vanilla. Verdict: the substrate (goals 1–2) is right; the sequencing was wrong —
  goals 3–4 were scheduled last and goal 6 had machinery but no data. Three findings a future
  session must not re-derive:
  1. *The A/B quality axis cannot detect an unimplemented feature.* Quality in `metrics/ab.py`
     is an ordinal over the repo's gate suite, so a vanilla arm that changes nothing keeps the
     suite green, scores quality 2 at near-zero cost, and wins the pairing — the kill-criterion
     can fire against a harness that delivered. Fix first (T5.5a): both arms judged by the same
     held-out acceptance tests, written before either arm runs. No verdict computed before that
     lands is trusted.
  2. *Cross-stage prompt-cache hits mostly do not exist.* `PromptPack.stable_prefix` claims
     them, but the system prompt varies per stage and precedes user content, and stages run on
     different models. Within-session caching is real; design.md §2 is amended, `types.py`'s
     docstring catches up at T5.5a. No design decision may cite cross-stage cache hits until
     measured.
  3. *Goal 5 is structurally at risk, not incidentally.* Five fresh sessions plus three
     gate-suite reruns per ticket regardless of size; the only live pairing cost 1.41x
     vanilla's tokens. The answer is routing (T5.7: per-ticket stage list) and continuation
     (T5.8: budget hit → re-hydrate and continue, not park) — not more stages.
  Consequences: T5.5 (review bake-off) cut; M2/M3 frozen; queue is T5.5a → T5.6 (expanded
  benchmark) → T5.7 → T5.8. Docs amended: plan.md §5, design.md §2/§3, CLAUDE.md, ADR 0011.
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
- **T4 done. M0's exit benchmark is met.** `src/flux/gates/` (subprocess gates + `flux.proc`),
  `src/flux/config.py` (`.flux/flux.toml`), `src/flux/scaffold.py` (`flux init`),
  `src/flux/git.py` (stage commits), `src/flux/tickets.py`, and `src/flux/stages/implement.py`.
  CLI: `init`, `run` (with `--dry-run`), `unpark` are real; `status` now names the next stage.
  362 tests. **Live run verified**: a hand-written ticket in a scratch repo went brief →
  implement → `lint`+`test` gates → tagged commit → `flux metrics` per-stage line, in 30s for
  5.5k uncached-in / 2.5k out.
- **Executor is usable now.** `ClaudeAgentSDKExecutor().run(pack, cfg)` works end to end and
  writes correct metrics lines. The runner drives any `Executor`; tests use fakes in
  `tests/fakes.py` (`FakeStage`/`FakeGate`/`FakeExecutor`) and never touch the SDK.
- **What the rest of T5 plugs into.** One more `Stage` implementation against the same protocol,
  added to `flux.stages.build_pipeline`. Four stages are in (`tests`, `implement`, `review`,
  `fix`) and the runner has not changed to accept any of them — including the two that turn the
  review loop, which the transition function has been driving since T3 with fakes. That is the
  spine doing its job.
- **T5.1 done — the harness can now be compared against not having it.** `src/flux/ab.py`
  (`flux run <ticket> --vanilla`: the ticket text, no pack, no repo map, no artifact contract,
  then the same gates) and `src/flux/metrics/ab.py` (paired per-ticket table, the `vanilla_every`
  cadence, and a machine-checked kill-criterion `flux metrics` prints whether or not it is
  welcome). 432 tests. **First live pairing, and it went against the harness**: on a trivial
  ticket in a scratch repo both arms passed the gates and the harness cost **1.41x** the tokens
  (13.8k vs 9.8k billable) — cheaper on turns (9 vs 14) and wall time (32s vs 38s), dearer on
  tokens. n=1 on a toy ticket proves nothing except that the measurement works, which was the
  deliverable. Two more samples in that direction and the criterion fires.
- **T5.2 done — the pipeline is two stages, and the hardening is structural rather than asked
  for.** `src/flux/testrun.py` (the opaque runner, now also the `pytest` gate summariser, so the
  two cannot drift), `src/flux/executor/guard.py` + `src/flux/stages/guards.py` (the `PreToolUse`
  path policy as flux data, compiled to SDK hooks by `sdk.py` alone), `src/flux/stages/tests.py`
  (`TestsStage`, `tests.json`, the runner-verified red step), a `[tests]` block in `flux.toml`,
  and held-out tests as a per-ticket gate at implement time. 501 tests.
  **Live run verified** on a scratch repo: brief → tests stage (2 tests, verified red,
  `first assertion: ModuleNotFoundError`, clean collection) → implement stage → `test` and
  `held-out` gates both green → two tagged commits, 21.9k uncached-in / 4.3k out over 57s.
- **The three things a future session should not re-derive about T5.2.**
  1. *A red step is not "the suite is red".* It is: no collection errors, nothing passing, at
     least one failure. The awkward case is the normal one — the module under test does not
     exist, so a top-level import is a collection error rather than a failing test. The prompt
     therefore teaches the technique (import inside the test function), and the live session
     used it. Hardening a model cannot comply with is a park with extra steps.
  2. *The guard is the cheap block; the digest is the teeth.* A `PreToolUse` guard reads path
     arguments, so it cannot see a shell redirect or filter a repo-wide `Grep`. `tests.json`
     stores a SHA-256 per test file and the implement stage re-hashes before it may stand
     (`reason="tests-modified"`), which catches every route rather than the predicted ones.
  3. *The tests stage must not run the test gate.* It is judged on red; a gate demanding green
     would fail every tests stage that worked. Lint and typecheck still run on the new files.
- **T5.3 done — the pipeline is four stages and the loop closes.** `src/flux/diff.py` (a unified
  diff parsed into files and hunks, addressable by `file:line`), `git.ticket_diff` (the ticket's
  own change, bounded by its stage tags, ending at the *working tree* so uncommitted work is not
  silently omitted), `src/flux/stages/review.py` (`ReviewStage`, `review.json`, findings deduped
  and numbered by the runner) and `src/flux/stages/fix.py` (`FixStage`, whose pack is unresolved
  findings plus only the hunks they point at). A `[review]` block in `flux.toml` holds
  `fix_severities` — the only part of a review the machine acts on. 578 tests.
  **Live run verified** on a scratch repo: tests → implement → review → completed; then a planted
  defect (`if not sort:` where the ticket said any unrecognised value must raise) was caught by
  the reviewer as a `correctness` blocker at the exact line, resolved by the fix stage, and the
  loop turned three times before parking at `review-loop-exhausted`. 12 sessions, 210k uncached
  in / 85k out over 21.5 minutes.
- **The three things a future session should not re-derive about T5.3.**
  1. *The reviewer is read-only by guard, not by `plan` mode — design.md is amended.* The SDK
     documents `plan` as "Planning mode, no execution of tools", which also stops the reviewer
     writing `review.json`, so every review pass would have parked on a missing artifact.
     `review_stage_guard` confines writes to the ticket's context directory instead: strictly
     more of the repo forbidden than plan mode, and provable in pytest rather than being a
     property of the CLI. `[stages.review] permission_mode` is now `acceptEdits` by default.
  2. *Blindfolding the reviewer is about the fix stage, not the reviewer.* `review.json` is read
     by the stage that edits code, so a reviewer that could quote an assertion would hand back
     through a finding exactly what the opaque gate withholds. Hence both `source_stage_guard`
     (unchanged, shared with implement) *and* `diff_exclusions`, since the tests stage commits its
     work and the ticket's own diff carries the test source until it is excluded. What the
     reviewer gets instead is the `cases` map from `tests.json` — acceptance criteria, which state
     the requirement without any test source in them.
  3. *Widening `fix_severities` past `blocker` does not converge, and this was measured.* With
     `["blocker", "major", "minor"]` set on the live repo, the loop ran three full fix↔review
     passes and parked: the reviewer kept raising housekeeping findings the fixer could not close.
     The default stays `["blocker"]`, and the docstring's warning is now an observation.
- **T5.4 done — the pipeline is five stages and a ticket lands.** `src/flux/stages/pr.py`
  (`PrStage`, `pr.md`, `parse_artifact`, the runner-written provenance footer), a `[pr]` config
  block, `pr_stage_guard` (and `handoff_only_guard`, now shared with the reviewer), and five new
  `git` helpers — `current_branch`, `remotes`, `default_branch`, `remote_sha`, `push_head`,
  `ticket_log`. 617 tests.
  **Live run verified** on a scratch repo with a bare remote: tests → implement → review → pr,
  four sessions, no retries, 108k uncached in / 20k out over 4.5 minutes (~$1.29 secondary).
  The local checkout stayed on `main`; the remote holds only `flux/wc-1`, at exactly the local
  HEAD. Haiku/low wrote a genuinely usable body.
- **The three things a future session should not re-derive about T5.4.**
  1. *The session writes prose; the runner does every fact.* No Bash is granted, and that is
     load-bearing rather than an economy — a session that could run `git push` would make "the
     runner verified the push" a statement about which process ran a command instead of a
     property of the design. `push_head` re-reads the ref from the remote and compares it with
     the local sha, because a zero exit from `git push` is the subprocess equivalent of a
     transcript claim.
  2. *"CI triggered" was dropped from the contract, not quietly skipped.* design.md's table
     asked `commit()` to verify it. Whether a push starts a pipeline is the forge's business and
     flux cannot observe it without polling a provider it does not know about, so the stage says
     what it measured — the branch exists at this sha, this suite was green on it — and nothing
     else. The table is amended.
  3. *HEAD is pushed by refspec, so a protected branch costs nothing.* `HEAD:refs/heads/<target>`
     needs no checkout and no branch creation, so work done on `main` goes to `flux/<ticket>`
     rather than parking a ticket whose every other stage succeeded. A missing *remote*, by
     contrast, does park (ADR 0005: a check that cannot run has failed) — `[pr] push = false` is
     how a repo says it lands nowhere.
- **The T5.3 junk-commit decision, made and implemented:** `git.JUNK_GLOBS` (`__pycache__`,
  `*.pyc`, `.DS_Store`, `.venv`, `node_modules`, the cache dirs) is excluded from what
  `stage_commit` stages *and* from what `ticket_diff` calls the change. Excluding at staging
  rather than cleaning the tree means flux never has to decide how to unstage; applying it to
  staging only means a repo that already tracks such a file keeps tracking it, which is the same
  rule `flux init` follows for `.flux/.gitignore` — what a repo commits is that repo's decision.
- **A new observation from the T5.4 live run, recorded not fixed:** on the *first* ticket in a
  repo where `.flux/` was untracked, the tests stage's `git add -A` sweeps the whole scaffold
  into that ticket's diff, and the pr body then lists ".flux project scaffolding" among the
  changes. Not junk — `flux.toml` genuinely belongs in the repo (ADR 0006) — but it belongs
  there by the operator's commit, not inside ticket 1. First-run-only, cosmetic, and the obvious
  fix (excluding `.flux/**` from stage commits) would stop the handoff artifacts being committed,
  which the design wants. Left alone deliberately; revisit if worktrees (M5) change the shape.
- **A real flux behaviour the live review surfaced, recorded not fixed:** `stage_commit` does
  `git add -A`, so in a target repo with no `.gitignore` it commits `__pycache__/*.pyc`. Those
  files then sit in the ticket's diff forever, the reviewer correctly reports them, and *no fix
  can remove them from the diff* — which is how the widened-severity loop above failed to
  converge. Out of T5.3's scope; worth deciding at T5.4 (the pr stage is the natural place to
  care what the branch contains).
- **A latent bug the tests stage surfaced, now fixed:** the gate summariser only recognised
  pytest's totals line in its `=== decorated ===` form, but `-q` — which is in flux's own default
  gate command — prints it bare. Every `pytest -q` gate detail flux has ever recorded is missing
  its counts. The parser now reads the line from the bottom up and strips decoration.
- **A real bug fell out of the first live run:** with `--worktree` pointing somewhere other than
  `--root`, the implement session was told to write `impl-notes.md` to a path outside its reach,
  so it wrote the same relative path *inside the worktree* and the ticket parked after two paid
  attempts. `ExecConfig.add_dirs` now grants the ticket's context directory; design.md §1 has the
  general lesson (a session denied access to what it was told to do does the nearest thing it
  can reach, and reports success).
- **This repo now dogfoods its own config** — `.flux/flux.toml` is committed, written by
  `flux init`, and its gate suite is the same three commands CLAUDE.md names.
- **T4b done — M0 is complete.** Repo map resolved to **`repowiki map`** (bake-off memo at
  `repo-map-memo.md`, ADR 0009 annotated). `src/flux/knowledge/` caches it to
  `.flux/cache/repo-map.json`, records the git HEAD it was generated at, and slices it into the
  implement pack; `flux index` regenerates it in **0.2s** with no LLM call, and
  `--install-hook` writes an opt-in `post-merge` hook. 397 tests.
- **T4c done — gitnexus refused, `repowiki map` stays.** Measured, not argued: three tickets x
  three pack variants (`none` / `repowiki` / `gitnexus`) on a real 88-file clone of flux, nine
  live runs, all gates green. gitnexus was **worse** on the KPI (23 exploratory calls vs 19) for
  more wall time and output tokens. Memo: `gitnexus-memo.md`, raw data:
  `gitnexus-memo-data.jsonl`, ADR 0009 annotated. `flux/knowledge/` is unchanged.
- **The bigger finding, now open for M1:** carrying **no** repo map was competitive with both —
  lowest total wall time, tied on turns, and it won one ticket outright. Between-ticket variance
  exceeded any between-variant difference at n=1/cell, so nothing is proven either way. Whether
  the `[repo_map]` pack section earns its place at all is the first concrete question for T5's
  A/B harness.
- **Known limit of that result, accepted: flux is too small a repo to judge a symbol graph on.**
  The no-map control spent only 4–9 exploratory calls, so there was a floor effect — a large
  saving cannot be demonstrated against a baseline of 4. T4c stands as "refuse the swap on
  current evidence", not as "symbol maps do not help". **T5b** re-runs it on a 3–7x larger repo
  with repeats and a fourth arm (CodeGraph). Do not treat T4c as having closed the knowledge-
  source question — it closed only the gitnexus-supersedes-repowiki question.
- **Settled for T5 by T4c:** the review stage hydrates from the `git diff` of the stage commits
  (design.md's stage I/O table is unchanged). `detect-changes` may only *append* a flow overlay
  alongside the diff — its symbol attribution slips on short symbols and it has no JSON output.
- **Available opt-in, not adopted by default:** `gitnexus check --cycles --json -r .` as a
  `[[gates]]` entry, validated through flux's own gate machinery. Not in `flux init` defaults —
  it answers about the *indexed* commit and flux does not manage a gitnexus index.

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
- [x] **T4 — M0 step 3: gates + first end-to-end ticket.**
  Done except the repo map, which is split out as T4b below (it needs a tool installed and a
  bake-off, and nothing else in M0 depends on it).
  **Benchmark met:** a hand-written ticket flowed through one implement stage + gates end to end
  in a scratch target repo; `flux metrics` printed per-stage cost/time.
- [x] **T4b — M0 step 3b: repo map.** `repowiki map` adopted; `flux index` regenerates in 0.2s,
  the slice reaches the implement pack, staleness is labelled. **M0 exit benchmark fully met.**
- [x] **T4c — reconsider the knowledge source: gitnexus vs `repowiki map`.**
  **Refused, on measurement.** Nine live runs (3 tickets x `none`/`repowiki`/`gitnexus` pack
  variants) on a real 88-file clone of flux: gitnexus scored 23 exploratory calls to repowiki's
  19, for more wall time and output tokens, so the claim it was raised on is unsupported.
  Memo `gitnexus-memo.md`, raw data `gitnexus-memo-data.jsonl`, ADR 0009 annotated.
  All four sub-decisions are settled there:
  1. symbol map vs file list — **no detectable difference**; `flux/knowledge/` not repointed;
  2. `check --cycles` gate — **validated, opt-in**, not in `flux init` defaults;
  3. review hydration — **`git diff` stays ground truth**; `detect-changes` may only overlay;
  4. CLI vs MCP — **pinned CLI**; the session's own MCP server is version-broken against the
     index format and returns empty results with exit 0.

- [ ] **T5 — M1: full five-stage pipeline + hardening + A/B baseline.** Expanded into T5.1–T5.8
  below (T5.5 cut, T5.5a/T5.7/T5.8 added 2026-08-19 per ADR 0011; specs in plan.md §5 M1 and
  the design.md stage I/O table). Do the subtasks in order.
  Carried into T5 from T4: the `PreToolUse` test-edit block (it needs a tests stage to protect,
  so it lands in T5.2), and the review stage must use a **different model** from implement
  (`flux.toml` already routes it to Opus with `permission_mode = "plan"`).

  **Phase-gate question, answered in writing before opening M1** (plan.md §5, ADR 0008):
  *"did the harness beat vanilla Claude Code on the last A/B samples, and which planned feature
  does the data say to cut?"*
  **Answer: there are no A/B samples, so the harness has not been shown to beat anything.**
  `variant` has been a metrics field since T2, but nothing has ever written a `vanilla` line —
  `flux run --vanilla` did not exist. Every number in the store to date is harness-vs-harness.
  This is not a neutral gap: it is the one comparison ADR 0008 exists to force, and M0 shipped
  without it. It is therefore T5.1, before any new stage is built.
  **Which feature does the data say to cut:** on the only comparative evidence that does exist
  (T4c, nine live runs), the candidate is **`[repo_map]`** — the `none` arm was competitive with
  both map variants on the exploratory-call KPI and had the lowest wall time. That is not yet a
  verdict (n=1/cell, floor effect on an 88-file repo); T5.1 gives it a harness and T5b gives it
  a fair repo. Nothing else in the plan has data either way, which is the finding.

  - [x] **T5.1 — A/B baseline harness (A1). Done 2026-08-18.** `flux run <ticket> --vanilla`: the same ticket
    through a plain session with *only* the ticket text — no pack, no repo map, no artifact
    contract — then the same gate suite, recorded as `variant="vanilla"` on the same metrics
    line shape. Plus the reading side: paired per-ticket comparison, the `vanilla_every` cadence
    ("a baseline sample is due"), and a machine-checked kill-criterion in `flux metrics`.
    Fairness rules that make the number mean something: same model/effort as `implement`
    (so the comparison isolates the harness, not the model), the same gate-command
    pre-approval (T4 proved a session that cannot run the gates argues instead of measuring),
    and a hard refusal to run vanilla in a worktree where the harness already did the work.
    **Done:** all four. One live vanilla sample and one live harness sample on the same ticket,
    sharing one metrics store via `--worktree`; the paired table, cadence and criterion print;
    35 new unit tests, none of which touch a model.
  - [x] **T5.2 — tests stage + the hardening that only it can carry. Done 2026-08-18.**
    `TestsStage` per the stage I/O table (`tests.json`: paths + cases↔acceptance-criteria map),
    the **runner-verified red step** (Rule 2 — flux runs the new tests itself and requires
    red-for-the-right-reason, not a green suite and not a collection error), the **opaque test
    runner** (counts, failing ids, first assertion line — never test source), the `PreToolUse`
    **test-edit block** on the implement stage, and held-out tests run at implement time.
    **Done:** all five, plus the digest backstop that makes the block hold against routes a hook
    cannot see. Details in design.md §2 "as built (T5.2)"; the mechanics worth remembering are in
    Current state above. **Carried to T5.3:** the fix stage reuses `source_stage_guard` unchanged
    — it is built to be shared, and re-deriving a second policy there would be the bug.
  - [x] **T5.3 — review + fix stages: close the loop with real stages. Done 2026-08-18.**
    `ReviewStage`
    (different model, `plan` mode, hydrates from the `git diff` of the stage commits per T4c,
    produces `review.json`) and `FixStage` (unresolved-finding slices + the diff hunks they
    point at, never the whole of anything). T3's transition function already turns the loop and
    parks at `max_review_iters`; this is the first time real stages drive it.
    Assert the reference-not-paste invariant here: pack size must not grow monotonically.
  - [x] **T5.4 — pr stage. Done 2026-08-19.** Haiku/low, `pr.md` (title + Summary/Changes/
    Review/Risk) from impl-notes + resolved review + commit log; the runner runs the gates on
    the tree it is about to push, pushes `HEAD` by refspec, and re-reads the ref out of the
    remote to confirm the sha. **"CI triggered" is deliberately not claimed** — see design.md
    §2 "as built (T5.4)". Also carries the T5.3 junk-commit decision: `git.JUNK_GLOBS`.
  - [x] **T5.5 — review bake-off (B3). CUT 2026-08-19 (ADR 0011), not done.** A bake-off
    between two review configurations is premature while nothing shows the review stage earns
    its place at all — T5.6's table is what answers that. Revisit only if the review loop
    survives the benchmark and its cost is the complaint.
  - [ ] **T5.5a — fix the A/B quality axis (ADR 0011). Do this before T5.6; every benchmark
    number routes through it.** Quality must be judged by the same per-ticket **held-out
    acceptance tests on both arms**, written before either arm runs and stored outside both
    worktrees. The held-out machinery from T5.2 is the mechanism; what is new is running it
    against the vanilla arm's tree in `flux/ab.py` and folding an "acceptance green" level into
    `metrics/ab.py`'s ordinal, above "gates green". Also amend the `Arm.quality` and
    `PromptPack` docstrings (design.md §2/§3 already carry the corrections). Done when: a
    do-nothing vanilla run loses its pairing in a unit test, and one live pairing records
    acceptance verdicts for both arms.
  - [ ] **T5.6 — M1 exit benchmark (expanded, ADR 0011).** (a) one real ticket runs to a
    mergeable PR unattended; (b) a deliberately gameable ticket (one a session could pass by
    weakening a test) is caught; (c) **5–10 paired real tickets** vs vanilla on a real repo
    (candidates: clones of `~/Dev/zaps/kiosk` or `~/Dev/zaps/api`, already named in T5b), on
    the model actually used for real work, quality judged per T5.5a. Then re-answer the
    phase-gate question from the table — including whether `[repo_map]`, the tests stage, and
    the review loop each survive, and which pipeline shapes T5.7 should offer as defaults.
  - [ ] **T5.7 — per-ticket pipeline configuration (ADR 0011).** The stage list becomes ticket
    data with the current five as the default: `stages = ["implement", "pr"]` for a small
    change, the full five where the ticket is risky or gameable. `Pipeline` already takes a
    stage list; what is new is a per-ticket override (ticket front-matter or a `[tickets]`
    table in flux.toml), validation of the list (review requires tests to have run, fix
    requires review, pr last), and the transition function honouring the shorter list. Done
    when: a trivial ticket lands on a two-stage pipeline at a measured cost below its
    five-stage run.
  - [ ] **T5.8 — smart-zone continuation (ADR 0011; goal 3 in minimal form).** A stage that
    hits `max_tokens` checkpoints progress into its artifact and continues in a **fresh
    session hydrated from disk**, rather than parking. Mechanism sketch: the budget hard-stop
    in `runner/loop.py` (`_hard_stop`) becomes "record the partial attempt, re-hydrate with
    the artifact so far, continue once; park only on a second breach". The artifact/hydration/
    checkpoint machinery already exists — this is the runner using it mid-stage instead of
    only between stages. Done when: a ticket that previously parked on `token-budget-exceeded`
    completes via one continuation, and the metrics lines show both sessions attributed to the
    same stage.

- [ ] **T5b — knowledge-layer A/B on a *large* repo, four arms. Do this after T5, not before.**
  **Why it exists:** T4c's refusal of gitnexus was measured on flux itself (88 files), and the
  user's challenge that this is too small to judge a symbol graph is **correct and accepted**.
  The no-map control spent only 4–9 exploratory calls, so there was a **floor effect** — you
  cannot show a large saving against a baseline of 4. T4c's result is therefore sound as
  "refuse the swap on current evidence" and weak as "symbol maps do not help".
  Two further confounds, both cutting the same way: the three tickets were written immediately
  after reading the repo and named their targets almost precisely enough to grep, and flux has
  clean descriptive module naming (`knowledge/repomap.py`, `runner/loop.py`) which makes grep
  unusually effective. The adversarial case — vague ticket, large repo, historical naming — was
  never tested.
  **Blocked on T5** because the A/B harness is a T5 deliverable; do not hand-roll a second one.
  **Setup when it runs:**
  - Target: a clone of a real, larger repo. Two are already to hand and already indexed —
    `~/Dev/zaps/kiosk` (662 files, 2,555 symbols) and `~/Dev/zaps/api` (296 files, 2,945
    symbols), i.e. 3–7x flux. Clone, never run stages against the working copies.
  - Four arms: `none` / `repowiki` / `gitnexus` / **`codegraph`**. Keep the `none` control —
    it was the most informative arm in T4c and the one T4b never ran.
  - Tickets written by someone who has *not* just read the repo, and deliberately vaguer than
    T4c's, so the pack has something to do. Replace the degenerate `gate-timing`-style ticket
    (it asked for `GateOutcome.duration_ms`, which already existed).
  - Repeats: n>=3 per cell. T4c ran n=1 and the between-ticket variance swamped the
    between-variant difference — that is the main thing to fix.
  - KPI stays `exploratory_calls`; also record turns, wall, output tokens, and pack_chars.
  - Method reference: `gitnexus-memo.md` §1 describes T4c's setup precisely enough to rebuild.
  **Fourth arm — CodeGraph (`colbymchenry/codegraph`), researched 2026-08-18, not yet spiked.**
  On docs only (via ctx7, *not* verified hands-on), it fixes every operational objection T4c
  raised against gitnexus:
  | T4c objection to gitnexus | CodeGraph per docs |
  |---|---|
  | `analyze` not incremental (7.4s for a one-line change) | `codegraph sync` — changed files only |
  | `detect-changes` has no `--json` | `query` and `impact` take `--json`, with filePath/startLine |
  | machine-global registry, `-r <alias>`, identity collisions | `-p, --path <path>` per invocation |
  | MCP build drifts from index format, fails silently | CLI-first; MCP is an explicit `serve --mcp` |
  Also local-first, no API keys (clears ADR 0010), Rust kernel, 20+ languages, and
  `install --print-config` prints rather than writing files — versus gitnexus rewriting
  `CLAUDE.md` by default.
  **Treat its headline claim as the hypothesis under test, not as evidence.** CodeGraph
  advertises "94% fewer tool calls, 77% faster exploration" — a vendor number about *exactly*
  the metric T4c measured as null. This is the third tool in a row proposed on a claim rather
  than a measurement (T4b adopted `repowiki map` on a research claim about Aider's symbol-level
  maps and shipped the ranking half; T4c raised gitnexus on a hands-on impression that did not
  survive measurement). The harness exists precisely so this one gets tested instead.
  Note the name is ambiguous — at least five projects call themselves CodeGraph; the one meant
  is `colbymchenry/codegraph`, the Claude-Code-targeted one with darwin-arm64 bundles.
  **Done when:** the four arms are measured with repeats on a large repo and the memo is amended
  with the outcome — including, explicitly, whether `[repo_map]` earns its place at all. A
  result that kills the repo-map section entirely is a legitimate and welcome outcome.


- [x] **Housekeeping — `.flux/state/` tried tracked, then reverted (2026-08-18).** For the
  record, because the reasoning is worth keeping: tracking a ticket's checkpoints was tried on
  the argument that flux's own repo is also the project record. It was reverted once the
  consequence was clear — flux addresses `state/`, `context/` and `usage/` under **`--root`**
  and never under the worktree, so committing state does not give a worktree anything (the
  `add_dirs` fix is what made `--worktree` work). It only creates a hazard: a clone or
  `git worktree` used as its *own* root arrives carrying committed checkpoints and skips stages
  it thinks are done. `.flux/.gitignore` is back to the `flux init` default, and
  `scaffold.IGNORED_DIRS` never changed.
  **What survives from the attempt, and is worth having:** `flux init` no longer rewrites an
  existing `.flux/.gitignore` — not even under `--force`, which is scoped to `flux.toml`. What a
  repo tracks is that repo's decision, and restoring the default over it would revert that
  decision with no trace (the same rule `flux index --install-hook` follows for a live hook).
  Init warns instead, naming the ignored-by-default directories the repo tracks, and the check
  reads patterns rather than the whole file so a comment explaining a choice is not mistaken for
  the choice.

- [x] **Housekeeping — `.claude/` resolved (2026-08-18).** The six `gitnexus setup` skill files
  under `.claude/skills/gitnexus/` are deleted and `.claude/` is gitignored;
  `settings.local.json` (the accumulated permission allowlist) is kept on disk, untracked.
  **Still live and outside this repo:** `gitnexus setup` also wrote hooks into
  `~/.claude/settings.json` pointing at `~/.claude/hooks/gitnexus/gitnexus-hook.cjs` — a
  `PreToolUse` on `Grep|Glob|Bash` ("Enriching with GitNexus graph context...") and a
  `PostToolUse` on `Bash` that prints the stale-index nag. They affect *your* sessions, not
  flux's stage sessions. **Do not follow that nag as written:** `gitnexus analyze` without
  `--skip-agents-md` rewrites `CLAUDE.md`, the session bootstrap.
  **Checked, and it matters for T5b:** those hooks cannot contaminate flux's own measurements —
  `ExecConfig.setting_sources` defaults to `("project",)`, so user-level settings never reach a
  stage session, and the T4c experiment clone had no `.claude/` at all. Any future A/B run must
  preserve that property, or exploratory-call counts become meaningless.

## Session-close checklist (execute before ending any working session)

1. Gates green (`uv run ruff check . && uv run pyright && uv run pytest`) — once T2 exists.
2. Commit with a descriptive message.
3. Update this file: current state, check off / re-scope queue items, add a log entry with any
   surprises, deviations from design.md, or decisions made (new ADR if load-bearing).

## Log

- 2026-08-19 — **Direction review: benchmark before machinery (ADR 0011).** A full review of
  the repo and code against the six goals flux exists for, requested by the user with "I'm
  ready to rip everything apart and start over if it's not going to benefit me". Verdict: keep
  the substrate (~3k lines serving goals 1–2 precisely), re-sequence everything else; nothing
  ripped apart. What changed and why:
  - **T5.5 cut.** A bake-off between two review configurations optimizes a stage whose
    existence has no supporting data. The benchmark decides whether the review loop lives.
  - **The A/B quality axis is the most important bug in the repo, and it blocks everything.**
    "Gates green" over the repo suite cannot distinguish "implemented the feature" from
    "changed nothing", so the kill-criterion can fire falsely in either direction. T5.5a fixes
    it (acceptance tests judge both arms) before any benchmark number is trusted.
  - **The cross-stage cache claim is amended, not yet measured.** The per-stage system prompt
    precedes user content and breaks the cache; stages run on different models. design.md §2
    carries the correction; the `types.py` docstring catches up at T5.5a.
  - **M2/M3 frozen.** Claude Code's native plan mode and subagents cover much of M3; M2 opens
    only if benchmark data names cold exploration as the constraint. plan.md §5 re-sequenced:
    M1 (amended) → M1b (new: pipeline routing + continuation) → M4 → M5.
  - **New tasks T5.7 and T5.8** move goals 3–4 (routing, smart-zone chunking) ahead of the
    knowledge layer. The likely end-state the benchmark points at: gates + checkpoints +
    metrics + a configurable 1–5 stage pipeline with per-ticket routing.
  - Docs-only session: ADR 0011 added; plan.md, design.md, status.md, CLAUDE.md amended. No
    code changed — T5.5a is where the code catches up with the docs.

- 2026-08-19 — **T5.4 done: the pr stage, and the first ticket flux landed.** The pipeline is
  five stages; a live ticket ran unattended from an empty module to a branch on a remote, and
  the branch was confirmed by reading the ref back rather than by anything claiming it. What is
  worth carrying forward:
  - **The interesting decision was where to draw the session/runner line, and it moved further
    than the design implied.** design.md gives the pr stage "PR body + pushed branch" as its
    output, which reads as though the session does both. It does not: the session has no Bash at
    all. Everything outward-facing — the last gate run, the push, the `gh` invocation — is the
    runner's, so every claim in the checkpoint is something flux observed. Granting the session a
    shell would have been the natural implementation and would have quietly converted "verified"
    back into "reported".
  - **A contract in design.md turned out to be unverifiable, and was dropped rather than faked.**
    The table asked `commit()` to verify "CI triggered". flux cannot see that without polling a
    forge it knows nothing about, and a stage that recorded `ci_triggered: true` because a push
    succeeded would be manufacturing exactly the kind of evidence the pipeline exists to
    distrust. The table is amended and the docstring says why.
  - **Restraint is the pr stage's whole design, because a push is the one thing `git reset`
    cannot undo.** Never a protected branch, never `--force`, drafts by default, and a missing
    remote parks rather than reporting a completed ticket that went nowhere. The protected-branch
    rule is only cheap because HEAD is pushed by refspec (`HEAD:refs/heads/<target>`): the local
    checkout never moves, so redirecting `main` to `flux/<ticket>` costs nothing and needs no
    branch to have been created first.
  - **T5.3's junk-commit problem is closed by exclusion at staging, not by cleaning.** A file
    flux never stages is a file flux never has to decide how to unstage. It applies to staging
    only, so a repo already tracking one of those files keeps tracking it — the same principle
    `flux init` follows for an existing `.flux/.gitignore`.
  - **The live run cost four sessions, no retries, 4.5 minutes.** Haiku at low effort produced a
    body a human would actually merge from, including an accurate Risk section about the
    machine-specific gate path in the scratch config — a finding about the *test setup*, arrived
    at from the review it was handed.

- 2026-08-18 — **T5.3 done: the review and fix stages, and the first loop that turns on real
  stages.** Four deliverables — a diff layer, a reviewer, a fixer, and the `[review]` policy that
  connects them — plus a live run that ended in exactly the park it should have. What is worth
  carrying forward, beyond the code:
  - **The design's `plan` mode for the reviewer could not have worked, and finding that cost
    nothing because the SDK says so in one line.** `permission_mode="plan"` is documented as
    "Planning mode, no execution of tools" — which includes writing `review.json`, the artifact
    the stage is judged on. A plan-mode reviewer parks every single time. The replacement is
    better rather than merely workable: `review_stage_guard` is allow-only on the ticket's
    context directory, so the reviewer may write its findings and *nothing else in the repo* —
    strictly more forbidden than plan mode, and a pytest assertion instead of a property of the
    CLI. design.md's stage I/O table is amended rather than quietly contradicted.
  - **The reviewer is blindfolded to the tests for the fix stage's sake, not its own.** This was
    the substantive design call. `review.json` is read by a stage that edits code, so a reviewer
    free to quote an assertion hands back through a finding precisely what the opaque test gate
    withholds — the whole T5.2 mechanism, defeated by a well-meaning code excerpt. So both the
    guard (it cannot reach a test) and `diff_exclusions` (a test cannot reach it): the tests stage
    *commits* its work, so the ticket's own `git diff` carries the test source until it is taken
    out. In exchange the reviewer gets the `cases` map from `tests.json` — the acceptance criteria,
    which are a statement of requirements with no test source in them.
  - **Using the pack found a leak the design did not predict.** The first review pack quoted
    `impl-notes.md`. flux's handoff artifacts live under `.flux/context/<ticket>/` and are
    committed beside the code, so `git diff` hands the reviewer flux's own plumbing as if it were
    work under review — including the artifacts the stage I/O table deliberately withholds from
    it. The exclusion is the *ticket's* context directory rather than all of `.flux/`, so a ticket
    that genuinely edits an ADR is still reviewable. Assertions about what a pack does not contain
    are worth writing: two of them caught this.
  - **`fix_severities` widened past `blocker` does not converge — measured, not predicted.** With
    `["blocker", "major", "minor"]` on the live scratch repo, the loop ran three full fix↔review
    passes and parked at `review-loop-exhausted`. The reviewer was not wrong on any pass; it kept
    finding housekeeping the fixer could not close. The default stays `["blocker"]` and the
    docstring's warning is now an observation, which is the version worth having.
  - **The live run's headline: a planted defect caught at the exact line, and fixed.** The ticket
    said any unrecognised `sort=` value must raise; the code was quietly changed to `if not sort:`,
    which silently accepts `""` and `0`. The tests did not cover it and the gates were green. The
    reviewer raised it as `correctness` at `report.py:11`, described the failing input, and the
    fix stage restored `if sort is None:`. That is the case ADR 0005 puts the reviewer there for —
    the defect a machine cannot see — and it is the first time flux has caught one.
  - **The loop's bound is only meaningful because both halves are bounded.** Two stages now raise
    `ParkSignal` from `hydrate()` — review on an empty diff, fix with no unresolved findings —
    which parks having spent nothing, because `_run_stage` calls `hydrate` inside the runner's
    park handler. Both conditions mean a session could only have discovered, expensively, that
    there was no work.
  - **The fix stage is the implement stage's twin, asserted rather than described.** Same guard
    object, same gate suite, same digest backstop, same granted directory, compared field by field
    in `test_fix_stage.py`. Anywhere those two diverge is somewhere a session that could not game
    the first stage could game the second — and this is the second place a session is told "make
    the gate go green".
  - **One flux behaviour recorded and deliberately not fixed:** `stage_commit` runs `git add -A`,
    so a target repo without a `.gitignore` gets its `__pycache__/*.pyc` committed, after which
    those files are in the ticket's diff permanently and no fix stage can remove them. That is how
    the widened-severity loop above failed to converge. It belongs to T5.4, where the pr stage has
    to decide what a flux branch may contain.

- 2026-08-18 — **T5.2 done: the tests stage, and the first hardening that is structural rather
  than requested.** Five deliverables, all live-verified on a scratch repo in one run.
  What is worth carrying forward, beyond the code:
  - **The red-step rule had to be made satisfiable before it could be enforced.** "Fail for the
    right reason" excludes collection errors, but the ordinary TDD case — the module does not
    exist yet — *is* a collection error if the test imports at module scope. So the tests stage's
    system prompt names the technique (import inside the test function). The live session
    followed it and produced a clean collection with two assertion-time failures. The general
    lesson is the T5.1 lesson in another costume: a rule the session cannot comply with does not
    produce compliance, it produces a park.
  - **A `PreToolUse` guard cannot be the whole of a test-edit block, and pretending otherwise
    would have been the defect.** It reads path arguments, so `sed -i` and repo-wide `Grep` go
    straight past it. `tests.json` therefore carries a SHA-256 per test file and the implement
    stage re-hashes them before it is allowed to stand. Guard for the cheap early block with a
    reason the model can act on; digest for the guarantee. Evidence beats prediction — the same
    argument that put the gates in ADR 0005 in the first place.
  - **The guard model is flux data, not SDK types.** `PathGuard` + a pure `decide()` in
    `flux/executor/guard.py`; `sdk.py` is the only thing that knows what a `HookMatcher` is. That
    keeps ADR 0007's seam intact and makes the whole of the hardening testable without a session
    — which is why `tests/test_guards.py` can assert the policy directly.
  - **`ArtifactSpec` grew a `check` callable.** "The key is present" is a weak reading of "valid"
    for an artifact that is a map: `cases: []` satisfies `required_keys` and tells the next stage
    nothing. Checking structure at validation time makes it cost one nudged retry instead of a
    park. `review.json` at T5.3 should use the same field rather than validating inside
    `commit()`.
  - **A latent parser bug, found by using the parser for a second purpose.** The pytest
    summariser only matched the `=== decorated ===` totals line; `-q`, which is in flux's own
    default gate command, prints it bare. Every `pytest -q` gate detail recorded to date is
    missing its counts. Fixed by reading bottom-up and stripping decoration — and the gate
    summariser and the red step now share one parser, so the next divergence is impossible
    rather than merely unlikely.
  - **Two housekeeping decisions.** `test_m0_end_to_end.py` now pins its own implement-only
    `Pipeline` instead of calling `build_pipeline`: it is the record of the M0 benchmark, and M0's
    pipeline was one stage. And pytest's `python_classes`/`python_functions` are narrowed in
    `pyproject.toml`, because flux now has production types called `TestReport`/`TestsStage` and
    helpers called `tests_*` that a test module importing them would otherwise collect.

- 2026-08-18 — **T5 opened and expanded into T5.1–T5.6; T5.1 done.** The phase-gate question was
  answered first, in the queue entry above, and the answer was **no data**: `variant` has been a
  metrics field since T2 but nothing had ever written a `vanilla` line, so every number in the
  store was harness-vs-harness. That is now fixed, and the first thing the fix produced was a
  result against the harness.
  - **The first paired sample: harness 1.41x vanilla on tokens, both green.** A trivial ticket
    ("add a `sort=` keyword to `report()`, with tests") in a scratch `tinylib` repo, one arm per
    clone, one shared metrics store. Vanilla: 6,757 uncached in / 3,029 out, 14 turns, 38.4s, 3
    exploratory calls. Harness: 10,962 / 2,832, 9 turns, 31.9s, 2 exploratory calls. Both passed
    the `pytest` gate. So the harness bought **fewer turns, less wall time and less exploration
    for more tokens** — which is a coherent story (a pack costs input tokens to save turns) and
    is worth exactly nothing at n=1 on a toy ticket. It is recorded because the whole point is
    that the number is recorded before anyone has an opinion about it.
  - **Defining "wins" was the substantive design work**, not the plumbing. The criterion's prose
    says "cost AND quality" and stops. Cost: uncached in + out over every line including retries;
    cache reads excluded (T4's 893k-token park is why). Quality: an ordinal over the gates *flux*
    ran — green > ungated > failed — taking the **latest** verdict per gate name, so the
    review↔fix loop is not scored as a defect for having done its job, and a failed-then-retried
    session is cost rather than a defect. Vanilla wins on **strictly cheaper and not worse**: the
    harness is the thing on trial, so a quality tie at a lower price is a loss for it.
  - **Fairness rules are in the code, not in the method notes.** Same model/effort as `implement`
    and *mirrored live* (`FluxConfig.profile`), so re-routing the stage re-routes the baseline —
    a copy taken at parse time would quietly turn the A/B into a model comparison. Same gate
    pre-approval, since T4 measured what an ungated headless session does instead of measuring.
    And a **hard refusal**, before any spend, to run a baseline in a worktree the harness already
    worked: that sample would read as "vanilla solved it in one cheap turn".
  - **The live run found a real bug, which is the argument for live runs.** With `--worktree`
    ≠ `--root` — the configuration the A/B needs so both arms share one metrics store — the
    implement session had no access to `.flux/context/<ticket>/`, so it wrote `impl-notes.md` at
    the same relative path *inside the worktree* and the ticket parked after two attempts and
    ~36k uncached tokens. Fixed with `ExecConfig.add_dirs`; every stage with a required artifact
    now grants its context directory. The general lesson is in design.md §1: **a session denied
    access to what it was told to do does the nearest thing it can reach, and reports success.**
    It had never shown up because T4's live runs had worktree == root.
  - **`PromptPack.system_prompt=""` now means "the CLI's own default"** rather than an empty
    system prompt. The baseline arm needs the real default preset — a blank one would be a
    handicap invented by the harness — and no stage passes an empty system prompt.
  - **`flux metrics` prints the A/B block even when it is empty** ("no paired samples yet"), and
    `flux run` says when a baseline is due. A cadence nobody is reminded of is a cadence that
    lapses, and silence at a phase gate reads as "nothing to report".
  - **Config surface:** `[ab] kill_streak` (the machine-readable half of the prose criterion, so
    the two are visibly adjacent), and *no* `[stages.vanilla]` in the generated `flux.toml` —
    with a comment saying the omission is the mirror, and that adding one breaks it deliberately.
  - Scratch evidence lives in the session scratchpad, not the repo: the contaminated first
    pairing (the one with the parked attempts) was kept aside as `metrics-with-bug.jsonl` and the
    clean pairing re-run from scratch. Neither is part of M1's ≥3 samples — those need real
    tickets on a real repo, which is T5.6.

- 2026-08-18 — **T4c's result challenged on repo size; challenge accepted, T5b queued.** The
  question raised was whether the null result is an artifact of flux being small, and whether
  gitnexus would do better on a bigger repo. It is a fair hit and the answer is yes, partly:
  the `none` control spent 4–9 exploratory calls, which is a **floor effect** — there is almost
  nothing to save. Two further confounds were conceded: the T4c tickets were written straight
  after reading the repo and named their targets nearly precisely enough to grep, and flux's
  module naming makes grep unusually effective. The adversarial case (vague ticket, large repo,
  historical naming) was never tested. **T4c's scope is therefore narrowed in the record:** it
  refuses the gitnexus-for-repowiki swap on current evidence; it does not establish that symbol
  maps are useless. `gitnexus-memo.md` §1 amended to say so up front rather than in a footnote.
- **CodeGraph raised as a better candidate; researched, not spiked.** On docs (ctx7, no hands-on
  verification) `colbymchenry/codegraph` fixes all four operational objections T4c raised —
  real incremental `sync`, `--json` on `query`/`impact`, `-p, --path` instead of a machine-global
  registry, CLI-first with MCP as an explicit opt-in — plus local-first with no API keys. It is a
  genuinely better engineering fit. **But it does not touch T4c's actual finding**, which was
  about whether a symbol-context section reduces exploration at all, not about ergonomics.
  Its "94% fewer tool calls" headline is a vendor number about exactly the metric measured as
  null, and this would be the **third** tool in a row adopted on a claim rather than a
  measurement. Queued as the fourth arm of T5b instead of adopted.
- **Standing rule this makes explicit:** knowledge-source candidates get measured through the
  A/B harness before adoption, never adopted on a README. T4b's mistake (adopting on a claim
  about Aider's symbol maps, shipping the ranking half) is the reference case.

- 2026-08-18 — **T4c done: gitnexus measured against `repowiki map` and refused.** The T4c
  raise was a good challenge answered honestly, and the answer went against it. Nine live
  implement-stage runs on a clone of flux at `38bb6d9` (88 files, 1,689 indexed symbols), three
  tickets x three pack variants, everything held constant but the knowledge section. Totals:
  `none` 18 exploratory calls / 87 turns / 483s, `repowiki` 19 / 87 / 696s, `gitnexus` 23 / 73 /
  716s. **gitnexus lost the KPI it was proposed on.** Memo: `gitnexus-memo.md`; raw data:
  `gitnexus-memo-data.jsonl`.
  - **The uncomfortable part is the control.** Carrying *no* map was competitive with both — it
    had the lowest wall time and won `gate-timing` outright. Direction disagreed per ticket
    (both maps beat `none` on `map-check`; `none` beat both on `gate-timing`; `repowiki` hit a
    near-perfect 1 on `park-detail` where `gitnexus` needed 8). Between-ticket variance exceeds
    any between-variant difference at n=1/cell, so the correct claim is "no effect detectable",
    **not** "the file list wins". That is enough to refuse a swap and not enough to conclude the
    pack section is worth its tokens — which is now T5's first A/B question.
  - **Why the good-looking pack section did not pay.** The gitnexus slice *reads* far better than
    a centrality ranking — for `map-check` it named `repomap.py`, `RepoMap`, `cli.py`,
    `build_parser`, `head_sha` and the two existing staleness tests, all with file:line — and it
    still did not reduce exploration. Worth remembering the next time a knowledge artifact is
    adopted because it looks informative rather than because it moved a number.
  - **`query` is only as good as the brief.** A two-word query ("gate") returned noise flows;
    a full-sentence ticket brief returned exactly the right symbols. Any future use must feed it
    the whole brief.
  - **Version drift is the real operational risk, and it bit twice.** `which gitnexus` was 1.6.1
    while latest was 1.6.9; `check` and `detect-changes` do not exist in 1.6.1 at all. Worse, the
    1.6.1 build cannot read the v42 index the 1.6.9 CLI writes: `context` raises, and **`query`
    returns an empty result set with exit 0**. The gitnexus MCP server attached to this very
    session is the broken one. That is the strongest argument for the pinned-CLI recommendation —
    stronger than the determinism argument it was originally made on.
  - **An empty index reports success.** Analyzing a clone whose identity collided with the
    already-registered `flux` entry produced `0 nodes | 0 edges`, exit 0, "indexed successfully".
    Sticky: `rm -rf .gitnexus`, `gitnexus remove`, `-f` and a fresh `--name` all still gave 0;
    only re-cloning recovered. Same failure class `knowledge/repomap.py` already guards against,
    and the reason that guard exists.
  - **Registry is machine-global** (`~/.gitnexus/registry.json`), resolved by alias, and `-r` is
    mandatory once more than one repo is indexed. `-r .` works and is what keeps a committed
    `[[gates]]` entry portable — `-r <alias>` would not be.
  - **The cycles gate is real** and was validated through flux's own `GateSpec`/`CommandGate`,
    not just at a shell: green on a clean repo, red with the cycle in `detail` on a two-module
    circular-import repo. Left **opt-in**: it answers about the *indexed* commit, and flux does
    not manage a gitnexus index, so wiring it into `flux init` would ship a gate that silently
    describes an older tree — the exact failure T4b built staleness labelling to prevent.
  - **`detect-changes` cannot be the reviewer's input.** A mid-body edit attributed perfectly
    (`generate` + three correct flows), but a 2-line insertion into the 4-line `is_stale` was
    attributed to the *next* method and `is_stale` never appeared. Plus there is no `--json`.
    So: diff stays ground truth, overlay is advisory. This settles the one T4c question T5 was
    blocked on.
  - **Cost, for the record:** `gitnexus analyze` 3.1–5.0s cold and 7.4s after a one-line change
    (not meaningfully incremental) against `repowiki map`'s 0.5s — ~15x on `flux index`.
  - **Method note / self-criticism:** `gate-timing` was a partly degenerate ticket —
    `GateOutcome.duration_ms` already existed, so it asked for work already done. All three
    variants faced it identically so the comparison holds, but it was not the test intended, and
    it should be replaced when this is re-run through T5's A/B harness.
  - `src/flux/knowledge/` was not touched. The seam's payoff here was making the swap question
    answerable by measurement rather than argument — the answer just happened to be "no".

- 2026-08-18 — **T4c raised: gitnexus looks like the right knowledge source, and T4b asked the
  wrong question.** Prompted by "does `repowiki map` actually save the agent tokens, or is it
  just running documentation?" — a fair challenge. The honest answer for the map as shipped is
  *neither*: it is a centrality ranking. It costs 58 tokens in the tinylib pack, and **no
  measurement exists that it saves any**; the successful live run's 3 exploratory calls predate
  it. On a 3-file repo it ranked `pyproject.toml` and `__init__.py` into the pack — noise. The
  research claim it was adopted on (`per-ticket-pipeline.md`, "a repo map beats letting the agent
  explore") is about Aider's **symbol-level** map; T4b carried it over to a tool that ships only
  the ranking half.
  **What was checked hands-on** (gitnexus 1.6.9, indexed on this repo — do not re-spike):
  - `analyze .` → **6.4s**, 1,689 nodes / 3,323 edges / 63 clusters / 119 flows, 46MB index.
    It adds `.gitnexus/` to `.git/info/exclude` itself, so it never dirties the tree.
  - **Python is exact**, not heuristic: `context run_ticket -r flux` returns
    `"epistemic": "exact"` with the true edges — `cmd_run` in, `_run_stage`/`next_stage`/
    `_apply_outcome`/`_park` out, all with file:line. This is the symbol map repowiki lacks.
  - **No API key** — `doctor` reports embeddings backend `local` (ONNX), and embeddings are off
    unless `--embeddings` is passed. Clears ADR 0010. Not strictly "zero LLM" if embeddings are
    enabled, but zero *billed* calls either way.
  - `check --cycles --json` → `{"status":"clean","cycleCount":0}`. A gate, as-is.
  - `detect-changes --scope compare --base-ref HEAD~1` on the T4b commit → 128 changed symbols,
    46 affected execution flows, risk level, and *which flow breaks at which step*
    ("Hydrate → Elapsed (6 steps) — changed: `_repo_map_section`, `hydrate`, `head_sha`").
    Strictly more informative than the raw `git diff` design.md currently hands the reviewer.
  - `impact <symbol> --direction upstream` → blast radius with risk + depth buckets. A real input
    to M4 ticket sizing (plan.md §6: "a ticket routinely needs >3 review iterations → tickets are
    too big").
  **Footguns found:** `analyze` **rewrites `CLAUDE.md`/`AGENTS.md` by default** — flux must always
  pass `--skip-agents-md`, since CLAUDE.md is the session bootstrap and load-bearing. FTS
  extension was unavailable in this environment ("continuing without FTS features"), so keyword
  search is degraded locally. Dependency surface is heavier than repowiki's `uvx` call: Node,
  a native `lbugjs.node`, ONNX runtime.
  **What survives regardless:** `src/flux/knowledge/` was built tool-agnostic — cache, git-HEAD
  staleness, slicing — and none of that changes if the ranker is replaced. That was the point of
  the seam, and this is the first evidence it was worth having.

- 2026-08-18 — **T4b done. M0 complete.** Repo-map bake-off run for real against flux (85 files)
  and the scratch target; memo at `repo-map-memo.md`, ADR 0009 annotated with the outcome.
  **`repowiki map` adopted.** What the bake-off actually found:
  - **RepoMapper is not adoptable.** Four blocking defects, and the last is fatal to its premise:
    PageRank runs *only* when `--chat-files` is supplied, so in flux's case (a map built before
    any file is chosen) the graph is built and discarded and **every file ranks 1.0**. Also: HEAD
    does not execute on any tree-sitter version (it raised the floor to ≥0.25 for `QueryCursor`
    while keeping `Language.query`, removed in 0.25); the CLI prints a Python tuple `repr`;
    `token_count(None)` raises inside the verbose path; and the tags cache memoises *failures*
    with no invalidation that `--force-refresh` can clear. Unmaintained since 2025-09-24 — the
    commit that broke it. Its Aider-derived symbol-level extraction is genuinely richer than a
    ranked file list, so **if flux later needs symbols, take them from Aider directly, not from
    this fork.**
  - **`repowiki map` works and ranks correctly**: on flux it put `errors.py`, `jsonio.py`,
    `executor/types.py`, `proc.py` on top — the four most-imported modules — in 0.2s with no LLM.
    On a 3-file repo everything ties, which is the right answer to "no signal", not a bug.
  - **Not taken as a dependency.** The `map` subcommand ships inside a full wiki generator
    (litellm, openai, numpy — 57 packages) for a zero-LLM feature, so the default command runs it
    through `uvx` and `[repo_map] command` makes the ranker swappable — same "tool as
    configuration" seam as the gate suite.
  - **flux owns cache, staleness and slicing.** The git HEAD at generation time is stored, and a
    map generated at a different commit is labelled as possibly out of date *inside the pack*
    rather than presented as current — stale context is the dominant residual risk (plan.md §7).
    A ranker that cannot run raises; caching an empty map would later read as "this repo has no
    important files", which flux must never conclude by accident.
  - Two smaller things worth keeping: exclusions are applied *after* the ranker picks its top N,
    so flux over-fetches (`OVERFETCH = 3`) or the map silently shrinks by however many
    flux-owned files happened to rank; and the `post-merge` hook is **opt-in**
    (`flux index --install-hook`), never part of `flux init` — it runs on every merge in a repo
    flux does not own, it refuses to clobber an existing hook, and it ends in `|| true` so a
    ranker problem can never become a git problem.

- 2026-08-18 — **T4 done (bar the repo map, split out as T4b).** M0's exit benchmark is met:
  a hand-written ticket in a scratch `tinylib` repo went brief → implement → gates → tagged
  commit → metrics line. Gates green, 362 tests (was 203). New modules: `flux/proc.py`,
  `flux/gates/`, `flux/config.py`, `flux/scaffold.py`, `flux/git.py`, `flux/tickets.py`,
  `flux/stages/`. design.md §1 amended (gates section, stage-commit semantics, budget
  correction). What the live runs taught, in the order it cost something:
  - **The token budget was measuring the wrong thing.** `_hard_stop` compared
    `Usage.total_tokens` against `max_tokens`; a 31-turn session reported 893k because a cached
    prefix is re-read every turn, and the first live run parked at "893,257 tokens against a
    budget of 200,000" having actually consumed ~44k. Now `Usage.budget_tokens` (uncached input
    + cache writes + output). Budgeting on the total caps *turns*, not work, and penalises the
    prompt caching the pack shape exists to earn.
  - **A headless session cannot answer a permission prompt.** The first run could not execute a
    single Bash command, so instead of running the gates it hand-traced all seven test cases in
    prose and wrote a long caveat into `impl-notes.md`. The implement stage now grants
    `Bash(<gate command>:*)` for exactly its configured gates. Same ticket afterwards: 31 turns →
    ~10, 97s → 30s, ~44k → 8k uncached tokens. **Any stage that is told to verify something must
    be given the means to.**
  - **Gate subprocesses inherited flux's own virtualenv.** flux runs from `.venv`, so a target
    repo with no typechecker got a confident `0 errors` from *flux's* pyright, and a bare
    `pytest` gate ran flux's pytest against the target and failed on `No module named 'tinylib'`.
    `flux.proc.clean_env` now strips `VIRTUAL_ENV`/`CONDA_PREFIX`/`PYTHON*`/`UV_PROJECT*` and the
    matching `bin` entries from `PATH`. Same principle as ADR 0010's credential strip — the
    parent's environment must not change what the child measures. No ADR: it is an
    implementation of 0005, not a new decision.
  - **A gate that cannot run is a failed gate**, never a skipped one. This is the rule the two
    findings above both argue for.
  - **`ExecConfig.hooks` read off the class is a slot descriptor**, not the default mapping —
    `dict(ExecConfig.hooks)` crashed the first live run before any API call. `NO_HOOKS` is now
    public in `executor/types.py` for callers that need the default *value*.
  - **`Stage.name`/`Gate.name` became read-only properties** so implementations can be frozen
    dataclasses. Nothing else changed in the runner: `ImplementStage` dropped into
    `run_ticket(ticket, Pipeline(...), executor)` with no edits to T3's spine, which is the
    claim T3 was making.
  - **`flux unpark` added** (not in plan.md §4's command list). A park asks a human to look;
    without a way to say "I looked", the only recovery was deleting the state directory, which
    also discards the checkpoints triage wants. It clears the park and resets `stage_runs`,
    and deliberately leaves the failed stage's checkpoint (not ok → the stage reruns).
  - **`flux run --dry-run`** prints the next stage, its `ExecConfig`, its gates and the exact
    pack. Hydration is pure, so this is the whole model input — the cheapest way to review a
    context pack before paying for it, and how the packs above were checked.
  - Gate suite is configuration (`[[gates]]` in `flux.toml`), commands are `shlex`-split and
    never shell-run, and `flux init` writes a starter suite matched to the repo (uv/pnpm/yarn
    detected from lockfiles). An unrecognised repo gets **no** gates and a warning, rather than
    a guess that would make an ungated pipeline look green.
  - Ticket briefs are `.flux/context/<ticket>/ticket.md` at M0; `flux.tickets.load_ticket` is
    the single place M4 swaps in `bd show`.

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
