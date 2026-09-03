---
phase: 03-flux-log
routing: mechanical
status: done
files:
  - bin/flux                       # new `flux log` command; init writes field-log.md; prime footer
  - tests/test_flux_cli.py         # flux log, init field-log.md, prime footer, non-flux silence
---

## objective
Put the four session verbs where the model already looks (the prime pack) and give the
field a durable instrument, so the model stops paying to rediscover the interface.
Three mechanical additions to `bin/flux`, all under the existing byte discipline:
1. a **pack footer** in `prime` — one ≤ 200-byte block naming the verbs `gate / subset /
   close / log`;
2. **`flux log <tag> "…"`** — appends one capped entry to `.flux/field-log.md`;
3. **`flux init` creates `.flux/field-log.md`** so every adopting repo has the instrument
   from day one.

## context (do not re-derive)
- Read-out items this phase lands (`.flux/analysis/2026-09-03-field-readout.md` §5):
  - item 5 — *pack footer with the verbs* → targets `--help` reads (F4) + skill-file
    reads + Bash output.
  - item 6 — *`flux log [audit-hit|pack-miss|want] "…"` and `flux init` creates
    `field-log.md`* → no ledger metric; it **is** the instrument (F10).
- **The claim (roadmap row 03):** `flux --help` + skill-file reads per cycle **10 → 0**;
  field-log present in every adopting repo. Not falsifiable at apply time — the reads
  number is read next cycle by `flux ledger --since 2026-09-03` in this repo. The ledger
  already measures it: `_scan_session` counts `help_reads` (bin/flux:1277, 1356/1370/1379
  — plugin-skill-mark Reads, `flux --help`/`-h` Bash, and `cat`ing a plugin SKILL/.md),
  aggregates it (1440), and `_ledger_row` prints it as the `%6d` column (1458–1469). So
  the phase claim is judged by an existing column, exactly like phase 02's ctx-p50.
- **Where the pack is built:** `_prime_inner` (bin/flux:642) assembles `lines`, then
  `print(clip("\n".join(lines), budget))` (686). The footer is just more lines appended
  before that final `clip`, so it inherits the budget clip for free — the tiny-budget
  test (`test_pack_respects_budget`, 40-byte budget) still holds because the whole pack,
  footer included, is clipped to `budget`. The footer's own ≤ 200-byte cap is a separate,
  stricter guard on the footer string itself, so it never dominates the pack.
- **Header tests are safe:** existing prime tests assert on `out.stdout.splitlines()[0]`
  (the `## flux prime …` header) and on `phase:`/`next:` lines. The footer is appended
  last, so no first-line or mid-pack assertion moves.
- **init's file-creation pattern** already exists: it writes an empty `state.jsonl` when
  absent (bin/flux:600–603), `.gitignore`, and gitattributes. `field-log.md` follows the
  same shape — created only if absent, never clobbering an existing one.
