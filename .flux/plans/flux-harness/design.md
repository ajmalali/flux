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
    guards: tuple[PathGuard, ...]               # PreToolUse path policy, as flux data (T5.2)
    hooks: dict                                 # raw hook config flux has no typed model for

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

### Reaching the artifact when the worktree is not the root (T5.1)

`ExecConfig.add_dirs` grants a session directories outside its `cwd`, and every stage with a
required artifact grants the ticket's context directory. This is not a convenience: handoff
artifacts live under the *root* (`.flux/context/<ticket>/`) while the session works in the
*worktree*, and those stop being the same directory the moment `flux run --worktree` is used —
which is the normal case at M5, and the case the A/B baseline needs so both arms share one
metrics store.

Observed live, 2026-08-18, before the grant existed: told to write an absolute path it had no
access to, the implement session wrote `impl-notes.md` at the same relative path *inside the
worktree*, the runner did not find it there, and the ticket parked after two paid attempts
(~36k uncached tokens). The failure mode is worth remembering in general — **a session denied
access to what it was told to do does the nearest thing it can reach, and reports success.**

### The repo map (T4b, ADR 0009)

Bought, and kept at arm's length: `[repo_map] command` in `flux.toml` names the ranker
(`uvx --from repowiki repowiki map` by default), and `flux index` runs it. flux owns only what a
ranker cannot know — the cache at `.flux/cache/repo-map.json`, the git HEAD it was generated at,
and how much of it a pack may carry (`pack_entries`, 25, against a cache of 60).

The staleness rule matters more than the ranking. `ImplementStage.hydrate` folds the map into the
context pack, and if HEAD has moved since generation it says so in the pack rather than presenting
the map as current: stale context is the dominant residual risk (plan.md §7), and a confident map
of an older tree is worse than no map. A ranker that cannot run raises rather than caching an
empty map — "no important files" is not a thing flux may conclude by accident.

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

**Correction (2026-08-19, ADR 0011): the cross-stage cache benefit described above is mostly
illusory as built.** The system prompt varies per stage and precedes the user prompt, so the
cache breaks before the "stable" prefix is reached; review and pr also run on different models,
and caches are per-model. Within-session caching across turns is real and is what the pack
structure earns. The `PromptPack` split stays — it is the right shape for determinism and for
measuring pack size — but no design decision may cite cross-stage cache hits until they are
measured. `types.py`'s docstring is amended at T5.5a.

### Stage I/O table (the whole pipeline on one screen)

| Stage | hydrate() reads | ExecConfig | required_artifact() | commit() verifies |
|---|---|---|---|---|
| tests | ticket brief · context pack · plan summary | Sonnet/high · acceptEdits · PreToolUse blocks `src/` edits · tests-dir only | `tests.json`: test file paths, cases↔acceptance-criteria map | runner reruns tests: all red, failing for the right reason (no collection errors); red output stored |
| implement | brief · pack · **test paths + red output** (not test bodies) | Sonnet/high · acceptEdits · PreToolUse blocks test-file edits + dangerous cmds | `impl-notes.md`: what changed, deviations from plan, discovered work (→ bd `discovered-from`) | gates: lint, typecheck, **opaque test run** (pass/fail + minimal diagnostics), coverage delta; held-out tests run here too |
| review | brief · acceptance criteria · diff (`git diff` of stage commits, tests excluded) · rubric · plan/ADR summary | **different model**/high · writes confined to the context dir · PreToolUse blocks reading tests · no Bash | `review.json`: findings (severity, file:line, rationale, rubric axis) | schema-valid; findings deduped; blocking-severity findings force fix stage |
| fix | **unresolved findings slices** + referenced diff hunks | Sonnet/high · acceptEdits · same blocks as implement | updated `review.json` resolutions | full gate suite reruns; reviewer re-invoked only if gates pass |
| pr | impl-notes · resolved review · commit log | Haiku/low · writes confined to the context dir · no Bash | `pr.md`: title + Summary/Changes/Review/Risk | gates green on the tree being pushed; the branch read back out of the remote at the local sha (see T5.4 below on "CI triggered") |

The opaque test runner is a flux subprocess wrapper: it runs the suite (including held-out tests
stored outside the worktree) and returns `{passed, failed: [test names], first_assertion_line}`
— never test source. The implement session's `allowed_tools`/hooks prevent it from reading test
bodies directly.

### The tests stage and its hardening, as built (T5.2)

