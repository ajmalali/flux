# Real-world bench — design & metric spec

**Status:** proposal, awaiting sign-off. Nothing here is built yet.

One sizable `plan.md` for a full-stack app, five git worktrees each configured with a
different framework, the same plan handed to each, driven interactively by a human,
analysed retroactively from the session transcripts.

## Why this run exists (read `meridian-003` first)

The headless bench has already answered the cost question and it is not flattering:

| arm | delivered | acceptance | $/task | sessions |
|---|---|---|---|---|
| vanilla | 4/4 | 100% | $1.05 | 1.0 |
| flux | 4/4 | 100% | $2.92 | 4.0 |
| flux-lite | 4/4 | 100% | $1.05 | 1.0 |
| paul | 1/4 | 31% | $1.92 | 4.0 |

`flux-lite` — flux's machinery with none of its ceremony — matched `vanilla` to the
cent and beat full `flux` on every efficiency column while delivering identically.
By plan.md's own falsifiability rule the four-session lifecycle is on death row.

But **every arm that ran scored 82/82**. A corpus on which everyone is perfect cannot
discriminate on quality; it can only rank cost, and on cost ceremony always loses.
That ceiling — not realism — is the reason to run something else.

So this run has exactly one job:

> **Make quality separable, then see whether flux's ceremony buys any of it.**

If it does not, flux becomes flux-lite and the lifecycle is deleted. That outcome is
pre-accepted; the run exists to make it earned rather than assumed.

## The three design changes that matter

1. **The plan must be hard enough to produce failure.** Deliberate ambiguity, an
   algorithm with easy-to-miss edge cases, and cross-cutting requirements that a
   naive implementation satisfies locally and breaks globally. If all five arms
   score 100% again, this run tells us nothing that meridian-003 did not.
2. **Milestones with hard session boundaries.** flux's entire claim is about what
   survives a cold start. One long session tests none of it. Four milestones, each a
   fresh session, each graded — and every milestone re-runs *all prior* milestones'
   acceptance tests. Cross-milestone regression is the cleanest objective measure of
   continuity there is.
3. **A mid-flight requirement change at M3.** The thing no headless bench has tested
   and the single most common real-world event. Does the arm propagate the change
   through decisions already recorded, or does it leave stale truth in its state file?

Plus the axis the headless bench structurally cannot see: **what the human spends.**
flux's ceremony is paid in operator attention, and it has never been priced.

## Honest limits, stated before the run

- **N=1 per arm.** Five arms × one run cannot rank frameworks statistically. Treat
  small differences as noise. This run is powered to detect *large* effects and
  *qualitative* failure modes, nothing finer.
- **The operator is the largest confound.** By arm five you know the plan cold. The
  interaction protocol below exists to bound that leak; it cannot remove it.
- **Therefore the decision rule is pre-registered** (below) and written down before
  the first session starts, so an unfavourable result cannot be re-interpreted after
  the fact.

## Pre-registered decision rule

Fill in and commit before running. Draft:

- flux's ceremony **survives** only if, versus `flux-lite`, it delivers **either**
  ≥1 additional milestone, **or** ≥15% fewer blind-review defects, **or** ≥30% fewer
  corrective human interventions — while costing < 2× in dollars and < 1.5× in
  human-minutes.
- If flux ties flux-lite on quality at any cost premium, **the lifecycle is deleted**
  and flux ships as flux-lite.
- If flux-lite ties vanilla on quality *and* cost, the machinery itself (prime,
  budgeted state, filtered check) is next on the block.

---

# Metric spec

Everything below is derivable from the session transcripts
(`~/.claude/projects/<worktree-slug>/*.jsonl`) plus the graded worktree, except the
three marked **[manual]** and the two marked **[blind]**.

Interactive transcripts carry `message.usage` per assistant turn (input,
cache_creation, cache_read, output), `timestamp`, `requestId`, `isSidechain`,
`version`, `gitBranch`, and every human message. There is no `--output-format json`
envelope, so **cost is computed from tokens × published model price** rather than
reported by the CLI — identical formula for all arms, so comparisons hold.

## A. Delivery & quality — the primary axis

