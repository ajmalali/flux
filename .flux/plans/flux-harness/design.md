# flux — Implementation Design: state machine, executor, and artifact handoff

Companion to `plan.md`. This answers the two mechanism questions concretely:
**(1) what is the state machine and where does state live**, and
**(2) how are stage outputs offloaded to artifacts and reliably picked up in a fresh context**.

## 1. The state machine

There is no framework and no long-lived process. The "state machine" is three things:

1. **A transition function** — plain code that, given a ticket's persisted state, returns the
   next stage to run (or `None` / `parked`).
2. **Persisted state** — split across three stores by audience, never held in runner memory:

   | Store | Holds | Why there |
   |---|---|---|
   | beads (`bd`) | ticket status, deps, human-visible comments, park notes | inter-ticket scheduling + human triage surface |
   | `.flux/context/<ticket>/` | handoff artifacts: context pack, `tests.json`, `review.json`, notes | the *interface between stages*; git-diffable |
   | `.flux/state/<ticket>/` | stage checkpoints: `<stage>.done.json`, retry counters | idempotency/resume; machine-only |

3. **A stateless runner** — can be killed at any point and re-invoked; it reconstructs
   everything from disk. Resume *is* rerun.

### Core abstractions

```python
class Executor(Protocol):                       # ADR 0007 — the ONLY seam to Claude
    def run(self, pack: PromptPack, cfg: ExecConfig) -> ExecResult: ...

class ClaudeAgentSDKExecutor:                   # sole module importing claude_agent_sdk
    ...

# Cap semantics (established in T2): `max_turns` is the only cap the CLI always enforces.
# The SDK's task budget (`--task-budget`) is model-gated — models without support reject the
# request with `400 This model does not support user-configurable task budgets` — so
# `max_tokens` is a flux-side budget (recorded in metrics, enforced by the runner) and sending
# it to the API is opt-in per stage via `advertise_token_budget`.
#
# T4 correction: `max_tokens` is measured in **uncached** tokens (`Usage.budget_tokens` =
# uncached input + cache writes + output), not `total_tokens`. A cached prefix is re-read on
# every turn, so a 31-turn Sonnet session on a 660-token pack reported 848k cache reads while
# consuming ~44k. Budgeting on the total would cap how many *turns* a stage may take and would
# punish the prompt caching the pack is structured to earn.
#
# Terminal CLI errors (turn cap hit, API error) arrive as a raised exception from the SDK
# message stream, not as an error ResultMessage. The executor converts those to
# ExecResult(ok=False) so the runner can retry or park; typed ClaudeSDKError (missing CLI,
# dead process) surfaces as a genuine environment fault.

# Billing (ADR 0010): the executor rides the logged-in Claude subscription. Preflight on every
# run: assert CLI subscription auth is live and strip ANTHROPIC_API_KEY/AUTH_TOKEN from the
# child environment. API billing engages only via the approved fallback ladder (auth broken /
# policy change detected / usage limit hit) and never without user approval; on a usage-limit
# hit the default is park + schedule resume at window reset, which the checkpoint model makes
# free.

@dataclass(frozen=True)
class ExecConfig:
    model: str; effort: str                     # always explicit, never SDK defaults
    permission_mode: str                        # "acceptEdits" | "plan" | ...
    allowed_tools: list[str]
    max_turns: int; max_tokens: int             # caps in turns+tokens (subscription mode);
                                                # max_budget_usd applies only in API fallback
    advertise_token_budget: bool                # send max_tokens to the API as a task budget
    hooks: dict                                 # e.g. PreToolUse test-edit block

class Stage(Protocol):
    name: str
    def hydrate(self, t: TicketContext) -> PromptPack: ...      # disk → prompt (pure code)
    def config(self, t: TicketContext) -> ExecConfig: ...
    def required_artifact(self) -> ArtifactSpec | None: ...     # schema the stage MUST produce
    def gates(self, t: TicketContext) -> Sequence[Gate]: ...    # deterministic post-checks
    def commit(self, t, exec_result, gate_results) -> Outcome:  # verify; runner checkpoints
        ...

class Gate(Protocol):                           # T4 fills these in as subprocess wrappers
    name: str
    def run(self, worktree: Path) -> GateOutcome: ...

@dataclass(frozen=True)
class Outcome:                                  # what commit() concluded
    ok: bool; parked: bool; note: str; reason: str
    open_findings: bool | None                  # review-loop signal, derived from review.json
    detail: Mapping[str, Any]                   # stage facts persisted in the checkpoint
```

### The runner loop

