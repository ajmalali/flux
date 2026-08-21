---
phase: 03-adopt
routing: design
status: done
files: [bin/flux, skills/adopt/SKILL.md, tests/test_flux_cli.py, .flux/plans/flux-v2/plan.md, README.md]
---

## objective
Any repo carrying prior project knowledge — PAUL, agent-os, a hand-kept STATE.md or
ROADMAP.md, just a CLAUDE.md — can be adopted into flux in one pass: live state
distilled into the capped pack, history left where it is, and the old framework
retired only on explicit confirmation and only by archiving.

## acceptance criteria

AC-1 — Given a repo containing `.paul/`, when `flux init` runs, then it names the
prior state sources it found and routes to `/flux:adopt`, having read none of them.

AC-2 — Given any repo, when `flux init --scan` runs, then it prints a budget-capped
inventory (label, path, size, biggest files) and writes nothing — whether or not
`.flux/` already exists.

AC-3 — Given a repo with no prior state, when `flux init --scan` runs, then it exits 0
and says so in one line.

AC-4 — Given `/flux:adopt` in a repo with a 299 KB STATE.md, then only live state
reaches the five state keys, the skill says what it dropped and where the original
still lives, and nothing is deleted or moved without explicit confirmation.

AC-5 — Given confirmed retirement, then the framework directory is `git mv`d into
`.flux/archive/<label>/` — never `rm` — and retirement refuses on a dirty tree.

## tasks

### T1 — detect prior state sources in bin/flux
files: bin/flux
do: add `STATE_SOURCE_RULES` (label, markers, note) and `detect_state_sources(root)`
returning every existing marker with size, file count and biggest files. Sort by
bytes. Walk skips `.git`/`node_modules`/`__pycache__` and caps at a file limit.
verify: `flux init --scan` in this repo lists CLAUDE.md and README.md
done: AC-2 when the inventory is accurate and nothing is parsed

### T2 — `flux init --scan` and init's prior-state note
files: bin/flux
do: `--scan` prints the inventory and returns before writing anything, working with
or without `.flux/`. Plain `flux init` appends a found-prior-state line routing to
`/flux:adopt`. Both outputs go through `clip()` at the state budget.
verify: `flux init --scan` in a temp repo with `.paul/`, and in an empty one
done: AC-1, AC-2, AC-3

### T3 — the adopt skill
files: skills/adopt/SKILL.md
do: judgment only — separating live state from history, reading a huge state file from
its ends rather than whole, trusting the tree over the framework's own claims, and the
retirement rules (opt-in, archive not delete, clean tree, adopt-before-retire).
verify: within the 6000-byte skill budget; passes the frontmatter and gate-args tests
done: AC-4, AC-5

### T4 — tests
files: tests/test_flux_cli.py
do: cover detection (dir and file sources, sizes, empty repo), `--scan` writing
nothing, init's routing line, and extend the skill-contract tests to `adopt`.
verify: `flux check`
done: every AC has a test that fails if the behaviour regresses

### T5 — amend the binding plan
files: .flux/plans/flux-v2/plan.md, README.md
do: add `/flux:adopt` to the skill roster and `--scan` to the CLI surface; name the
ledger metric adopt must move.
verify: plan.md no longer contradicts the shipped surface
done: the roster matches reality

## boundaries
do not change: `CHECK_RULES` and check detection · prime's hook-safe silent no-op ·
the five-key state model · the CLI verb list — `--scan` is a flag on `init`, not a new
command.
out of scope: parsing any framework's file *format* in `bin/flux`. The CLI finds and
sizes; the skill reads and judges. A PAUL-specific parser in the CLI would be a
per-project fork of the plugin, which plan.md rules out.

## verification
`flux check` green, plus `flux init --scan` run for real against `zaps/kiosk` (has a
412 KB `.paul/`) and against a repo carrying nothing.

## outcome — 2026-08-20
shipped: `STATE_SOURCE_RULES` + `detect_state_sources()` in `bin/flux` (15 frameworks
and hand-kept formats, every matching marker reported, sorted by size, `.git`/
`node_modules`/`__pycache__` skipped, 2000-file walk cap); `flux init --scan` printing
a budget-capped inventory and writing nothing; a routing line on plain `flux init`;
`skills/adopt/SKILL.md` (4.7 KB); 9 tests. 55 -> 64 green.
deviated: the inventory's "biggest files" hint was written to rank by raw size, which
surfaced a 3 MB JPG as the most important file in kiosk's `.paul/`. Added
`PROSE_SUFFIXES` so the hint ranks prose and falls back to all files — the total size
still counts everything. Caught by running against the real repo, not by a fixture;
locked by `test_assets_do_not_hide_the_prose`.
deferred: nothing from this plan. `/flux:adopt` itself has not been run end-to-end —
kiosk is its first real target, and that is the next queue item.
verification: `flux check` green; `flux init --scan` run for real against kiosk
(7.4 MB `.paul/` + 454 KB `.claude/paul-framework` + CLAUDE.md/AGENTS.md, correctly
ranked and correctly leaving `.cursor/mcp.json` out) and against an empty repo.
