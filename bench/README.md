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
| `flux` | plan → audit → apply → wrap | flux as plan.md prescribes it |
| `flux-lite` | apply | flux's machinery without the ceremony — the control *within* flux |
| `paul` | plan → audit → apply → verify | the incumbent flux was distilled from |
| `speckit` | specify → plan → tasks → implement | GitHub Spec Kit |
| `agentos` | inject → implement | Agent OS v3's standards layer (see caveat) |

`flux-lite` exists to keep flux honest against itself. It separates two claims
that are easy to conflate: what the deterministic machinery (prime, budgeted
state, filtered check) is worth, and what the four-session lifecycle costs on top
of it. If `flux-lite` beats `flux`, plan.md's falsifiability rule says the
ceremony goes.

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

## Why every task ships a reference implementation

`run.py verify` asserts two things per task, cumulatively, in order:

- **red** — the acceptance tests fail on the tree the arm receives. Otherwise they
  measure nothing.
- **green** — they pass once the task's `reference/` is applied, and the repo gate
  still passes. Otherwise the brief is ambiguous and every arm loses points for the
  task author's writing.

This is not hypothetical. The first smoke run had both arms fail the same
acceptance test on a boundary the brief never pinned down (`max_length=9` against a
9-character slug). `verify` is what stops that reaching a real run, and it runs as
part of this repo's own gate.

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