| # | metric | how |
|---|---|---|
| A1a | **`delivered@first`** — acceptance tests pass ∧ gate green, graded at the arm's first declaration of done | held-out suite, copied in after the milestone, removed after |
| A1b | **`delivered@fix1`** — same, after one fixed-wording nudge | the A1b−A1a gap *is* the value of the framework's own review step |
| A2 | **Cross-milestone regression** — do M(n)'s changes break M(1..n-1)'s tests? | re-run all prior suites at every checkpoint |
| A3 | **Spec fidelity** — % of plan.md's numbered requirements implemented | checklist, scored per requirement |
| A4 | **Blind defect count**, severity-weighted **[blind]** | anonymised final diffs → identical review prompt per arm |
| A5 | **Does it actually run** | boot the app, hit the documented endpoints, one screenshot |
| A6 | **Scope discipline** — LOC & files delivered vs. the reference | over-building is a cost, not a win |
| A7 | **Dead/unwired code** — files created but never imported | static check over the final tree |

A1 is binary per milestone; A3/A4 are where a hard plan lets arms actually separate.

## B. Machine cost

| # | metric | how |
|---|---|---|
| B1 | **$ per milestone / total** | Σ tokens × price, per session, bucketed by milestone |
| B2 | **Token split** — input / output / cache-write / cache-read | transcript usage |
| B3 | **Cache-write share of spend** | plan.md target column (< 15%) |
| B4 | **Context per request, p50 / p90** | `input + cache_read + cache_creation` per assistant turn |
| B5 | **Requests per milestone**; sessions > 150 requests | plan.md target column (0) |
| B6 | **Wall-clock per milestone** | first → last transcript timestamp |
| B7 | **Subagent share of spend** | `isSidechain: true` turns |
| B8 | **Context-exhaustion events** | auto-compact inside a milestone — recorded, never rescued |
| B9 | **Protocol compliance** | asserted, not trusted: no Opus session wrote app source, no Sonnet session planned, no unauthorised resume |
| B10 | **Outage events** | `isApiErrorMessage` entries classified as limit / transient / operator-side; sessions flagged `interrupted` and reported separately |

## C. Human cost — new, and the point of doing this interactively

| # | metric | how |
|---|---|---|
| C1 | **Human turns per milestone** | user-type transcript entries |
| C2 | **Characters typed** | same |
| C3 | **Operator wall-time engaged** | Σ (agent-turn-end → next human turn), capped at 5 min/gap to exclude walking away |
| C4 | **Ceremony invocations [manual]** | how many commands *you* had to fire (`/paul apply`, `/flux:wrap`, …) |
| C5 | **Interruptions & permission prompts** | denial + interrupt markers in transcript |
| C6 | **Corrective interventions** | human turns classified after the fact: `advance` (next step), `answer` (agent asked), `correct` (fixing wrong work), `unblock` (agent stuck) |
| C7 | **Steering pressure [manual]** | times you *wanted* to intervene and didn't — logged in the run journal |

**C6 is arguably the headline metric.** A framework that needs less steering to reach
the same result is better, and no headless bench can see it.

## D. Process efficiency — plan.md's existing targets, kept for continuity

| # | metric | target |
|---|---|---|
| D1 | Tool error rate | < 1.5% |
| D2 | Redundant re-reads per session | < 1 |
| D3 | Bash output volume per session | < 25k chars |
| D4 | Tool calls per delivered milestone | — |
| D5 | **File churn** — files edited ≥ 3× within one milestone | rework proxy |

## E. Continuity — the flux thesis, measured directly

| # | metric | how |
|---|---|---|
| E1 | **Cold-start ramp** | tokens + tool calls burned before the first `Edit`/`Write` of each post-M1 session |
| E2 | **Re-orientation reads** | files read in session N that were already read in session N-1 |
| E3 | **Continuity errors [blind]** | contradicts an earlier decision · re-asks a settled question · re-implements something that exists · violates a convention it set itself |
| E4 | **Requirement-change propagation** | after the M3 change: does stale truth persist in the arm's own state artifact? |
| E5 | **Handoff artifact size** | bytes of `.flux/state.toml` / `.paul/STATE.md` / spec folder, and how much of it enters context |

E4 is the sharpest test of the case for a state file. A framework that writes decisions
down and then fails to revise them is worse than one that writes nothing.

## F. Derived verdict columns

`$ / delivered milestone` · `human-minutes / delivered milestone` ·
`defects / delivered milestone` · `regression rate` · `corrective interventions / milestone` ·
**`review yield`** = `delivered@fix1 − delivered@first` (what the audit ceremony bought)

---

# The corpus

**App: "Ledger" — a small team expense-splitting service.** Chosen because it has a
genuinely non-trivial core (debt settlement) where careless work produces
plausible-but-wrong code that naive tests pass — exactly the separator meridian-003
lacked.