- **Budget convention is binding** (CLAUDE.md): "Anything flux … stores as state has a
  byte cap." `field-log.md` is stored state, so each `flux log` entry's free-text is
  clipped to the state budget before it is written — no uncapped write path. The file
  grows append-only but each line is bounded; prime does **not** inject field-log into
  context in this phase (that is phase 04's seal/warn loop), so there is no per-file
  context cap to enforce here.
- **`flux log` vs `flux state log`:** distinct. `state log` (bin/flux:860, a *sub*command
  of `state`) prints recent state writes; `flux log` is a new *top-level* command that
  writes to the field-log. Named `flux log` verbatim per the read-out. Register it in
  `COMMANDS` (bin/flux:1619) and the module docstring/`--help` (bin/flux:9–19).
- **Tag set:** the read-out names three canonical tags — `audit-hit`, `pack-miss`,
  `want`. Phase 04's seal hook will append a fourth, `unwrapped`. To avoid re-touching
  this command next phase, `flux log` accepts **any single bareword tag** (no
  whitespace), and `--help`/usage lists the canonical three. Rationale recorded in
  `## coherence`.

## acceptance criteria
AC-1 (footer) — Given a flux repo with the default budget, when `flux prime` runs, then
its output ends with a footer block that contains the four verbs `gate`, `subset`,
`close`, and `log`, each next to its command (`flux check`, `flux run … -- <cmd>`,
`flux check && flux state set … && flux handoff`, `flux log <tag> "…"`), and the footer
string on its own encodes to ≤ 200 bytes. In a non-flux repo `flux prime` still prints
nothing (silent no-op preserved).
AC-2 (log) — Given a flux repo, when `flux log pack-miss "prime lacked the gate cmd"`
runs, then `.flux/field-log.md` gains exactly one appended entry carrying an ISO-8601
timestamp, the tag `pack-miss`, and the text; a second `flux log` appends a second entry
without disturbing the first; the free-text is clipped to the state budget; and
`flux log` with a missing tag or missing text prints a usage line to stderr and returns
non-zero without writing.
AC-3 (init) — Given a fresh repo, when `flux init` runs, then `.flux/field-log.md`
exists; when `flux init --force` runs over a repo whose field-log already has entries,
then those entries are preserved (init creates only when absent).
AC-4 (gate) — `flux check` is green (was 207; the new tests raise the count), and the
existing prime/init/state tests still pass unchanged.

## tasks
### T1 — `flux log <tag> "…"` command + field-log writer
files: bin/flux
do: add `cmd_log(args)` and a small `_append_field_log(root, tag, text)` helper.
`cmd_log`: resolve `repo_root()`; require a flux repo (`read_config(root) is None` →
print `usage: flux log <tag> "<text>"  (tags: audit-hit | pack-miss | want)` to stderr,
return 2) — hook-safety in non-flux repos is phase 04's concern, this is a user command;
require `len(args) >= 2` and a non-empty, whitespace-free `args[0]` tag else the same
usage/return 2; join the remaining args as the text, clip it to `state_budget_bytes(cfg)`.
`_append_field_log`: ensure `.flux/` exists, open `field-log.md` in append mode, write
one line `- %s %s  %s\n` % (ISO-8601 minute-stamp, tag, clipped text). Register
`"log": cmd_log` in `COMMANDS`; add the one-liner to the module docstring's command list
and the `flux log …` synopsis block (mirror the `flux state log` style).
verify: `flux log pack-miss "x"` then `flux log want "y"` in a temp flux repo →
`field-log.md` has two lines, newest last, each `- <ts> <tag>  <text>`; `flux log` with
no args and `flux log onlytag` both return 2 and write nothing.
done: AC-2.

### T2 — `flux init` creates `.flux/field-log.md`
files: bin/flux
do: in `cmd_init`, after the state.jsonl block (bin/flux:600–603), create
`.flux/field-log.md` only if absent — `open(path, "a").close()` (empty file; the first
`flux log` supplies content). Do not add a header line the ledger might miscount; keep it
byte-empty like the initial state log. Never overwrite an existing field-log (so `--force`
re-running init keeps prior field entries — `--force` targets flux.toml only).
verify: `flux init` in a fresh repo → `.flux/field-log.md` exists and is empty; seed it
with an entry, run `flux init --force`, entry survives.
done: AC-3.

### T3 — prime pack footer
files: bin/flux
do: define a module-level `PACK_FOOTER` string (and `PACK_FOOTER_BUDGET = 200`) naming the
four verbs on one compact line, e.g.
`verbs — gate: flux check · subset: flux run -- <cmd> · close: flux check && flux state set … && flux handoff · log: flux log <tag> "…"`.
In `_prime_inner`, append `PACK_FOOTER` to `lines` immediately before the final
`print(clip(...))` so it rides the same budget clip. Assert-by-test (not at runtime) that
`len(PACK_FOOTER.encode()) <= PACK_FOOTER_BUDGET`. Do not gate the footer on state being
present — its whole point is to teach the verbs to a cold/fresh session.
verify: `flux prime` in a flux repo ends with the footer and contains all four verb
tokens; footer bytes ≤ 200; non-flux `flux prime` prints nothing; the 40-byte-budget
test still yields ≤ 41 bytes total.
done: AC-1.

### T4 — tests
files: tests/test_flux_cli.py
do: add a `TestLog(FluxRepoCase)` (append once/twice, newest-last ordering, budget clip
of a long text, usage error + no-write on missing tag and on missing text, non-flux repo
→ return 2 and no file); extend `TestInit` with a field-log-created + `--force`-preserves
case; extend `TestPrime` with a footer-present (four verb tokens) + footer-≤-200-bytes +
still-silent-without-flux case. Reuse `run_flux`/`FluxRepoCase.write`.
verify: `python3 -m unittest discover -s tests` green; new count > 207.
done: AC-4.

## boundaries
do not change: the ledger (`cmd_ledger`, `_scan_session`, `_ledger_row`) — it already
counts and prints `help_reads`; this phase only *feeds* that column, it does not touch it.
Do not change any hook wiring, `plan.md`, `state.jsonl`, `status.md`, or the roadmap. Do
not add a `field-log.md` reader to prime — inlining/seal/warn is phase 04/06, not now. Do
not validate the tag against a fixed enum (kept open for phase 04's `unwrapped`). Do not
have `flux log` swallow errors silently — it is a user command; the seal-hook path in a
non-flux repo is phase 04's separate, hook-safe caller.
out of scope: `flux guard`/`flux seal`/key-age (phase 04); handoff inline (phase 06);
removing `routing` or skills (phase 07); the gate-bypass nudge (phase 08); rolling
`field-log.md` into radiator/kiosk (their own `flux init` runs create it — "every
adopting repo" is satisfied by init, not by this repo's apply).

## verification
`flux check` green (new count > 207), plus, in a temp flux repo: `flux prime` ends with
the four-verb footer and the footer encodes ≤ 200 B; `flux log <tag> "…"` twice →
two ordered entries in `.flux/field-log.md`; `flux init` on a fresh repo creates the
field-log; non-flux `flux prime` silent and non-flux `flux log` returns 2. The phase
**claim** — `--help` + skill-file reads 10 → 0 — is not falsifiable at apply time; it is
read next cycle by `flux ledger --since 2026-09-03` in this repo (the `help_reads` column)
and recorded in phase 05. "field-log present in every adopting repo" is satisfied
structurally by init creating it; verify it for *this* repo at apply, and note that
radiator/kiosk pick it up on their next `flux init`. Record both in the phase `## outcome`.

## coherence
Checked against `00-roadmap.md` (this is its phase 03, mechanical; the deliverables —
`flux log <tag> "…"`, `flux init` writes `field-log.md`, pack footer `gate/subset/close/log`
≤ 200 B — and the claim match row 03), against `.flux/analysis/2026-09-03-field-readout.md`
§5 items 5 & 6 (footer verbs and the field-log instrument, both landed), and against
CLAUDE.md's binding conventions: single-file stdlib-only (all three additions are in
`bin/flux`, no deps); byte caps enforced (footer ≤ 200 B guard; each field-log entry
clipped to the state budget — no uncapped path); `flux prime` never fails / never nags in
non-flux repos (footer rides the existing `try/except` + cfg-None no-op, AC-1 guards it);
every feature names its ledger metric (footer → `help_reads`; field-log → it *is* the
instrument, F10). One call made explicit rather than left to apply: `flux log` accepts an
open bareword tag (not a fixed enum) so phase 04's seal can append `unwrapped` without
re-touching the command; the canonical three tags live in the usage string. Second call:
`flux init --force` preserves an existing field-log (only flux.toml is force-rewritten),
because the field-log is accrued field evidence, not a template. No contradiction found.

## outcome — 2026-09-03
shipped: three additions to `bin/flux`, all under the byte discipline —
(1) `flux log <tag> "…"` (new top-level command + `_append_field_log`): appends
`- <iso> <tag>  <text>` to `.flux/field-log.md`, free-text clipped to the state budget,
errors (rc 2, no write) on a non-flux repo, a missing/whitespace tag, or empty text;
(2) `flux init` now creates an empty `.flux/field-log.md` when absent and never clobbers
an existing one (so `--force` preserves accrued entries — verified);
(3) prime pack footer `PACK_FOOTER` (143 B ≤ 200 cap) naming the four verbs
gate/subset/close/log, appended before the final budget `clip` so it inherits the pack
budget. Registered `log` in `COMMANDS` + the module docstring. Tests: +9
(`TestLog`, `TestInitFieldLog`, `TestPackFooter`) — **216 green** (was 207). AC-1..4 met.
deviated: none — coverage lives in three new FluxRepoCase classes rather than threaded
into TestInit/TestPrime, equivalent to the AC wording. Constants read via the existing
`flux_module()` importer.
deferred: the phase **claim** (`--help` + skill-file reads 10 → 0) is not falsifiable at
apply time — read next cycle by `flux ledger --since 2026-09-03` in this repo (the
`help_reads` column) and recorded in phase 05. "field-log present in every adopting repo"
holds structurally: init creates it; radiator/kiosk pick it up on their next `flux init`.
