# fluxbench

Does flux actually beat the alternatives, on the metrics it claims to move?

flux's `plan.md` says every feature must name a ledger metric and be deleted if it
doesn't move it. That rule is only enforceable if the numbers exist. This is where
they come from: one multi-task project, run end to end through several Claude Code
setups, measured on the same axes, graded by the same held-out tests.

```
./bench/run.py list                     # arms and projects
./bench/run.py verify --project X       # is the corpus fit to judge anybody?
./bench/run.py run --project X --arms vanilla,flux,paul --model sonnet --max-usd 30
./bench/run.py report <run-id>
```

Stdlib Python, no install step. Run artifacts land in `~/.flux-bench/runs/`, never
in this repo — flux ships as a plugin by copying its own directory, and a benchmark
must not ride along in every install.

## What an arm is

An arm is a Claude Code setup. It may differ from another arm in exactly three ways:

1. files seeded into the repo (`.claude/commands/`, framework payloads, …),
2. plugin directories loaded (`--plugin-dir`),
3. the sequence of prompts each task is driven with.

Everything else is fixed by the runner: model, effort, permission mode, denied
tools, the starting tree, the environment, and the grading suite. `Arm` has no
field for a model or an effort level, and there is a test asserting it never
gains one — otherwise a "win" might only ever mean a bigger model.

| arm | per-task procedure | what it is |
|---|---|---|
| `vanilla` | implement | the control: one session, the brief, the gate |
| `flux` | apply | flux as plan.md prescribes it: primed, one session, `flux check` |
| `flux-full` | plan → audit → apply → wrap | the opt-in lifecycle, for work that earns it |
| `paul` | plan → audit → apply → verify | the incumbent flux was distilled from |
| `speckit` | specify → plan → tasks → implement | GitHub Spec Kit |
| `agentos` | inject → implement | Agent OS v3's standards layer (see caveat) |

These two exist to keep flux honest against itself. They separate two claims that
are easy to conflate: what the deterministic machinery (prime, budgeted state,
filtered check) is worth, and what the four-session lifecycle costs on top of it.
The rule was stated in advance — if the lean arm beats the full one, plan.md's
falsifiability rule says the ceremony goes — and it did, twice: meridian-003
(4 tasks, every arm at 100% acceptance, full lifecycle 2.8x the cost) and
meridian-004 (m5, written specifically to punish a single pass; every arm 27/27,
2.9x). So the names swapped on 2026-08-22: `flux` is the lean path, `flux-full`
is the ceremony, kept for the one experiment this corpus cannot yet run
(`.flux/analysis/2026-08-22-ceremony-two-cycles.md`).

**Agent OS caveat.** v3 is built to interview the user: every command drives the
work through `AskUserQuestion`, and `/shape-spec` refuses outright unless the
session is in plan mode. `AskUserQuestion` is denied to every arm here — a
headless run has no human — so depending on it is a property of the framework
rather than a handicap imposed on it. But a hard refusal is not a graceful
degradation, so `/shape-spec` is excluded rather than burned on a stop. The
`agentos` row therefore measures Agent OS's standards layer, not its full loop,
and should be read with that in mind.

**Spec Kit note.** It ships project *skills*, not commands. They resolve by
explicit `/name` under `--setting-sources project` even though a headless session
never advertises them in context — verified by invoking a planted probe skill,
after asking the model "do you have this skill?" gave a confidently wrong "no".

## Why the project is multi-task and the sessions are never resumed

Nothing is resumed with `--continue`. Every step of every task is a cold session.
Carrying knowledge across that gap is the arm's job, done through whatever
mechanism it believes in — `.flux/state.toml`, `.paul/STATE.md`, a spec folder, or
nothing at all. That gap *is* most of what flux is, and a benchmark of independent
one-shot prompts would measure none of it. Tasks are ordered and build on each
other for the same reason.

## Why efficiency is never reported alone

The v1 harness had a working A/B rig and a broken verdict: it graded both arms on
the repo's own test suite, which stays green when a session changes nothing. A
do-nothing arm scored maximum quality at near-zero cost and could win the pairing —
so the kill-criterion could fire against the arm that actually delivered
(`.flux/archive/v1/adr/0011-benchmark-before-machinery.md`).

So every task ships **held-out acceptance tests**, written before any arm runs and
kept outside every worktree. They are copied in after the arm finishes, run, and
removed. An arm delivers a task only when its acceptance tests pass *and* the
repo's pre-existing gate still passes. In the report, no arm with zero deliveries
can win a column.

## Why a rate limit is void, not a zero