Stack: Next.js App Router + SQLite + Vitest + Playwright. Well-trodden enough that no
arm loses to unfamiliarity; the differences we want to measure are about method.

Grading weight sits mostly on HTTP-level API contract tests (fast, deterministic),
with a thin Playwright layer for the two UI flows that matter.

| milestone | scope | what it stresses |
|---|---|---|
| M1 | schema, session auth, groups + membership CRUD | foundation; conventions the later milestones must respect |
| M2 | expenses, split strategies (equal / exact / percentage), validation | breadth + rounding correctness (cents must reconcile exactly) |
| M3 | settlement engine (minimise transactions), balances view **+ the requirement change: multi-currency, retroactive to M2's model** | judgment, edge cases, and change propagation |
| M4 | audit log, CSV export, permission hardening | cross-cutting — touches every file built so far |

M4 is deliberately cross-cutting: it forces re-reading everything, which is precisely
where continuity machinery either pays for itself or does not.

Same rules as the headless corpus, and they are not optional:

- **Held-out acceptance tests, written before any arm runs**, kept outside every
  worktree. ADR 0011's lesson: graded on the repo's own suite, a do-nothing arm scores
  perfect.
- **A reference implementation per milestone**, and red-on-seed / green-on-reference
  verified before any arm is judged.
- **The corpus rule: if an acceptance test calls it, the plan must name it, including
  its signature.** This is what cost meridian-001 and -002 their validity.

---

# The arms

Five. Each differs only in seeded files, loaded plugins, and the procedure you drive.

| arm | setup | per-milestone procedure |
|---|---|---|
| `vanilla` | nothing seeded | one session: plan hand-off → implement |
| `flux` | `--plugin-dir` this repo | plan → audit → apply → wrap |
| `flux-lite` | `--plugin-dir` this repo | apply only |
| `paul` | PAUL framework copied in | interactive Q&A → `/paul apply` → `/paul audit` |
| `mattpocock` | mattpocock-skills plugin | its own skills (tdd / codebase-design / code-review) |

**Note on the `mattpocock` arm:** flux *vendors* six of Matt's skills already
(wayfinder, to-spec, to-tickets, ask-matt, review, grill). So this arm is partly a
subset of flux, which makes it unusually informative — if bare mattpocock-skills
matches flux, then flux's own additions (prime, state, check, lifecycle) are what
needs to justify itself, and the vendored layer is doing the work.

`speckit` and `agentos` are dropped: both voided in 003, agentos degrades to a refusal
without an interactive human anyway, and a human-driven arm is far too expensive to
spend on a framework we cannot drive faithfully.

---

# Protocol — what the operator does

## Setup (once)

1. New repo `~/Dev/ledger-bench`, seed committed on `main` (scaffold + tooling + the
   plan, no feature code).
2. Five worktrees, one per arm, one branch each. Ports allocated per arm
   (3101…3105) so dev servers never collide.
3. Framework payloads seeded per worktree. `.gitignore` the framework state so diffs
   stay comparable.
4. Held-out tests and references live in the bench repo, **never** in a worktree.
5. **Arm order randomised and written down before starting.** You get better at this
   plan with every arm; the order must not favour the arm we want to win.

## Per milestone, per arm

Launch isolated — this is not optional, or your global plugins leak into `vanilla`:

```
claude --setting-sources project --model <opus|sonnet> [--plugin-dir …]
```

- **Session and model boundaries: see "Session and model protocol" below.** In short —
  fresh session at every milestone, planning session on Opus and forbidden to touch
  application source, everything after it on Sonnet, as many within-milestone sessions
  as the framework prescribes.
- **Identical kickoff text across arms**, modulo framework command names.
- Milestone ends when the arm declares it done. Grade at that moment: copy in the
  acceptance suites for M1..Mn, run them, run the gate, record, remove. Then one
  fix round with the fixed wording, and grade again.

## Interaction rules — the part that keeps this fair

You may:
- issue the kickoff prompt, and the ceremony invocations the framework requires;
- answer the agent's questions **only from the plan**. If the plan does not say:
  *"not specified — use your judgment."*

You may **not**:
- point out a bug, suggest an approach, or paste an error the agent could have found;
- fix anything by hand.

If the agent is hard-stuck > 10 minutes, one `unblock` intervention is allowed. Record
it and its severity.

**Why answers are constrained.** Interactive frameworks (PAUL especially) extract spec
from you. Answer generously and they win on *information*, not method. Capping every
answer at "what the plan says, else your judgment" equalises information across arms —
and if a framework's questions are genuinely better, that shows up as fewer defects,
which is what we are measuring.