`flux.testrun` is the opaque runner, and the `pytest` gate summariser is now the *same* parser —
what a session may learn from a gate verdict and what the red step records cannot drift apart.
`[tests]` in `flux.toml` holds where tests go, the argv, and the held-out directory; the argv
defaults to the repo's own test gate rather than being spelled twice, because a red step measured
with a different command from the gate is not evidence about the gate.

- **Red for the right reason is three conditions, and the prompt teaches the technique that makes
  them satisfiable.** No collection errors, nothing passing, at least one failure. The hard case
  is the ordinary one — the module under test does not exist yet, so a top-level import is a
  *collection error*, not a failing test. The tests stage's system prompt says to import inside
  the test function. Confirmed live: the session did exactly that and produced
  `2 failed`, `first assertion: ModuleNotFoundError`, with the suite collecting cleanly.
  A rule the session cannot satisfy is not hardening, it is a park with extra steps.
- **The tests stage does not run the test gate.** It is judged on the suite being *red*; a gate
  demanding green would fail every tests stage that worked. Lint and typecheck still run — a test
  file is code. Gate selection is by name (`[tests] gate`, else the `pytest`-kind gate, else one
  called `test`), never by re-deriving a command.
- **Two guards, one mechanism** (`flux.executor.guard.PathGuard` → `PreToolUse`). The tests stage
  is allow-only (tests dir + its context dir); implement and fix are deny (tests dir, held-out
  dir, and test-shaped basenames anywhere). Reading is blocked as well as writing on the deny
  side: a session that can read the assertion can write to *that assertion* rather than to the
  requirement, which hands back through `Read` exactly what the opaque gate withholds. The policy
  is flux data and a pure function; `sdk.py` compiles it, so ADR 0007's seam holds and the whole
  of ADR 0005's structural hardening is provable in plain pytest.
- **The guard is the cheap block; the digest is the teeth.** A guard reads the path arguments of
  path-taking tools, so it cannot see a shell redirect and cannot filter a repo-wide `Grep`. So
  `tests.json` stores a SHA-256 per test file and the implement stage re-hashes them before it is
  allowed to stand: a test changed *by any route at all* fails the stage with
  `reason="tests-modified"`. Evidence beats prediction — the same reason gates exist.
- **Held-out tests are an ordinary gate, appended per ticket.** `.flux/held-out/<ticket>/`, run
  only at implement time, and only when the ticket has any. `PYTHONPATH` is set to the worktree:
  the gate environment is otherwise cleaned so a gate measures the target rather than flux, but
  pytest inserts the *test file's* directory, so without it the held-out tests could not import
  the code they test. That restores what they would have had inside the worktree, which is the
  only difference held-out is meant to make.
- **`ArtifactSpec.check`.** "The key exists" is a weak reading of "valid" for an artifact that is
  a *map*: a `tests.json` whose `cases` is `[]` passes `required_keys` and tells the next stage
  nothing. A structural check at validation time makes that cost one nudged retry instead of a
  park, which is the loop the runner already owns. `review.json` will want the same at T5.3.
- **The checkpoint digest is taken after `commit()`, not before.** The tests stage writes the red
  run it observed back into its own artifact, so the pre-commit hash described a file that no
  longer exists in that form.

### The review and fix stages, as built (T5.3)

`flux.diff` parses a unified diff into files and hunks, `git.ticket_diff` produces one bounded by
the ticket's own stage tags, and the two stages sit either side of it: the reviewer reads the
whole diff, the fixer reads only the hunks its findings point at.

- **The reviewer is read-only by *guard*, not by `plan` mode — a correction to this document.**
  The table above used to say `plan` mode, and the SDK documents that mode as "Planning mode, no
  execution of tools": it would also stop the reviewer writing `review.json`, the one artifact the
  stage is judged on, so every review pass would park on a missing artifact. `review_stage_guard`
  confines every write to the ticket's context directory instead. That forbids strictly more of
  the *repo* than plan mode does, and unlike a permission mode it is flux data, so what a reviewer
  may write is a pytest assertion rather than a property of the CLI.
- **The reviewer is blindfolded to the tests, and this is about the fix stage, not the reviewer.**
  `review.json` is read by the stage that edits code, so a reviewer able to quote an assertion
  would hand back through a finding exactly what the opaque test gate withholds. Two mechanisms,
  same policy: `source_stage_guard` (unchanged from implement) stops it *reaching* for a test, and
  `diff_exclusions` stops one *arriving* inside the diff — the tests stage commits its work, so
  the ticket's own diff contains the test source until it is excluded. What the reviewer gets
  instead is the `cases` map from `tests.json`: acceptance criteria, which are a statement of
  requirements with no test source in them.
