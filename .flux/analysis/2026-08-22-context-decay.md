# Does quality decay as context grows? — measured

Date: 2026-08-22
Prerequisite to: `.flux/adr/0001-execution-frontier.md`, rule 2 (task-size budget)
Re-run with: `./bench/run.py decay`
Code: `bench/fluxbench/decay.py` · 15 tests in `tests/test_bench.py::ContextDecayTests`

## The answer

**There is no knee.** No context size at which anything measurable falls off a cliff.

More precisely, across 414 transcripts / 16,909 main-chain tool calls / 344 sessions
on this account:

- **Correctness does not decay.** The one proxy that is about the model's picture of
  the code being wrong — Edit/Write failing with *"String to replace not found"* or
  *"File has not been read yet"* — is **flat** within a model family: 0.91%, 0.89%,
  0.73%, 0.85%, 1.37% across the 75k → 300k+ bins. No trend, and the sample cannot
  rule out a small one (see *Power*).
- **Re-orientation cost does rise, and the step is at ~100k, not at the 200k window
  boundary.** How often the model reads a file it has read within its last five
  reads roughly **triples** across 100k: 10.7% / 9.2% below, then 26.6% / 28.9% /
  32.6% above. It holds within-session — each session compared against itself — at
  every cut tried, but only marginally (sign-test p=0.09 at 200k, p=0.22 at 100k).
- **File churn does not rise.** Once the exposure artifact is removed, re-editing a
  recently-edited file is flat, and *within-session it falls* (9 sessions worse
  above 200k, 18 better; −7.9pp mean).

So: what a long context costs you here is **re-reading, not correctness**. That is a
cost curve, not a quality cliff — and ADR 0001 rule 2 asks for a hard refusal, which
a cost curve does not license. See *Consequence* below.

## What had to be fixed before any of it meant anything

Three naive versions of this measurement each return a confident wrong answer.

### 1. Most "tool errors" are permission friction

| class | n | share |
|---|---:|---:|
| **permission** | **589** | **57%** |
| exit (non-zero Bash) | 219 | 21% |
| other | 118 | 11% |
| **memory** (stale string / wrong path / unread file) | **64** | **6%** |
| limit (file too large, tool missing) | 46 | 4% |
| notfound (exit 126/127) | 6 | 1% |

*"This command requires approval"*, *"was blocked"*, *"the user doesn't want to
proceed"* — these measure the operator's allowlist warming up, and they cluster at
the **start** of a session, where the allowlist is coldest. Counted raw, the
tool-error rate **falls fivefold** as context grows (32.8% in the 0–25k bin → 1.9%
above 300k) and reads as proof that context *helps*.

> **This is a live defect in `bench`.** `metrics.SessionMetrics.tool_error_rate` is
> reported in the run table as if it were a quality column. 57% of it is the
> operator's permission config, and arms differ in it mostly by how their commands
> happen to trip the allowlist. `decay.classify_error` is the fix; wiring it into
> `report.py` is a follow-up task, not done here.

### 2. Naive churn is arithmetic, not behaviour

"Did this Edit touch a file already touched this session?" rises 26% → 76% with
context. It **must**: the touched set only grows. The metric is invalid as ADR 0001
specified it.

Replaced with a fixed-size window of the same activity — *is this file among the last
**five files edited**?* Five-files-ago is the same distance on tool call 5 and on tool
call 500, and windowing over edits rather than over raw tool calls means a run of
Bash calls in between cannot hide a return.

### 3. Between-session comparison confounds model with context

Pooled across all models, Edit/Write memory errors look like a real effect:

| | errors / calls | rate | |
|---|---:|---:|---|
| < 200k | 13 / 2,569 | 0.51% | |
| ≥ 200k | 19 / 1,284 | **1.48%** | 2.92× · Fisher **p = 0.0038** |

Within the opus family alone it evaporates:

| | errors / calls | rate | |
|---|---:|---:|---|
| < 200k | 10 / 1,367 | 0.73% | |
| ≥ 200k | 12 / 1,190 | 1.01% | 1.38× · Fisher **p = 0.52** |

Textbook Simpson's paradox. Sonnet and haiku sessions (691 Edit calls) **never exceed
200k**, and they sit at ~0.16% — not because sonnet is more careful, but because those
are short bench tasks on small greenfield trees. They drag the "< 200k" cell down, and
the entire pooled effect is that, not context.

Everything reported above is therefore given both un-stratified and within a single
model family, and every headline is also given **within-session**: one session
compared against itself either side of a cut, which removes model, project and task
difficulty in one step.

## The one thing that moves: re-orientation

Opus family, *is this file among the last five files read?*