Every urge you suppress goes in the run journal as C7. That log is data, not overhead.

---

# Session and model protocol

The two questions this section settles: *when does a session end* (undefined for
`vanilla`, prescribed for `flux` — so it must be pinned by the runner or the
comparison is rigged), and *which decomposition steps may use the bigger model*.

## Boundaries come in two kinds

**Between milestones — a project fact, owned by the runner.** Review gates and day
boundaries exist in real work regardless of framework. Every arm starts a **fresh
session at every milestone**. Never `--continue`, never `--resume`.

**Within a milestone — a framework fact, owned by the arm.** `flux` takes four
sessions (plan / audit / apply / wrap), `vanilla` takes two. That is not unfairness;
it is the framework, and it is already priced by `$ per delivered milestone` and
`human-minutes per delivered milestone`.

An arm may open further sessions inside a milestone when the previous one ends. Each
is counted. Session count is a metric, not a budget.

**Context exhaustion is data, not a fault to be corrected.** If an arm hits
auto-compact inside a milestone — most likely `vanilla` on M4, which touches every
file built so far — record it as an exhaustion event and let it play out. That is
exactly the failure mode flux claims to prevent, and it is only evidence if it is
allowed to happen.

## The model rule

> **The first session of each milestone is the planning session and runs Opus. It may
> not edit application source — only plan / spec / state artifacts. Every subsequent
> session in that milestone runs Sonnet.**

Launch each session with the right `--model`; nothing switches mid-session, so every
transcript file carries exactly one model.

Why this preserves the no-model-difference rule: the planning phase becomes a property
of the **runner**, granted identically to all five arms, rather than a property of the
arms that happen to ship a plan command. Arms still differ in *how* they decompose and
*what artifact they leave behind* — which is the thing under test. They no longer
differ in model access.

For `vanilla` this means plan mode → implement. That is not a contaminated control; it
is stock Claude Code used the way a competent person uses it. A vanilla denied any
planning step would be a strawman, and meridian-003 already had the strawman winning.

**Risk, stated up front:** Opus planning may converge plan quality across arms and
mute framework differences — a ceiling effect of the kind that made meridian-003
uninformative on quality. Accepted, because the claim under test is not plan quality
but *what survives to the next cold session*, which is determined by the artifact
rather than by the model that wrote it.

**Compliance is computed, not remembered.** Transcripts record `message.model` per
turn and every tool call, so the analyser asserts that no Opus session wrote to
application source and no Sonnet session ran a planning step. Protocol violations
surface as findings instead of silently biasing a column.

## Grading: first declaration of done

> **The arm decides when the milestone is finished. You grade at that moment. That is
> the recorded delivery.**

This is the measurement that makes audit ceremony pay for itself or not: `flux` and
`paul` each spend a whole session reviewing before declaring done, and this is the
only column where that session can show up.

Then **one fix round**, worded identically for every arm and carrying no information:

> *"The milestone is not complete; review it against the plan."*

Grade again. Record `delivered@first` and `delivered@fix1` as separate columns — the
gap between them **is** the value of the framework's own review step. The resulting
tree carries into the next milestone either way, so an arm that stumbles at M1 builds
on real ground instead of collapsing for the rest of the run.

The nudge counts as a `correct` intervention under C6.

---

# Interruptions, limits, and recovery

The run rides a subscription, so it *will* be interrupted. meridian-002 was destroyed
by exactly this and the report published the damage as a result: 32 sessions came back
`You've hit your session limit`, and four of six arms were graded on work that never
ran. Interactively the same event is worse, because it lands mid-session with **files
already written**.

## What the transcripts actually record

Verified against this machine's transcript corpus. Every class below appears as an
assistant entry with `isApiErrorMessage: true` and parseable text, so the analyser
detects outages rather than trusting anyone to remember them:

| class | text | treatment |
|---|---|---|
| **session limit** | `You've hit your session limit · resets <time>` (sometimes `· progress saved`) | wait out the window |
| **transient** | `API Error: 500 …`, `Connection closed mid-response`, `The response stopped arriving` | retry immediately |
| **operator-side** | `Your computer went to sleep mid-response` | retry immediately |
| **compaction** | *no flag exists* — `isCompactSummary` never appears | detected behaviourally: context drops > 50% between consecutive requests inside one session |

## The recovery rule