A benchmark's most expensive failure mode is a number that reads like a result
and isn't. Run `meridian-002` produced one: the account hit its rate limit
mid-run, 32 sessions came back in under a second with `api_error_status: 429`,
and the report went on to state that `paul` and `flux-lite` delivered 0 of 4.
Four of six arms were graded on work that never ran, in a table indistinguishable
from one where the frameworks had genuinely failed.

Two rules now stand between that and the report:

- **A transport failure is waited out, not scored.** Statuses in
  `driver.RETRYABLE_API_STATUSES` (429, 5xx, 529) are retried on a backoff of
  60s / 180s / 600s — long enough to ride out a rate-limit window. A retry is
  only ever attempted on an attempt that *cost nothing*: a session billed for
  turns may already have written to the repo, and re-running it would judge the
  arm against a tree its own abandoned attempt had moved.
- **What survives the retries voids the task.** The arm is abandoned rather than
  graded, and the task is recorded with a `void` reason. Void tasks are excluded
  from every denominator in the report — not counted as failures to deliver — and
  an arm with no scored tasks renders as `void` rather than as `0/4`. The targets
  table shows `—` for it, because an arm that never ran hits every target by
  doing nothing.

When arms end up with different task sets, the verdict stops comparing their
delivery columns and compares them on the tasks each pair **both** attempted.
That intersection is usually the only real evidence a spoiled run produced, and
throwing it away is its own kind of dishonesty.

The report applies the void rule to session records written before it existed, so
old runs re-read correctly instead of republishing the mistake.

## Why every task ships a reference implementation

`run.py verify` asserts two things per task, cumulatively, in order:

- **red** — the acceptance tests fail on the tree the arm receives. Otherwise they
  measure nothing.
- **green** — they pass once the task's `reference/` is applied, and the repo gate
  still passes. Otherwise the brief is ambiguous and every arm loses points for the
  task author's writing.

`verify` also refuses a task whose acceptance tests import names that are neither
in the seed nor mentioned in the brief — testing a helper nobody asked for
measures whether the arm guessed the author's imagination.

This is not hypothetical, twice over. The first smoke run had both arms fail the
same acceptance test on a boundary the brief never pinned down (`max_length=9`
against a 9-character slug). And m2 shipped with a worse version of it: the tests
bound to `refund_cents(price_cents, gap)` while the brief named only the module.
Vanilla wrote `refund_cents(booking, cancelled_at)` — a perfectly good design —
and lost a task it had actually delivered. That run was thrown away.

**The corpus rule, because red/green cannot enforce it.** The reference
implementation is written by the same person as the tests, so it agrees with them
by construction; verification can never catch a shared assumption. Therefore:

> If an acceptance test calls it, the brief must name it — including its
> signature. Anything else the test needs must already exist in the seed.

Signatures are the part that bites. `verify` catches unbriefed *names*; only this
rule catches unbriefed *shapes*.

## What gets measured

From the `--output-format json` envelope: cost, wall time, turns, permission
denials. From the session transcript: context size at every request, tool calls,
tool errors, redundant re-reads, Bash output volume.

The report's columns are `plan.md`'s targets table — median context per request,
cache-write share of spend, tool error rate, re-reads per session, Bash volume,
$ per task — plus delivery rate and wall time. "Context" counts cache reads:
cached context is still context, and reading `input_tokens` alone would report a
30k-token turn as 2 tokens.

## The verdict section

Under the table, the report answers the question in words: every metric `flux`
loses, who beat it, and by how much. "Is flux beating everything?" is not
readable off a twelve-column table at a glance, and the point of the exercise is
that an unfavourable answer triggers work rather than being quietly absorbed.
Pass a different focus arm to `report(records, focus=...)` to turn it on someone
else.

## Isolation

Sessions run with `--setting-sources project`, so the operator's own `~/.claude`
— every installed plugin, hook and skill — stays out of the measurement. Verified:
a bare session's cached prefix is ~6.5k tokens with it. The child environment is
scrubbed of `CLAUDECODE` and `CLAUDE_CODE_*` because the bench is usually run from
inside a Claude Code session.

The flux arm loads the plugin from this working tree with `--plugin-dir`, not from
the installed cache copy, so the benchmark always measures the flux that is checked
out right now — no version bump required.

## Third-party frameworks

`./bench/setup-frameworks.sh` stages them into `~/.flux-bench/frameworks`. Their
payloads are never vendored into this repo: flux's plugin install copies this whole
directory, and those licences are theirs, not ours.

- **PAUL** — copied from a repo that already has it (`PAUL_SRC=`, default
  `~/Dev/zaps/kiosk`). Only the framework is copied, never a project's `.paul/`
  state.
- **GitHub Spec Kit** — installed per-run by its own CLI; needs `uvx` on PATH.
- **Agent OS** — needs its base install in `~/.agent-os` first.
