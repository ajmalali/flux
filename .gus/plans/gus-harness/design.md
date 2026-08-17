# gus — Implementation Design: state machine, executor, and artifact handoff

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
   | `.gus/context/<ticket>/` | handoff artifacts: context pack, `tests.json`, `review.json`, notes | the *interface between stages*; git-diffable |
   | `.gus/state/<ticket>/` | stage checkpoints: `<stage>.done.json`, retry counters | idempotency/resume; machine-only |

3. **A stateless runner** — can be killed at any point and re-invoked; it reconstructs
   everything from disk. Resume *is* rerun.

### Core abstractions

```python
class Executor(Protocol):                       # ADR 0007 — the ONLY seam to Claude
    def run(self, pack: PromptPack, cfg: ExecConfig) -> ExecResult: ...

class ClaudeAgentSDKExecutor:                   # sole module importing claude_agent_sdk
    ...

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
    hooks: dict                                 # e.g. PreToolUse test-edit block

class Stage(Protocol):
    name: str
    def hydrate(self, t: TicketContext) -> PromptPack: ...      # disk → prompt (pure code)
    def config(self, t: TicketContext) -> ExecConfig: ...
    def required_artifact(self) -> ArtifactSpec: ...            # schema the stage MUST produce
    def gates(self, t: TicketContext) -> list[Gate]: ...        # deterministic post-checks
    def commit(self, t, exec_result, gate_results) -> Outcome:  # verify + write checkpoint
        ...
```

### The runner loop

```python
STAGES = [TestsStage(), ImplementStage(), ReviewStage(), FixStage(), PrStage()]

def run_ticket(ticket_id: str) -> None:
    t = TicketContext.load(ticket_id)                  # bd show + .gus/context/<ticket>/
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

### The transition function

Pure function of checkpoints — no hidden memory:

```python
def next_stage(t: TicketContext) -> Stage | None:
    if not done(t, "tests"):     return TestsStage()
    if not done(t, "implement"): return ImplementStage()
    if not done(t, "review") or open_findings(t):
        n = retry_count(t, "review")                   # stored in review.done.json
        if n >= t.config.max_review_iters:             # default 3
            return None if human_accepted(t) else Parked("review loop exhausted")
        return ReviewStage() if not done(t, "review") else FixStage()
    if not done(t, "pr"):        return PrStage()
    return None                                        # terminal: bd close
```

Properties this buys:
- **Idempotent**: a completed stage is skipped on rerun (checkpoint exists).
- **Resumable**: crash mid-stage → no checkpoint → the stage reruns cleanly (stage side effects
  are confined to the worktree, which git can reset to the last stage-commit tag).
- **Bounded**: the review↔fix loop can only oscillate `max_review_iters` times, then parks the
  ticket in bd with a failure note for human triage.
- **Inspectable**: `gus status` is just a read of bd + checkpoint files.

Each stage `commit()` also makes a git commit in the worktree tagged `gus/<ticket>/<stage>`,
so "reset to last good stage" is a `git reset --hard`, not bookkeeping.

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

The opaque test runner is a gus subprocess wrapper: it runs the suite (including held-out tests
stored outside the worktree) and returns `{passed, failed: [test names], first_assertion_line}`
— never test source. The implement session's `allowed_tools`/hooks prevent it from reading test
bodies directly.

## 3. Metrics store and A/B baseline (P0, per change doc A1/A2)

- `metrics.record()` appends one JSON line per (ticket, stage) to `.gus/usage/metrics.jsonl`:
  tokens in/out, cache read/write, wall time, gate results, retry count, exploratory-call count
  (Read/Grep outside the context pack, from transcript), model, effort, billing mode
  (subscription | api-fallback), and `total_cost_usd` as a secondary estimate. On subscription
  (ADR 0010) the primary economics are **tokens + usage-window consumption**; `gus metrics`
  reports remaining-window pressure alongside the KPI table.
- `gus run --vanilla <ticket>`: runs the same ticket through plain `claude -p` with just the
  ticket text, records identical metrics. 1-in-10 cadence. Standing kill-criterion (written into
  `gus.toml`): if vanilla wins on cost AND quality for 3 consecutive samples, freeze harness
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

1. `Executor` protocol + `ClaudeAgentSDKExecutor` + `ExecConfig` + usage capture → prove one
   `run()` round-trip with explicit model/effort and a metrics line written.
2. Checkpoint store + transition function + `run_ticket()` loop with a single fake stage
   (executor stubbed) → prove idempotency and crash-resume with plain pytest, no LLM.
3. Gates as subprocess wrappers + the tests/implement stages with their hooks → first real
   ticket end-to-end (plan.md M0/M1 exit benchmarks).

Everything else (review/fix/pr stages, opaque runner, A/B harness) lands on top of this spine
without changing it.
