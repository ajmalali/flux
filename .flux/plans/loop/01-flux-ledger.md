---
phase: 01-flux-ledger
routing: design
status: planned
files:
  - bin/flux                      # cmd_ledger + COMMANDS entry + help text
  - tests/test_ledger.py          # synthetic transcripts; table, void rules, budget
  - README.md                     # one paragraph: what ledger reads, what it prints
---

## objective
`flux ledger` prints, from the Claude Code transcripts on disk, the targets table the
2026-09-03 read-out computed by hand — per repo, per cycle, budgeted — so principle 5
runs from data a session did not have to derive.

## context (do not re-derive)
- Transcripts live at `~/.claude/projects/<slug>/*.jsonl`, where `<slug>` is the repo's
  absolute path with every `/` and `.` replaced by `-` (`/Users/x/Dev/flux` →
  `-Users-x-Dev-flux`). `--fleet` finds every slug whose path exists and carries a
  `.flux/flux.toml`.
- Record types that matter: `assistant` (`message.id`, `message.model`,
  `message.usage.{input_tokens,cache_creation_input_tokens,cache_read_input_tokens,
  output_tokens}`, `message.content[].{type:tool_use,name,id,input}`; one `message.id`
  can span several records — dedupe on it); `user` (string content = prompt; list
  content = `tool_result` blocks keyed by `tool_use_id`, `is_error`); `attachment`
  (`attachment.type == hook_success`, `hookName` starts with `SessionStart`, `content`
  holds the pack); `isSidechain` marks subagent traffic — count it, never mix it into
  main-thread context. Skill invocations appear both as
  `<command-name>/flux:x</command-name>` in a user string and as a `Skill` tool_use
  with `input.skill` — count both.
- The 2026-09-03 analyzer that produced the read-out is the reference
  implementation; its output is the acceptance oracle. Reproduce it inside `bin/flux`,
  do not import it.
- Sessions are the clock: a cycle is ten substantive sessions (≥ 5 main-thread
  requests) across the scanned repos, newest cycle last, partial cycle labelled so.

## acceptance criteria
AC-1 — Given the rpi-rfm69 transcripts as of 2026-09-03, when `flux ledger --since
2026-08-20` runs in that repo, then the table shows 16 substantive sessions, median
context per request within 5% of 87k, 0 sessions > 150 requests, wrap coverage 11/16,
and `flux check` 24 vs raw gate 35.
AC-2 — Given a transcript with a zero-turn session and one whose only request carries
`api_error_status: 429`, when ledger runs, then both are listed as `void`, excluded
from every denominator, and the footer says how many were voided.
AC-3 — Given `--fleet`, when ledger runs from the flux repo, then one row per adopting
repo plus a `meta-tax` line (flux-repo est $ / adopting-repo est $) is printed, and
the whole output is clipped to the state budget (2 000 tokens default) with a
`… N rows elided` marker rather than exceeding it.
AC-4 — Given a repo without `.flux/`, when `flux ledger` runs, then it exits 0 with
one line saying so and reads nothing.

## tasks
### T1 — Add `cmd_ledger` with the session scanner
files: bin/flux
do: implement `_scan_session(path)` returning one dict per transcript — start/end,
model mix, main-thread requests, ctx per request (input+cache_write+cache_read), est $
(opus tier 15/75, sonnet 3/15, haiku 1/5; cache write ×1.25, read ×0.10 — labelled
"API-equivalent"), tool histogram, Bash result bytes, calls before first Edit/Write,
repeated `Read` paths, `flux` subcommand counts (`check|run|state|handoff|prime|init|
--help`), raw-gate count (the configured `[check].command` plus `pytest|npm run
check|pnpm test|astro build`), skill invocations by both paths, whether the pack
fired, whether a `flux state set`/`handoff`/`/flux:wrap` happened (wrapped), void
status (zero requests, or every request errored with a retryable status). Then
`cmd_ledger(args)` groups by cycle and prints the targets-table rows: ctx p50, cache-
write share, sessions > 150, re-reads, Bash bytes, calls-before-first-edit, wrap
coverage, gate ratio, help/skill-file reads, est $/session. Flags: `--since`, `--fleet`,
`--json` (raw rows to stdout, uncapped only under `--json`, documented as such).
verify: `./bin/flux ledger --since 2026-08-20` in `~/Dev/archsense/rpi-rfm69` prints
AC-1's numbers; `./bin/flux ledger` in `/tmp` prints the AC-4 line.
done: AC-1, AC-4 when both commands print as specified.

### T2 — Void rules, budget clip, fleet and meta-tax
files: bin/flux
do: mark void per AC-2 (zero-turn, or all requests with `api_error_status` in
429/5xx/529 — mirror `bench`'s `RETRYABLE_API_STATUSES`); exclude from denominators;
footer line `voided: N`. `--fleet`: discover slugs by walking `~/.claude/projects`,
mapping slug → path (reverse the `/`,`.` → `-` rule by testing candidates against the
filesystem; skip ambiguous), keep those with `.flux/flux.toml`; add `meta-tax` line
when the flux repo is among them (detect by `.claude-plugin/plugin.json` name
`flux`). Run the whole rendered output through the existing `clip()` with the state
budget; append `… N rows elided` when rows are dropped, dropping oldest cycles first.
verify: `./bin/flux ledger --fleet` from this repo prints one row per adopting repo,
a meta-tax line, and never exceeds the budget on today's 330 MB of transcripts in
< 10 s.
done: AC-2, AC-3 when the tests in T3 pass and the fleet run matches.

### T3 — Tests on synthetic transcripts
files: tests/test_ledger.py
do: write a tiny transcript builder (assistant/user/attachment records with the fields
in context above) and pin: dedupe on `message.id`; sidechain excluded from ctx;
both skill paths counted; void detection for zero-turn and 429; wrap detection via
`flux state set` Bash *and* `/flux:wrap` slash *and* `Skill` tool; budget clip with the
elided marker; non-flux repo exits 0 silently; slug ↔ path round-trip for a path with
a dot in it. Add one golden test that runs the scanner over a checked-in 20-record
fixture and compares the full row dict.
verify: `flux check` green; the new file adds ≥ 10 tests.
done: AC-2, AC-3 pinned by tests; AC-1 documented in the test as a manual oracle with
the numbers above (real transcripts are not checked in).

## boundaries
do not change: `flux prime` (no ledger call on the SessionStart path — it must stay
fast and silent); the state format; `bench/` (its report is for benchmark runs, the
ledger is for real sessions — do not merge them).
out of scope: claims and `--verdict` (phase 05); the cycle line in prime (05); any
hook (04); reading the field log (03 creates it, 05 tallies it).

## verification
`flux check` green, plus: run `--fleet` once and paste the table into
`.flux/plans/loop/01-flux-ledger.status.md` next to the read-out's table with the
deltas — that side-by-side is the AC-1 evidence and the phase's `## outcome`.