```python
STAGES = [TestsStage(), ImplementStage(), ReviewStage(), FixStage(), PrStage()]

def run_ticket(ticket_id: str) -> None:
    t = TicketContext.load(ticket_id)                  # bd show + .flux/context/<ticket>/
    while (stage := next_stage(t)) is not None:
        pack = stage.hydrate(t)                        # deterministic, from artifacts only
        result = executor.run(pack, stage.config(t))   # ALWAYS a fresh session
        ok, artifact = validate_artifact(t, stage.required_artifact())
        if not ok:
            result = executor.run(pack.with_appendix(MISSING_ARTIFACT_NUDGE),
                                  stage.config(t))     # one retry
            ok, artifact = validate_artifact(t, stage.required_artifact())
            if not ok:
                return park(t, stage, "required artifact missing/invalid")
        gate_results = [g.run(t.worktree) for g in stage.gates(t)]
        metrics.record(t.id, stage.name, result.usage, gate_results)   # ADR 0008
        outcome = stage.commit(t, result, gate_results)
        checkpoint_write(t, stage.name, outcome)       # atomic: tmp file + os.rename
        if outcome.parked:
            return park(t, stage, outcome.note)
```

As built (T3):

- **One metrics line per executor call**, failed attempts included — retries are exactly
  what the store exists to surface, so dropping the failed attempt would understate the
  ticket's cost. The line for the final attempt carries the gate results.
- **A failed session (`ok=False`) is treated like a missing artifact**: one retry with an
  appended nudge, then park (`reason="session-failed"` vs `"artifact-invalid"`).
- **Two conditions skip the retry and park immediately**, because a second attempt cannot
  help and would cost more: a usage-window rejection (ADR 0010 — park, resume at reset) and
  a session that blew `ExecConfig.max_tokens`. This is where the flux-side token budget from
  T2 is enforced.
- **A crash is not a park.** An unexpected exception propagates: no checkpoint is written, so
  the stage reruns on the next invocation. `stage_runs` is persisted *before* the stage runs,
  so a crash loop still burns budget and terminates.
- Atomic writes are `.flux/fsio.write_atomic` (tmp file → fsync → `os.replace` → fsync dir).

### The transition function

Pure function of checkpoints — no hidden memory:

```python
def next_stage(pipeline, *, completed, state, config) -> Decision:
    if state.parked: return Decision.park(...)          # a parked ticket stays parked
    for stage in pipeline.stages:
        if stage.name == "fix": continue                # fix is only reachable via the loop
        if stage.name not in completed: return Decision.run(stage)
        if stage.name == "review" and state.open_findings:
            if state.human_accepted: continue           # human owns the rest; carry on to pr
            if state.review_iterations >= config.max_review_iters:
                return Decision.park("review loop exhausted", reason="review-loop-exhausted")
            return Decision.run(pipeline.by_name("fix"))
    return Decision.finished()                          # terminal: bd close
```

As built (T3), with the mechanics the sketch left implicit:

- **Pure.** `completed` and `state` are read from disk by the *caller*; the function
  itself does no IO, so the whole state machine is exercised in plain pytest.
- **`done(stage)` means "the checkpoint exists **and** `ok=True`."** A stage that ran but
  did not stand (gate failure, self-park) leaves its checkpoint for triage and reruns once
  the ticket is unparked — being skipped would be the wrong reading of a failed stage.
- **Where the loop counter lives.** Not in `review.done.json` (the runner deletes that file
  to force re-review) but in `.flux/state/<ticket>/run.json`, alongside `open_findings`,
  `human_accepted` and `stage_runs`. `review_iterations` increments when a review pass
  *completes*, so `max_review_iters=3` means three review passes and two fixes, then park.
- **Turning the loop is the runner's job, not a stage's.** After the fix stage commits, the
  runner clears the `review` and `fix` checkpoints so the reviewer re-verifies the fix.
  `open_findings` is set from the review stage's `Outcome`, which derives it from
  `review.json` — the artifact stays the source of truth, the runner stays generic.
- **`human_accepted`** lets a signed-off ticket continue to `pr` rather than terminating.
- **A stage-run backstop** (`max_stage_runs`, default 40, persisted before each stage runs)
  catches a stage that completes without ever writing a checkpoint. The transition
  function is already bounded; this catches the bug that would make it not be.

Properties this buys:
- **Idempotent**: a completed stage is skipped on rerun (checkpoint exists).
- **Resumable**: crash mid-stage → no checkpoint → the stage reruns cleanly (stage side effects
  are confined to the worktree, which git can reset to the last stage-commit tag).
- **Bounded**: the review↔fix loop can only oscillate `max_review_iters` times, then parks the
  ticket in bd with a failure note for human triage.