- **The diff excludes the ticket's context directory too, and that was found by using it.** The
  first review pack quoted `impl-notes.md` — flux's handoff artifacts are committed beside the
  code, so `git diff` hands the reviewer its own plumbing as if it were work under review,
  including the artifacts the stage I/O table deliberately withholds. Excluding the ticket's
  context directory, not all of `.flux/`, keeps a ticket that genuinely edits an ADR reviewable.
- **Severity is the machine's business, so it is closed and configurable.** `[review]
  fix_severities` (default `["blocker"]`) is the only part of a review flux acts on: those
  findings set `open_findings`, turn the loop, and park the ticket when the passes run out.
  Everything else is recorded and read by a human. Findings are deduped, numbered and sorted by
  the *runner* rather than requested from the model — a duplicated blocker is one extra paid fix
  session and one more chance to park.
- **The fix stage is the implement stage's twin, on purpose.** Same guard object, same gate
  suite (held-out included), same digest backstop, same granted directory — asserted equal in
  pytest, because anywhere they differ is somewhere a session that could not game the first could
  game the second.
- **The reviewer re-reads the code, never the resolutions.** A fixer that marks a finding resolved
  without changing anything gains nothing: the next pass hydrates from the diff, so the finding
  comes back, and the loop bound turns a standoff into a park. That is also why the fix stage may
  dispute a finding in writing — a dispute the next review does not repeat is settled, and one it
  repeats is a disagreement for a human.
- **Two stages now raise `ParkSignal` from `hydrate()`.** Review with an empty diff, fix with no
  unresolved findings. `_run_stage` calls `hydrate` inside the runner's `ParkSignal` handler, so
  this parks correctly having spent nothing — which is the point, since both conditions mean the
  session could only discover, expensively, that there was no work.

### The pr stage, as built (T5.4)

The last stage, and the one whose split between session and runner is drawn furthest towards the
runner. The session writes prose into `pr.md` — a title and four body sections — and has no Bash,
no reach outside the ticket's context directory, and no knowledge of git. Everything that is a
*fact* is the runner's: it runs the gate suite one last time on the exact tree it is about to
push, pushes `HEAD` by refspec, re-reads the ref out of the remote, and opens the pull request.

- **"`git push` succeeded" is verified against the remote, not against an exit status.** A zero
  exit from `git push` is the subprocess equivalent of a transcript claim. `git.push_head`
  re-reads `<remote>/<branch>` with `ls-remote` afterwards and compares it with the local commit,
  so `PushResult.ok` means the remote genuinely holds that sha.
- **"CI triggered" is *not* claimed — a correction to the table above.** Whether a push starts a
  pipeline is a property of the forge's configuration, and flux has no way to observe it that is
  not polling a provider it does not know about. flux states what it measured (the branch exists
  at this sha; this suite was green on it) and states nothing else. The provenance footer flux
  appends to every body carries exactly those two facts, which is why it is written by the runner
  rather than asked of the session.
- **HEAD is pushed by refspec, so the local checkout never moves.** `HEAD:refs/heads/<target>`
  puts the work on the remote with no checkout, no branch creation, and no change to the tree a
  human may be sitting in. That is also what makes the protected-branch rule cheap: work done on
  `main` goes to `flux/<ticket>` instead of parking a ticket whose every other stage succeeded.
- **Three refusals, in `[pr]`.** Never a protected branch (`main`, `master`, `trunk`, `develop`
  by default); never `--force`, since a remote branch that already exists and does not contain
  this work is a collision for a human; drafts by default, because an unattended harness asking
  for review is asking a person for time and a draft asks without also claiming readiness.
- **A push that cannot happen has failed** — ADR 0005's gate rule, applied to landing. A repo with
  no matching remote parks (`reason="no-remote"`) rather than reporting a completed ticket that
  went nowhere; `[pr] push = false` is the supported way for a repo to mean "this lands nowhere",
  and then the stage writes the body and stands.
- **Opening the pull request is best-effort by default, and says so.** `gh` is used because it
  already holds the user's credentials — the same reason flux runs on the logged-in subscription
  (ADR 0010): flux does not want to be told a token. `[pr] create` is `auto` (open one if `gh` can,
  record why not otherwise), `always` (a failure to open one parks) or `never`. A branch that
  landed with no pull request is most of the job done, so `auto` does not park over it.
- **The gate suite runs a third time, deliberately.** The tree has not changed since implement or
  fix passed it, so this re-measures something already measured — for the cheapest evidence in the
  pipeline: a green suite recorded against the exact sha that lands, which is the difference
  between a pull request that *says* the gates passed and one that shows it.
- **Build output is excluded from what flux commits and from what it calls a diff.** T5.3 observed
  that `git add -A` in a repo with no `.gitignore` commits `__pycache__/*.pyc`, that the reviewer
  correctly reports them, and that *no fix can remove them from the diff* — so the loop cannot
  converge. `git.JUNK_GLOBS` is excluded at staging time and from `ticket_diff`. It applies to
  staging only, so a repo that already tracks such a file keeps tracking it: what a repo commits
  is that repo's decision.

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

As built (T5.1) — `flux/ab.py` writes the baseline arm, `flux/metrics/ab.py` reads it:

- **Three fairness rules, because breaking any of them hands the comparison to one side.**
  The baseline runs the *same model and effort as `implement`*, mirrored live rather than copied
  (re-routing the stage re-routes the baseline, or the A/B silently becomes a model comparison);
  it gets the *same gate pre-approval*, since T4 measured what a session that cannot run its
  gates does instead; and it *refuses to run in a worktree the harness already worked*, before
  spending anything, because that number would say vanilla solved it in one cheap turn.
- **A baseline sample writes no checkpoint and no artifact.** It is a measurement, not a
  pipeline run, and must never make the transition function think a stage is done.
- **"Wins" had to be defined, because the criterion's prose does not.** Cost is uncached input
  plus output summed over every line the ticket cost, retries included (cache reads excluded, for
  the same reason the runner's budget excludes them). Quality is an ordinal over the gates *flux*
  ran — all green > no gates at all > any failure — taking the **latest** verdict per gate name,
  so a gate that went red at implement and green after a fix ends green. Vanilla wins a ticket
  when it is **strictly cheaper and not worse**: the harness is the thing on trial, so a tie on
  quality at a lower price is a loss for it, not a draw.
- **The block prints even when it is empty**, saying "no paired samples yet". Silence would read
  as "nothing to report" at exactly the phase gate that exists to ask.

**Amendment (2026-08-19, ADR 0011): the quality ordinal as built cannot detect an unimplemented
feature.** "Gates green" is measured over the repo's own suite, which a vanilla arm that changes
nothing keeps green — so it can win a pairing against a harness run that actually delivered the
feature, and the kill-criterion can fire falsely. Before any benchmark number is trusted
(T5.5a), both arms must be judged by the same per-ticket held-out acceptance tests, written
before either arm runs and stored outside both worktrees; the ordinal gains a level for
"acceptance green" above "gates green".

As built (T5.5a): the acceptance verdict is an ordinary gate line named `held-out`
(`metrics.ab.ACCEPTANCE_GATE`, which `stages.implement.HELD_OUT_GATE` aliases so the two
spellings cannot drift). `flux.ab.vanilla_suite` composes the baseline's suite through the same
`held_out_gate` the implement/fix/pr stages use, so the two arms cannot be judged by different
suites; the gate's `PYTHONPATH` names each arm's own worktree. The ordinal reads: acceptance
green (3) > gates green (2) > no gates (1) > any red gate — acceptance included — (0); an arm
whose ticket has no held-out tests tops out at "gates green" on both sides, which keeps
old-style pairings comparable. One repair the first live pairing forced: held-out tests live
under the *root*, so pytest's upward conftest scan from them loads the root's own `conftest.py`
and puts the root — un-worked code — ahead of the worktree on `sys.path`; `held_out_gate` now
passes `--confcutdir=<held-out dir>` so acceptance judges the tree the session actually changed.

## 4. What gets built vs. bought

| Piece | Verdict |
|---|---|
| Runner, transition fn, stages, gates, hydrator, metrics | **build** (this doc; it's small) |
| Substrate (before building runner) | **spike first**: Archon + Gas City, half-day each, hard timebox; keep-custom is the default hypothesis; steal Archon's run-logging model regardless |
| Repo map | **bought**: `repowiki map` (zero-LLM), chosen in the T4b bake-off (`repo-map-memo.md`). Invoked as a configured command, not a dependency; flux owns the cache, the staleness signal and the slicing |
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
