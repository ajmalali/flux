# flux

Deterministic session machinery for Claude Code. flux does the parts of a working
session that are the same every time — priming, budgeted state, filtered verification,
generated handoffs — as scripts wired to hooks, so the model's context stays small and
stable. Judgment stays in a lean set of user-invoked skills.

One repo is both the plugin and its own marketplace. The CLI is a single stdlib Python
file (≥3.9) with no dependencies and no install step. Everything it puts into model
context has a byte cap it enforces itself.

## Install

Once per machine, inside Claude Code:

    /plugin marketplace add ajmalali/flux
    /plugin install flux@marketplace

Once per repo:

    flux init            # detects Nx / Turbo / npm / cargo / uv, writes .flux/flux.toml
    flux init --scan     # optional first: inventory prior state (PAUL, STATE.md, …), write nothing

`.flux/flux.toml` is the whole per-repo adapter: the gate command, the state budget,
the output filter. Repos without `.flux/` are untouched — every hook is a silent no-op.

## Updating

The plugin is a cached copy pinned to the version it was installed at. It does not
follow this repo on its own:

    claude plugin update flux@marketplace     # then restart Claude Code

The marketplace reads pushed `main` on GitHub, and the update only takes when
`.claude-plugin/plugin.json` carries a higher version than the installed one. Check
with `claude plugin list`. New hooks, commands, and skills reach every adopting repo on
the next session after the restart.

Repos that already have `.flux/` need nothing. The CLI reads old `flux.toml` files as
they are, ignores tables it no longer uses, creates `field-log.md` and `cache/` on first
use, and `flux init` refuses to overwrite an existing adapter unless you pass `--force`,
which rewrites `flux.toml` only and keeps state and field-log intact.

## What runs by itself

| Hook | Command | Does |
|---|---|---|
| SessionStart | `flux prime` | Prints the context pack: branch, phase, position, next, open items, stale-key ages, the last handoff inlined, and the four verbs. ≤2k tokens. |
| UserPromptSubmit | `flux guard` | Past 120 requests, one line nudging you to wrap and `/clear`. Never blocks. |
| SessionEnd | `flux seal` | Flags a substantive session that ended without a wrap; the next prime warns. |

## Commands you type

| Command | Does |
|---|---|
| `flux check` | Run the repo's configured gate; print failures only. The only thing that counts as done. |
| `flux run --filter failures -- <cmd>` | Same filter on one narrow command, for iterating. |
| `flux state set <key> "<value>" …` | Write `phase` / `position` / `next` / `open`. Refuses writes over budget. |
| `flux handoff` | Capped handoff from git status, state, and recent commits. Prime inlines the latest one. |
| `flux log <tag> "…"` | Field note: `pack-miss`, `audit-hit`, or `want`. Feeds the ledger. |
| `flux ledger [--fleet] [--verdict]` | Read the session transcripts on disk and print the targets table per cycle of ten sessions; `--fleet` one row per repo; `--verdict` score each open claim. |
| `flux claim add <feature> <metric> <bar>` | Register the metric a feature must move. Unmoved two cycles means delete it. |

## Skills

All user-invoked, none listed to the model.

| Skill | Use when |
|---|---|
| `/flux:plan` | Work outlives the session, takes an irreversible step, or is still being argued about. |
| `/flux:audit` | A plan touches design, money, auth, data, or hardware. Runs in a subagent. |
| `/flux:apply` | Executing, with or without a plan. Execute, report status honestly, qualify against the spec. |
| `/flux:wrap` | Ending any working session. Verify, reconcile, state, handoff, commit. |
| `/flux:grill` | Sharpening a design by interview before planning. Vendored from mattpocock-skills (MIT). |
| `/flux:adopt` | Bringing a repo with existing project docs into `.flux/`. Once per repo. |

## How to use it

**Orienting in a codebase.** Nothing to run. Open a session and the pack tells you
where things stand and what to do first. If it missed something you needed, say so:

    flux log pack-miss "needed the migration order; not in state"

flux stores state, not knowledge. What the code does lives in CLAUDE.md and the code.

**Small feature or bug fix.** One session, no skills. Say the task back in one line
with the files you expect to touch, then work. Iterate narrow, finish whole, close:

    flux run --filter failures -- <one test file or target>
    flux check
    flux state set position "…" next "…"
    flux handoff
    git commit

Measured twice: planning ahead of well-specified single-session work cost 3x and
delivered the same result. Skip the ceremony here.

**Big feature.** Ceremony attaches at phase boundaries, one phase per session.

1. `/flux:grill` if the design is still soft.
2. `/flux:plan` — one self-contained phase: objective, acceptance criteria, 2–3 tasks,
   boundaries, verification.
3. `/flux:audit` for design-routed or irreversible phases.
4. `/flux:apply` — execute against the plan.
5. `/flux:wrap` — reconcile plan against diff, record deviations, write state, handoff,
   commit.

The next session starts cold from the pack and goes to the next phase. Keep a roadmap
file with one row per phase alongside the plan files; that is the cross-phase spine.

**Every session, regardless.** End with `/flux:wrap` or the four lines above. A
session that ends without a wrap has lost what it learned, and `flux seal` will say so
next time.

## What it measures

Every feature names a ledger metric and lives or dies on it. `flux ledger` mines
transcripts into: context p50, cache-write share, sessions over 150 requests,
re-reads, Bash bytes, calls before first edit, wrap coverage, raw gate vs `flux check`,
est \$/session. Dollar figures are API-equivalent list price on a subscription — a
token proxy, not a bill. `flux ledger --verdict` scores each claim in
`.flux/claims.jsonl` only against cycles newer than the claim.

flux pays where a repo has a heavy resume read or a fan-out test runner. In a repo with
a terse gate and a small state file it measured nothing, and was not installed there.

## Development

    python3 -m unittest discover -s tests     # also wired as `flux check` here

Project docs: `.flux/plans/flux-v2/` (plan, status), `.flux/plans/loop/` (the
self-measurement loop), `.flux/analysis/` (dated field studies). v1, a full Python
orchestration harness, is archived at tag `v1-final` and `.flux/archive/v1/`.