Inherited principle: *a transport failure is waited out, not scored; what cannot be
waited out voids rather than zeroes.* Interactive adds a second axis — **did the
interruption cost anything?**

**1. Nothing written yet → discard and redo.** If the outage lands before the arm's
first `Edit`/`Write` in that session, kill it, wait out the window, start that session
fresh. Mark the dead transcript `aborted-clean` and exclude it from every metric.

**2. Work already written → resume the same session (`claude --continue`), and mark it
`interrupted`.** This is the important one, and it is *not* a violation of the
no-resume rule: that rule governs **milestone boundaries**. Resuming an involuntarily
killed session restores the state the arm would have had without the outage. It is
restoration, not a bonus.

The alternative — starting a fresh session and letting the arm re-orient — hands an
**extra cold start** to whichever arm got unlucky. An extra cold start systematically
*advantages* state-carrying frameworks (`flux`, `paul` recover from their state files)
and *penalises* `vanilla`. That is bias pointing straight down the axis under test, and
it is the one direction this experiment cannot afford to lean.

**3. A resume is not free, so normalise it.** Re-warming a cold cache produces a large
`cache_creation` spike, which inflates B3 (cache-write share) for whoever got unlucky,
and the outage gap inflates B6 (wall-clock). Both are reported twice: raw, and with
`interrupted` sessions excluded. C3 is already immune — its 5-minute per-gap cap
discards the outage automatically.

**4. Cannot resume the same day → void the milestone for that arm.** Void is excluded
from every denominator, never scored zero, and the verdict falls back to comparing arms
on milestones they both attempted.

**5. Never correct anything by hand.** No manual file edits, no git surgery, no
re-prompting with information the arm did not have before the outage. If the resumed
session needs a nudge, the wording is fixed and empty of content:

> *"Continue."*

An outage must cost the arm time, never change what the arm knows.

## Avoiding most of it: scheduling

- **Do not interleave arms.** Run one arm's milestone to completion, then move on.
- **Check the remaining window before starting a milestone, not during.** A milestone
  is a 1–2 hour unit; starting one with twenty minutes left guarantees the problem.
  `/usage` in any session shows where the window stands.
- **The operator commits after grading**, on every arm identically, with fixed wording
  (`bench: <arm> M<n> @first`, `… @fix1`). Never the arm — committing is a runner
  property here, not framework behaviour. This gives per-milestone diffs for A4/A6/A7
  and a rollback point that never requires hand-editing a tree.

## The run journal

One line per outage: arm, milestone, wall-clock, class, resumed or voided. Tiny to
keep, and the analyser cross-checks it against the `isApiErrorMessage` entries it
finds. **A disagreement between the journal and the transcripts is reported as a
finding**, not silently reconciled — that mismatch is precisely what let meridian-002
publish a rate limit as a benchmark result.

---

# What I build once this is signed off

1. `bench/realworld/setup.sh` — repo, worktrees, framework seeding, port allocation.
2. `bench/realworld/analyze.py` — transcript → metrics JSON per arm per milestone
   (reuses `fluxbench/metrics.py`; adds cost-from-tokens, human-turn and continuity
   metrics). Point it at a worktree path; it finds the project slug itself.
3. `bench/realworld/grade.sh` — copy suites in, run M1..Mn + gate, record, remove.
4. `bench/realworld/report.py` — the tables above, plus the verdict section.
5. The corpus: `plan.md`, four acceptance suites, four reference implementations,
   verified red-on-seed / green-on-reference.
6. A blind-review pass at the end: anonymised diffs, identical prompt per arm.

**Order matters.** The corpus is built and verified *before* any arm runs; the analyser
is built before the first session so nothing is discovered missing after the fact.

## Decisions (2026-08-21)

- **Stack: Next.js App Router + SQLite + Vitest + Playwright.** Grading weight on
  HTTP route contract tests; thin Playwright layer for the two UI flows that matter.
- **M3 change: the nastier one.** Not multi-currency. An expense included in a
  completed settlement becomes immutable; edits must produce a compensating
  adjustment carried into the next settlement round, with the original preserved.
  Scoped so it cannot corrupt the regression measure: settlements do not exist until
  M3, so M2's suite only ever exercises unsettled expenses and stays valid through
  M3 and M4. The arm restructures real code; the ruler does not move.
- **Model & sessions: settled.** See "Session and model protocol" below. Every arm
  gets a planning phase on Opus and implements on Sonnet; the phase is a property of
  the runner, not of the arm, so the no-model-difference rule survives intact.
