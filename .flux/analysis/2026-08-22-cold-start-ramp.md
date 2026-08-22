# The cold-start ramp — measured, before building `flux task`

Date: 2026-08-22
Ledger metric for: `.flux/adr/0001-execution-frontier.md` (the execution index)
Re-run with: `./bench/run.py ramp`
Code: `bench/fluxbench/ramp.py` · 8 tests in `tests/test_bench.py::ColdStartRampTests`

## Why this was measured first

ADR 0001 makes `flux task` answerable to one number — the **cold-start ramp**, the
tokens and tool calls a session spends before its first `Edit`/`Write` — and states
its own falsifier: *ramp does not shrink ⇒ the frontier was not where context went;
delete it.* That number had never been measured. It was the same position the decay
premise was in the day before, and that one did not survive contact with the data.

Corpus: **175 real interactive sessions, 129 of which reach an edit**, across 16
repos. Bench sessions are excluded — a `claude -p` arm is handed its task in the
prompt and has no frontier to derive, so including ~100 of them would have halved
every median and flattered the metric. Sessions that never edit are excluded rather
than imputed: they had no first edit to approach.

## The answer

**The ramp is real and big. The frontier is a small, concentrated minority of it —
and the part that is expensive is a problem `flux prime` already solves.**

| | median | p90 | mean |
|---|---:|---:|---:|
| tool calls before the first edit | 21 | 37 | 23.7 |
| context growth before it | 47,727 tok | 114,985 tok | 58,577 tok |
| context already there at the first call | 38,349 tok | 46,231 tok | 39,190 tok |

So a session spends ~21 tool calls and ~48k tokens getting ready to work. That is a
large ramp, and it is the number ADR 0001 was pointing at. But it does not decompose
the way the ADR assumed:

| bucket | calls | % of calls | result tokens | % of tokens | can an index remove it? |
|---|---:|---:|---:|---:|---|
| frontier | 467 | 15% | 867,522 | 31% | **yes** — status, plans, queues, handoffs, `git log` |
| docs | 108 | 4% | 84,784 | 3% | no — CLAUDE.md, ADRs, specs |
| code | 1,896 | 62% | 1,668,465 | 60% | no — reading the source about to be changed |
| other | 592 | 19% | 138,995 | 5% | no — builds, test runs, shell plumbing |

**60% of the ramp is reading the code.** No execution index removes that. The ceiling
on what a perfect `flux task` could save is the frontier row alone:

| | median | p90 | mean |
|---|---:|---:|---:|
| frontier calls | 3 | 9 | 3.6 |
| frontier result tokens | 2,715 | 20,563 | 6,725 |

Against a median ramp growth of 47,727 tokens, the median session would save
**2,715 tokens — 5.7%**. At p90 it is 17.9%. That is the whole prize.

## The finding that actually decides it

The frontier cost is not spread across the corpus. It is one repo.

| corpus | n | median ramp | median frontier calls | median frontier tokens |
|---|---:|---:|---:|---:|
| zaps/kiosk (PAUL, 299 KB `STATE.md`) | 44 | 27 calls | 6 | **14,083** |
| everything else | 85 | 17 calls | 1 | **1,098** |

**75% of every frontier token in the corpus is kiosk.** The single biggest ramp reads
in the whole dataset are `.paul/STATE.md` at 50–52 KB and `.paul/phases/*/NN-PLAN.md`
at 48–60 KB, read whole, at the start of a session, to work out where the project is.

In a repo with no state framework, re-deriving the frontier costs about **1,100
tokens** — roughly one `git log` and one glance at a README. There is no problem
there to solve.

**And flux already ships the fix for the case where there is one.** `flux prime`
replaces exactly that read: kiosk's 299 KB `.paul/STATE.md` against a prime pack
capped at 2,000 tokens. The expensive frontier is a PAUL-shaped problem, and the
capability that addresses it is built, shipped and adopted in kiosk as of 2026-08-20.

`flux task` would be competing for what is left *after* prime: a median of 3 calls
and 2,715 tokens.

## What this does not settle

Two things, and the first is the real one.

**1. This measures the ceiling on *removing* frontier reads. It cannot see whether an
index would make the 60% code bucket better targeted.** ADR 0001 has the index store
*declared files* per task. A session that starts knowing "task X touches these four
files" might read four instead of fifteen — an effect on the largest bucket that no
amount of transcript mining can detect, because no session in this corpus had that
information. If `flux task` is built, **this is the mechanism it should be built for,
and the ledger metric should be code-bucket ramp, not frontier ramp.** The frontier
justification is spent.

**2. The prime before/after comparison is underpowered and proves nothing yet.**

| corpus | n | median ramp calls | median frontier calls |
|---|---:|---:|---:|
| before 2026-08-20 | 112 | 21 | 3 |
| on/after | 17 | 16 | 0–3 (unstable at this n) |

Worse: **kiosk has had zero sessions since it adopted flux.** The one repo carrying
75% of the frontier cost, and the adoption that was supposed to remove it, have never
met. Until one real kiosk session runs on flux, prime's effect on the number it was
built to move is unmeasured.

That is also the cheapest possible experiment available: **run one real kiosk session
on flux, then re-run `./bench/run.py ramp`.** If the 14,083 collapses toward 1,098,
prime captured the prize and `flux task`'s frontier case is closed by its own metric.

## Method notes

- **Frontier vs docs is drawn narrowly on purpose.** Only files that answer *what is
  done and what is next* (status, plans, roadmaps, queues, handoffs, `state.toml`,
  `git log`/`status`) count as frontier. CLAUDE.md, ADRs, READMEs and specs are
  orientation an index does not replace, and they get their own bucket. Counting
  them for flux would have manufactured the result the ADR was being tested for.
- **Calls and tokens are both reported because they disagreed.** Counted by calls the
  frontier is 15% of the ramp; counted by the tokens its results put into context it
  is 31%. The first version of this analysis reported calls only and understated the
  case for flux by half. Tokens are estimated from tool-result bytes (÷4).
- **A defect found and fixed mid-analysis.** The first classifier read only
  `file_path`, so every ramp call made through Bash — `cat`, `sed -n`, `grep`, which
  a global instruction on this account tells the model to prefer over Read — landed
  in "other". That bucket was 69% of the ramp and the frontier and code buckets were
  understated threefold. Bash is now classified on its whole command line, past
  `cd … &&` and env-var prefixes, with a runner check so a heredoc mentioning `grep`
  is not counted as a file read. `other` fell to 19%. **The result in the first
  section is from the corrected classifier**; the uncorrected one would have said the
  ramp was 69% unclassifiable.
- Both buckets were spot-checked against their largest members before any conclusion
  was drawn: the biggest `frontier` results are PAUL `STATE.md`/`PLAN.md` reads, the
  biggest `code` results are `.tsx`/`.py` source files. Two strays were found and
  left (a `settings.local.json` counted as code, a scratchpad `plan-turns.txt`
  counted as frontier) — neither moves a figure.
- Main-chain only; subagent calls are excluded, as in `decay.py`.
- The running session is itself in the corpus and grows while the command runs. At
  n=175 this is noise; in the n=2 cells of the prime table it is not, which is part
  of why that table is reported as underpowered rather than as evidence.