| context | n | rate | 95% CI |
|---|---:|---:|---|
| 50–75k | 56 | 10.7% | 5.0–21.5 |
| 75–100k | 120 | 9.2% | 5.2–15.7 |
| 100–150k | 184 | **26.6%** | 20.8–33.4 |
| 150–200k | 121 | 28.9% | 21.6–37.6 |
| 200–300k | 144 | 32.6% | 25.5–40.7 |
| 300k+ | 78 | 25.6% | 17.3–36.3 |

Within-session, the same direction at both cuts:

| cut | sessions | worse above | better | tied | mean delta | sign-test p | pooled below → above |
|---|---:|---:|---:|---:|---:|---:|---|
| 100k | 8 | 5 | 1 | 2 | +13.9pp | 0.219 | 7.9% → 21.2% |
| 200k | 15 | 10 | 3 | 2 | +9.2pp | **0.092** | 23.7% → 30.5% |

Neither reaches p < 0.05. Consistent direction across three independent cuts and two
designs is worth something; it is not proof. Call it *suggestive, at the strength the
data can support*.

**Read it as cost, not damage.** Re-reading a file you just read is the model paying
to re-establish something it already had. It is exactly the thing `flux prime` and a
task-sized session are supposed to avoid — and exactly the thing that shows up as
dollars and wall-clock rather than as a failed acceptance test. Which is consistent
with `meridian-003`, where every arm scored 82/82 and only cost separated them.

## Everything reverses above 300k — do not read it as recovery

Re-reads fall to 25.6%, churn to 51.5%. Only **26 sessions** ever reach 300k and
**10** reach 400k. That is survivorship (a session that is going badly gets abandoned
or compacted before it gets that far) plus a shift in what those sessions are doing —
long write-ups and reports, not editing. Unexplained, and not evidence of a ceiling.

## Power — what "flat" is and is not evidence of

To detect the observed 0.73% → 1.01% in Edit memory errors at 80% power needs
**~18,700 Edit calls per side**. There are ~1,300 — underpowered by **14×**. Even a
doubling (0.73% → 1.5%) needs ~3,000 per side.

So *"correctness is flat"* means **"a correctness effect large enough to justify
refusing work is not present, and a small one cannot be seen here."** It does not mean
there is none. The re-read metric, by contrast, needed ~108 observations per side to
show what it shows, and has 176/261 — that one is adequately powered marginally, and
underpowered only for the within-session design.

Corpus ceiling, for planning a follow-up: 119 sessions ever pass 100k, 89 pass 150k,
65 pass 200k, 26 pass 300k. Waiting for this account to accumulate 18,700 high-context
Edit calls is not a plan. Answering the correctness question requires a **designed**
run — the same task executed at deliberately different context loads, graded on
acceptance — not more mining.

## Consequence for ADR 0001

Rule 2 currently reads: *"`flux task add` estimates the context a task will cost and
**refuses** one that exceeds `[task].budget_tokens`, exactly as `flux state set`
refuses an oversized write today."*

The premise it rests on — quality decays with context — is **not supported by the
proxies available**, and the correctness proxy is flat. A refusal is the right shape
for `flux state set` because that budget protects a hard, known limit (what fits in a
prime pack). This budget protects a **gradual cost curve with no cliff**, and the
number would be picked from a marginal effect, so the same refusal shape is not
earned.

**Recommended amendment** (written into the ADR alongside this file):

- Rule 2 becomes **advisory**: `flux task add` warns above the threshold and records
  the estimate; it does not refuse.
- The threshold, if one is wanted, is **~100k**, where the re-read step appears — not
  the 200k context-window boundary, which nothing in this data marks.
- Its ledger metric changes from *quality* to what was actually measured: **re-read
  rate above the threshold**, re-run by `./bench/run.py decay`. If sizing tasks under
  the budget does not lower it within two reporting cycles, the budget goes.
- The correctness claim is not abandoned, it is **deferred to a designed experiment**
  and must not be asserted in `plan.md`'s targets table until one runs.

Rules 1, 3 and 4 of the ADR are untouched by this — none of them depends on the
decay premise.

## Method notes

- Sources: `~/.claude/projects/**/*.jsonl` and `~/.flux-bench/runs/**/*.jsonl`,
  414 transcripts with tool calls, 2026-08-22.
- Context = `input_tokens + cache_read_input_tokens + cache_creation_input_tokens` on
  the assistant turn that issued the call — what the model actually had in front of
  it, per `metrics.Request.context_tokens`.
- Subagent (`isSidechain`) calls are excluded throughout: a subagent carries its own
  small context, and folding its calls in would credit high-context work to a
  low-context bucket.
- Intervals are Wilson, not normal — every interesting count is single digits over
  thousands of calls, and the normal approximation puts the lower bound below zero.
- Within-session tests use an exact two-sided sign test over per-session deltas.
  A pooled Fisher across the same sessions is reported beside it and **ignores session
  clustering**, so it is an upper bound on confidence, not the headline.