- **Inspectable**: `flux status` is just a read of bd + checkpoint files.

Each stage `commit()` also makes a git commit in the worktree tagged `flux/<ticket>/<stage>`,
so "reset to last good stage" is a `git reset --hard`, not bookkeeping.

As built (T4), that commit is **advisory, not a gate**: `flux.git.stage_commit` does `git add -A`
(a stage's output includes files it created), tags, and returns a result the stage records in its
checkpoint. A worktree that is not a repo, a repo with no `user.email`, and a clean tree all come
back as an unsuccessful-but-not-fatal result. Throwing away work that already passed its gates
over a bookkeeping problem would be the wrong trade; `stage_commits = false` turns it off.

### Gates (T4)

Gates are the merge authority (ADR 0005), so what they are *unable* to conclude matters as much
as what they conclude. Three rules, all in `src/flux/gates/`:

- **A gate that cannot run has failed.** Missing binary, missing worktree, timeout, empty command
  — all produce `passed=False` with a one-line reason. Skipping an absent typechecker would let
  "we did not check" be recorded as "there was nothing to find", which is the exact failure the
  suite exists to prevent.
- **The gate's environment is cleaned first.** flux is itself a Python program, normally launched
  from its own virtualenv, and a gate is its subprocess. `flux.proc.clean_env` strips
  `VIRTUAL_ENV`, `CONDA_PREFIX`, `PYTHONHOME`, `PYTHONPATH`, `UV_PROJECT*` and drops the
  corresponding `bin` directories from `PATH`. This is the same principle as the ADR 0010
  credential strip: the parent's environment must not change what the child measures. Observed
  before the fix — a target repo with no typechecker got a confident green from *flux's* pyright,
  and a bare `pytest` gate ran flux's pytest against the target and failed on an import.
- **A gate is data, not code.** `[[gates]]` entries in `flux.toml` carry `name`, `command`
  (string or argv; split with `shlex`, never run through a shell) and `kind`. `kind` picks only
  how output is *summarised* — the verdict is always the exit status. The `pytest` summariser is
  the opaque runner in gate form: counts, failing test ids and the first assertion line, never
  test source.

The implement session is granted `Bash(<gate command>:*)` for exactly its configured gates. A
headless session has nobody to answer a permission prompt, so without it "run the gates before you
finish" is an instruction the stage cannot follow — and the first live run did exactly what that
predicts: it hand-traced seven test cases in prose instead of measuring them, over 31 turns. With
pre-approval the same ticket took 30s and a third of the tokens. The grant adds no authority the
harness was not about to exercise anyway: flux runs those same commands itself moments later.

`Stage.name` and `Gate.name` are declared as read-only properties so an implementation can be a
frozen dataclass — the natural shape for something fully described by its configuration.

## 2. The artifact handoff contract (offload + fresh-context pickup)

The failure mode to design against: a stage "knows" something only in its transcript, the next
stage starts fresh, and the knowledge is gone. The contract has three rules:

**Rule 1 — a stage is done when its artifact validates, not when the model says so.**
Every stage declares a `required_artifact()` (path + JSON schema or markdown skeleton). After
the session ends, the *runner* checks that the artifact exists and validates. Missing/invalid →
one retry with an explicit nudge appended → then park. The model is asked to write the artifact
in the prompt, but the guarantee is runner-side validation, not model compliance.

**Rule 2 — evidence is recorded by the runner, never trusted from the transcript.**
Example: the tests stage must show tests fail for the right reason. `commit()` itself runs
`pytest` on the new test files and stores the red-run output into `tests.json`. If the model
claimed red but the runner sees green (or a collection error), the stage fails. Same for gates:
lint/typecheck/test/coverage results come from subprocesses the runner executes.

**Rule 3 — pickup is deterministic hydration; the model never needs to remember.**
`hydrate()` is pure code that assembles the prompt pack from disk. A fresh session receives
exactly the pack and nothing else — so "did the handoff work?" is testable without any LLM:
assert the pack contains what the stage needs.

### Prompt pack shape (cache-friendly, reference-resolved)

```
PromptPack
├── stable prefix (identical across stages of a ticket → prompt-cache hit)
│   ├── system prompt for the stage role
│   ├── plan/ADR summary          (re-injected every stage — plan-reminder effect)
│   └── context pack              (relevant-file list + repo-map slice + acceptance criteria)
└── stage tail (varies)
    └── resolved references to prior artifacts
```

Per change-doc B4, prior artifacts are **referenced, not pasted**: artifacts stay on disk keyed
by ticket, and prompts carry `path#section` references that the hydrator resolves into only the
needed slices under a token budget. Concretely: the fix stage's pack contains *unresolved
findings from `review.json`* plus *the diff hunks those findings point at* — never the
concatenation of all prior stage outputs. Invariant to assert in tests: measured pack size does
not grow monotonically across stages.

### Stage I/O table (the whole pipeline on one screen)

| Stage | hydrate() reads | ExecConfig | required_artifact() | commit() verifies |
|---|---|---|---|---|
| tests | ticket brief · context pack · plan summary | Sonnet/high · acceptEdits · PreToolUse blocks `src/` edits · tests-dir only | `tests.json`: test file paths, cases↔acceptance-criteria map | runner reruns tests: all red, failing for the right reason (no collection errors); red output stored |
| implement | brief · pack · **test paths + red output** (not test bodies) | Sonnet/high · acceptEdits · PreToolUse blocks test-file edits + dangerous cmds | `impl-notes.md`: what changed, deviations from plan, discovered work (→ bd `discovered-from`) | gates: lint, typecheck, **opaque test run** (pass/fail + minimal diagnostics), coverage delta; held-out tests run here too |
| review | brief · diff (`git diff` of stage commits) · rubric · plan/ADR summary | **different model**/high · plan mode (read-only) | `review.json`: findings (severity, file:line, rationale, rubric axis) | schema-valid; findings deduped; blocker findings force fix stage |
| fix | **unresolved findings slices** + referenced diff hunks | Sonnet/high · acceptEdits · same blocks as implement | updated `review.json` resolutions | full gate suite reruns; reviewer re-invoked only if gates pass |
| pr | impl-notes · resolved review · commit log | Haiku/low (or local, later) | PR body + pushed branch | `git push` succeeded; CI triggered ("land the plane") |

The opaque test runner is a flux subprocess wrapper: it runs the suite (including held-out tests
stored outside the worktree) and returns `{passed, failed: [test names], first_assertion_line}`
— never test source. The implement session's `allowed_tools`/hooks prevent it from reading test
bodies directly.

## 3. Metrics store and A/B baseline (P0, per change doc A1/A2)

- `metrics.record()` appends one JSON line per (ticket, stage) to `.flux/usage/metrics.jsonl`:
  tokens in/out, cache read/write, wall time, gate results, retry count, exploratory-call count
  (Read/Grep outside the context pack, from transcript), model, effort, billing mode
  (subscription | api-fallback), and `total_cost_usd` as a secondary estimate. On subscription
  (ADR 0010) the primary economics are **tokens + usage-window consumption**; `flux metrics`
  reports remaining-window pressure alongside the KPI table.
- `flux run --vanilla <ticket>`: runs the same ticket through plain `claude -p` with just the
  ticket text, records identical metrics. 1-in-10 cadence. Standing kill-criterion (written into
  `flux.toml`): if vanilla wins on cost AND quality for 3 consecutive samples, freeze harness
  feature work and investigate.

## 4. What gets built vs. bought

| Piece | Verdict |
|---|---|
| Runner, transition fn, stages, gates, hydrator, metrics | **build** (this doc; it's small) |
| Substrate (before building runner) | **spike first**: Archon + Gas City, half-day each, hard timebox; keep-custom is the default hypothesis; steal Archon's run-logging model regardless |
| Repo map | **buy**: `repowiki map` (zero-LLM) or Aider RepoMapper — whichever ranks better on the target repo |
| Wiki / architecture docs | **buy** (Phase 2): OpenWiki vs deepwiki-by-cc spike; keep custom only ADR log, interface catalog, exploration-call KPI hook |
| Research/planning templates | **mine**: GSD + OpenSpec formats; keep custom the mandatory dissent sections and different-model plan review |
| Intra-stage fan-out (e.g. multi-lens review) | **evaluate**: Claude Code native workflows bake-off vs single different-model reviewer |

## 5. Build sequence for the runner itself (first ~3 sessions of work)

1. ✅ (T2) `Executor` protocol + `ClaudeAgentSDKExecutor` + `ExecConfig` + usage capture → prove
   one `run()` round-trip with explicit model/effort and a metrics line written.
2. ✅ (T3) Checkpoint store + transition function + `run_ticket()` loop with fake stages
   (executor stubbed) → idempotency and crash-resume proven with plain pytest, no LLM.
3. ✅ (T4) Gates as subprocess wrappers + `flux init` + the implement stage → a hand-written
   ticket end to end in a scratch repo, gated and committed, with per-stage cost in
   `flux metrics` (plan.md M0 exit benchmark). The `PreToolUse` test-edit block waits for M1,
   when a tests stage exists for it to protect.

Everything else (review/fix/pr stages, opaque runner, A/B harness) lands on top of this spine
without changing it.
