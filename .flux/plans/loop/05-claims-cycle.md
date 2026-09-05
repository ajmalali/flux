---
phase: 05-claims-cycle
routing: design
status: done
files:
  - bin/flux                       # cmd_claim; _fleet_scan extraction; ledger --verdict path; prime cycle line; FLUX_LEDGER_ALLOW_TMP bypass; COMMANDS + __doc__
  - .flux/claims.jsonl             # NEW append-only claim store (created by this phase, seeded T4)
  - tests/test_flux_cli.py         # T0 harness (HOME-redirected transcripts, timestamped _transcript); claim add + dedupe warn; verdict moved/unmoved-1/-2 + None/inf; claim-ts eligibility; prime cycle line flux-only + never-blank
  - README.md                      # one paragraph: claims are data, `flux claim add`, `flux ledger --verdict`, the cycle line
---

## objective
Close ADR 0003's loop: make attribution *data*, not a session's memory. After this
phase, every feature's claim lives as a record in `.flux/claims.jsonl`, `flux ledger
--verdict` scores each open claim against the cycles that postdate it (moved / unmoved 1
/ unmoved 2), and `flux prime` in the flux repo prints one line when a cycle has closed
so the next loop session knows to read the verdict, propose, and write the next cycle's
claims before any change lands. Principle 5 stops depending on a session remembering it.

Roadmap row 05, routing **design**. Read-out loop steps 2 (attribute each feature to
its metric) and 4 (one session per cycle, pre-registered). This is the phase whose own
success is ADR 0003's falsifiable claim: *"no feature survives two unmoved cycles
unexamined; meta-tax < 0.5."*

## context (do not re-derive)

- **The claim record (ADR 0003, fixed shape).** `.flux/claims.jsonl`, append-only, one
  JSON object per line — same file mechanics as the state log (`read_log` at
  bin/flux:170 skips any line not starting `{` and any unparseable line; `append_records`
  at bin/flux:242 is the writer pattern). Fields:
  `{"ts","feature","metric","bar","scope","cycles"}`. `ts` = `now_iso()` (UTC ms, the
  "never score against data older than the claim" clock). `feature` = the phase/feature
  slug (e.g. `04-guard`). `metric` = one name from the vocabulary below. `bar` = a
  comparator string (below). `scope` = `repo` (this repo's cycles) | `fleet` (all
  adopting repos pooled) | a repo basename. `cycles` = patience N, default 2 — how many
  consecutive post-claim cycles may miss the bar before the verdict escalates to
  `unmoved 2`. Do **not** reuse the `{ts,k,v}` state-log shape — claims are their own
  record type in their own file; `read_log`'s generic skip-bad-lines loop is reused, its
  `k`-field filter is not (write a claims-specific reader that keeps dicts carrying
  `feature`+`metric`).

- **Metric vocabulary = the ledger aggregate keys + two derived.** `_aggregate`
  (bin/flux:1668) already produces every raw metric a claim can name:
  `ctx_p50`, `cw_share`, `over_cap` (the `>150 req` count — the runaway target),
  `rereads`, `bash_bytes`, `first_edit`, `wrapped`, `raw_gate`, `flux_check`,
  `help_reads`, `dollars`, `per_session`. Two derived metrics the verdict computes on
  top of an aggregate, because the read-out states them as ratios, not raw counts:
  `wrap_coverage = wrapped / sessions` (fleet claim, phase 04) and `meta_tax =
  flux$ / adopting$` (fleet only, ADR 0003 — reuse the exact `_ledger_fleet` computation
  at bin/flux:1849–1852, do not re-derive it a second way). A claim naming any other
  string is a **config error surfaced at `claim add` time**, never a silent pass.
  <!-- audit --> **B4/R2 — `_ledger_fleet` is not a reusable data source and sessions
  carry no repo tag.** `_ledger_fleet(since, as_json)` (bin/flux:1809) builds its repo
  list locally, prints a table, and returns 0 — it exposes no pooled list — and the
  session dict from `_scan_session` (bin/flux:1634) has **no `is_flux`/repo field**, so a
  pooled+sorted fleet list cannot be split flux-vs-adopting for `meta_tax`. Fix: extract a
  shared helper `_fleet_scan(since) -> [(name, path, is_flux, sub_sessions), …]` from the
  loop at bin/flux:1812–1829; `_ledger_fleet` calls it (behaviour unchanged), and the
  verdict calls it for fleet-scoped claims. This extraction is **explicitly permitted**
  (see boundaries) — it is additive, not a redefinition of "substantive"/"cycle".
  <!-- audit --> **B4 — `meta_tax` is NOT a per-cycle-chunk metric.** It cannot be
  `_aggregate(chunk)[…]` because the chunk has no repo identity. Special-case it: over the
  eligible window (fleet sessions after the claim ts), sum flux$ and adopting$ via
  `_fleet_scan` and apply the bar to the single ratio; the `cycles` patience is measured as
  "the window spans ≥ `cycles` × `LEDGER_CYCLE` eligible sessions and still misses". This
  matches how `_ledger_fleet` states meta-tax (one ratio, its own bar) — not the
  per-chunk `moved`/`unmoved N` model the other metrics use. State this divergence in the
  verdict output so it is not read as a bug.
  <!-- audit --> **R3/R4 — None and inf guards.** `_aggregate(chunk)["first_edit"]` is
  `None` for an edit-free chunk (bin/flux:1681) — a claim on `first_edit` over such a
  chunk must **skip** that chunk (no signal), and if every eligible chunk is None →
  `pending`, never `op(None, …)` (TypeError). `meta_tax` with zero adopting spend is `inf`
  (bin/flux:1853) — treat that window as `pending` ("n/a — no adopting spend"), not a miss.

- **`bar` is an explicit operator string, because direction is per-metric.** ctx and
  meta-tax are lower-is-better; wrap coverage is higher-is-better; over_cap and
  help_reads want `==0`. An implicit direction would encode the wrong test for half the
  metrics. Format: `<op><number>`, op ∈ `== != < <= > >=`, number is int or float
  (`==0`, `<75000`, `>=0.8`, `<0.5`). A verdict "meets" the bar when
  `op(metric_value, number)` is true. Parse once into `(op, threshold)`; reject an
  unparseable bar at `claim add` time.

- **Cycles for the verdict — reuse the ledger's own chunking, filtered by claim ts.**
  A `repo`-scoped claim's cycles are this repo's substantive sessions (the
  `sub = [s for s in sessions if s["requests"] >= LEDGER_SUBSTANTIVE_MIN and not
  s["void"]]` filter at bin/flux:1784) chunked by `LEDGER_CYCLE`=10 exactly as
  `cmd_ledger` does at bin/flux:1793. A `fleet`-scoped claim pools every adopting repo's
  `sub` sessions (the `_ledger_fleet` scan at bin/flux:1814–1826), sorts by `start`,
  chunks by 10. **The binding rule:** only sessions with `start` strictly after the
  claim's `ts` are eligible (loop rule: "never score a claim against data older than the
  claim"). Take the eligible sessions, chunk by 10, and evaluate only the **last
  `cycles` complete chunks** (a partial trailing chunk is not a closed cycle and does not
  count toward `unmoved`).
  <!-- audit --> **R1 — `start` and `ts` are different precisions; normalize before
  comparing.** A session's `start` is minute-precision `(first_ts or "")[:16]`
  (bin/flux:1635, e.g. `2026-08-21T09:00`); `now_iso()` is `…:SS.mmmZ` (bin/flux:286).
  Compare both at minute precision: a session is eligible when `start > claim_ts[:16]`.
  Consequence to accept and state: a session in the *exact same wall-clock minute* as the
  claim is excluded — harmless (claims are written at loop-close; sessions accrue after),
  and fixtures space starts by ≥1 minute/day so the ACs are unaffected. Raw full-string
  comparison (unnormalized) would silently drop same-minute-later sessions as a prefix — do
  not do it.

- **Verdict states, per claim:**
  - `pending` — fewer than one complete eligible cycle since the claim: not judged yet.
  - `moved` — the bar is met in the most recent complete eligible cycle.
  - `unmoved 1` — the most recent complete cycle misses the bar, but only one complete
    cycle exists since the claim.
  - `unmoved N` — the bar is missed in the last `min(cycles, available)` consecutive
    complete cycles; `unmoved 2` (at `cycles`=2) is the escalation ADR 0003 watches. A
    claim at `unmoved 2` with no queue item naming it is the ADR's falsification.
  Print one line per claim, budgeted through `_fit_to_budget` (bin/flux:1723) so
  `--verdict` obeys the same state budget the table does. Closed/retired claims (a
  future `flux claim close`) are out of scope here — every claim in the file is open.

- **The prime cycle line — flux repo only, O(1) in the common case, never fails.**
  ADR 0003: "In the flux repo only, `flux prime` adds one line when a cycle has closed."
  The cycle clock is fleet substantive sessions; the only cross-repo source of truth is
  the transcripts, so a fleet scan is unavoidable — but prime must stay hook-safe
  (cannot fail, must not parse tens of MB on every SessionStart). Design:
  1. Gate on `_is_flux_repo(root)` (bin/flux:1715) — the line never appears in an
     adopting repo, matching the ADR.
  2. The **ack** is the newest `ts` in `.flux/claims.jsonl` — the last time the loop
     acted (wrote a cycle's claims). No separate ack marker; claims.jsonl *is* the clock.
  3. "Cycle closed" = count of fleet substantive sessions with `start` after the newest
     claim ts ≥ `LEDGER_CYCLE`. Cache the count in `.flux/cache/cycle.json`
     `{"n","computed_at"}`; recompute (via the fleet scan) only when the cache is absent
     or older than a freshness window (default 6 h, a new `[guard] cycle_refresh_hours`
     key via `_guard_cfg`, bin/flux:351). Every read and the recompute are wrapped so any
     failure yields **no line** (prime's inviolable rule).
  4. When closed, print exactly one line, e.g.:
     `cycle closed — N substantive sessions since <date>; read \`flux ledger --verdict\`, then \`flux claim add …\` before the next change.`
     It rides the existing pack `clip()` at bin/flux:797. When no claims file exists yet
     (first ever run), there is no ack and thus no line — seeding T4 establishes it.
  This lag ("line appears only after the ledger cache is warm") is acceptable: the loop
  session runs `flux ledger` anyway, and the line is a reminder to *close*, not to start.
  <!-- audit --> **A2 (load-bearing) — the block's own try/except is not optional.**
  `_prime_inner` runs under `cmd_prime`'s blanket `except: return 0` (bin/flux:735–738),
  which prints *nothing* on any exception — so an unguarded raise in the cycle-line block
  blanks the **entire pack**, not just the line. The block MUST catch its own exceptions
  and continue to `print(clip(...))`. A test asserts a corrupt `cycle.json` yields a
  *complete* pack (phase/next/footer present), not an empty one.
  <!-- audit --> **B3 — the fleet scan excludes tmp roots, which breaks fleet tests.**
  `_is_adopting_repo` returns False for any path under `_LEDGER_TMP_ROOTS`
  (bin/flux:1500–1505); macOS temp dirs live under `/var/folders`, so a test's fabricated
  fleet repos are invisible to the scan. Add an env-gated bypass **for tests only**:
  `_is_adopting_repo` honours `FLUX_LEDGER_ALLOW_TMP=1` (skip the tmp-root check). This is
  additive, off by default, invisible in production. The `_fleet_scan` helper and the prime
  cycle line both inherit it. (Repo-scoped verdict tests do **not** need this — they hit
  `_ledger_sessions` directly, no adopting check — so AC-2/AC-3 avoid B3 entirely.)

- **Coherence with what already ships.** `guard`/`seal`/key-age (phase 04) all live in
  `bin/flux` under `_guard_cfg`; `cycle_refresh_hours` joins them in the `[guard]` block
  of the init template (bin/flux:670) as another commented-optional key. The `ledger`
  aggregate and fleet scan are reused verbatim — no second definition of "substantive",
  "cycle", or "meta-tax". `flux claim` is a new top-level command: add to `COMMANDS`
  (bin/flux:1866) and to `__doc__` (bin/flux:16). `--verdict` is a new flag parsed in
  `_ledger_scope` (bin/flux:1855), routed inside `cmd_ledger` before the table path.
  <!-- audit --> **B5 — `_ledger_scope` is at bin/flux:1746, NOT 1855** (1855 is inside
  `_ledger_fleet`'s meta-tax print). Parse `--verdict` in `_ledger_scope` at **1746**.
  <!-- audit --> **R6 — pin the verdict branch to the TOP of `cmd_ledger`.** It branches
  `if fleet: return _ledger_fleet(...)` before the config check (bin/flux:1770–1771), so
  there are two table paths. The verdict branch must be the **first** statement after
  arg-parse — before the `if fleet` return and before the config check — or `flux ledger
  --verdict --fleet` silently yields the fleet table.
  <!-- audit --> **A1 — `--verdict` is text-only; it IGNORES `--json`.** Decided now:
  `flux ledger --verdict --json` prints the text verdict (json flag ignored). A test
  asserts this. A JSON verdict form is out of scope — nothing reads it yet.

## acceptance criteria

AC-1 — Given a repo with `.flux/`, when `flux claim add <feature> <metric> <bar>
[--scope S] [--cycles N]` runs, then a well-formed record with a `now_iso()` `ts` is
appended to `.flux/claims.jsonl`; an unknown metric name or an unparseable bar exits
non-zero with a one-line error and appends nothing.

AC-2 — Given a `.flux/claims.jsonl` and **repo-scoped** claims whose eligible cycles are
built by the T0 harness (HOME-redirected transcripts under
`$HOME/.claude/projects/<slug>/`, distinct ordered `start`s), when `flux ledger
--verdict` runs, then it prints one budgeted line per claim with the correct state:
`pending` (no complete post-claim cycle), `moved` (latest cycle meets the bar), `unmoved
1` (one cycle, missed), or `unmoved 2` (last two consecutive cycles missed).

AC-3 — Given a claim whose `ts` postdates some sessions in the fixture, when `--verdict`
runs, then those pre-claim sessions do not contribute to any cycle for that claim (the
"never score against data older than the claim" rule is observable: adding a pre-claim
losing session does not change the verdict).

AC-4 — Given a flux-repo temp tree (`FLUX_LEDGER_ALLOW_TMP=1` so the fleet scan sees the
fixture) with a `claims.jsonl` whose newest `ts` is old enough that ≥10 fleet substantive
sessions have started since, when `flux prime` runs, then the pack contains exactly one
cycle-closed line pointing at `flux ledger --verdict`; given an adopting (non-flux) repo,
or a flux repo with fewer than 10 post-ack sessions, the line is absent.

AC-5 — Given this cycle's shipped features (phases 02/03/04 + ADR 0003), when the phase
lands, then `.flux/claims.jsonl` holds their seeded claims (T4) so the *next* cycle's
`--verdict` has something to score.

<!-- audit --> AC-6 — Given a claim on `first_edit` whose eligible cycles have no edits
(metric = `None`), or a `meta_tax` claim over a window with zero adopting spend (ratio =
`inf`), when `--verdict` runs, then that claim reads `pending`/"n/a" — never a crash and
never counted as a miss.

<!-- audit --> AC-7 — Given a corrupt or unreadable `.flux/cache/cycle.json` in the flux
repo, when `flux prime` runs, then it returns 0 and prints the **complete** pack (header,
state keys, footer) with the cycle line simply omitted — not an empty output. (The
cycle-line block's own try/except, not `cmd_prime`'s blanket catch, must be what handles
the error — see the A2 note in context.)

## tasks

<!-- audit --> **Ordering:** T0 → T1 → T2 → T3 → T4. T0 is a prerequisite the original
plan omitted: there is **no ledger test or fixture in the repo today** (the only helper,
`_transcript` at tests:1050, hardcodes one timestamp and injects via `transcript_path`,
not the ledger's HOME-derived `PROJECTS_DIR`). T2/T3 cannot be verified without it, so it
is scoped as its own task, not folded into a `verify` line.

<!-- audit --> ### T0 — ledger/verdict test harness (prerequisite)
files: tests/test_flux_cli.py
do: Build the fixture infrastructure the verdict tests need. (a) Extend `_transcript`
(tests:1050) with a `ts` param so sessions get **distinct, ordered** starts and enough
bulk to clear the 5 KB floor `_ledger_sessions` enforces (bin/flux:1651) — a session
under 5 KB is skipped, so pad content or request count. (b) Add a helper that plants
transcripts under a **redirected HOME**: run `flux` with `env_extra={"HOME": tmp}` and
write files to `<tmp>/.claude/projects/<slug>/*.jsonl` where `slug = _slug_for_path(repo)`
— this is the *only* way to feed `_ledger_sessions`, whose `PROJECTS_DIR` is HOME-derived
at import (bin/flux:1373). The fixture *directory* varies per run (temp path), so only its
*contents* are deterministic — assert on rendered output, not a checked-in directory. (c)
Confirm `PROJECTS_DIR` actually re-reads HOME in the subprocess (it does: fresh import per
`run_flux` call).
verify: A throwaway test proves the harness works end-to-end: plant 20 timestamped
sessions for the repo's slug under redirected HOME, run `flux ledger`, assert the table
shows 2 cycles. If that passes, T2/T3 have a foundation.
done: `flux ledger` over harness-planted transcripts returns a non-empty, correct table.

### T1 — `flux claim add` + the claims store
files: bin/flux, tests/test_flux_cli.py
do: Add `cmd_claim(args)` dispatching on `args[0]=="add"`. Parse
`add <feature> <metric> <bar>` positional + `--scope repo|fleet|<name>` (default
`repo`) + `--cycles N` (default 2). Validate `metric` against the vocabulary set
(aggregate keys + `wrap_coverage`,`meta_tax`) and `bar` against the `<op><number>`
grammar; on either failure print `flux claim: <reason>` to stderr and return 2 without
writing. On success append `{"ts": now_iso(), "feature","metric","bar","scope","cycles"}`
to `.flux/claims.jsonl` (create dir/file if absent; reuse the `append`-with-`makedirs`
idiom from `append_records`, bin/flux:242). Register `"claim": cmd_claim` in `COMMANDS`
(bin/flux:1866) and add a `claim add` line to `__doc__` (bin/flux:16). Add a
claims-specific reader `read_claims(root)` that reuses `read_log`'s tolerant line loop
but keeps dicts carrying `feature`+`metric`.
<!-- audit --> R5 — no dedupe: the store is append-only and `close`/`list` are out of
scope, so re-running `claim add` for the same `feature`+`metric` appends a second record
and resets that claim's eligibility clock to the newer `ts`. `cmd_claim` must **warn to
stderr** ("claim add: <feature>/<metric> already open — appending supersedes its clock")
when `read_claims` already holds an open match, but still append (append-only integrity).
verify: `python3 bin/flux claim add 04-guard over_cap ==0 --scope fleet` in a temp
`.flux/` repo appends one parseable line with a `ts`; `flux claim add x bogus ==0` and
`flux claim add x over_cap nonsense` each exit 2 and append nothing (assert file byte
count unchanged). New unit tests cover append shape, both rejections, and default
scope/cycles.
done: AC-1 when both tests (append + rejection) pass under `flux check`.

### T2 — `flux ledger --verdict`
files: bin/flux, tests/test_flux_cli.py
do: Parse `--verdict` in `_ledger_scope` (<!-- audit --> **bin/flux:1746, not 1855**;
return it as a 4th value or a flag). In `cmd_ledger`, <!-- audit --> route the verdict
branch as the **first statement after arg-parse — before the `if fleet` return
(bin/flux:1770) and before the config check** (R6) — to `_ledger_verdict(root, since)`.
That function: read claims; for each, gather the scope's substantive sessions (`repo` →
this slug via `_ledger_sessions`; `fleet` → <!-- audit --> the new `_fleet_scan(since)`
helper (R2), pooled + sorted; named → that repo's slug), drop sessions with
<!-- audit --> `start[:16] <= claim_ts[:16]` (R1 minute-normalized), sort by `start`,
chunk by `LEDGER_CYCLE`, keep only complete chunks. Compute the claim's metric per chunk
(raw = `_aggregate(chunk)[metric]`; `wrap_coverage` = `wrapped/sessions`). <!-- audit -->
`meta_tax` is **special-cased, not per-chunk** (B4): over the whole eligible window sum
flux$/adopting$ via `_fleet_scan`'s `is_flux` split and apply the bar once; patience =
window spans ≥ `cycles`×`LEDGER_CYCLE` eligible sessions. <!-- audit --> Guard None
(`first_edit` on an edit-free chunk → skip that chunk; all-None → `pending`) and inf
(`meta_tax`, no adopting spend → `pending`/"n/a") — never `op(None|inf, …)` as a miss
(R3/R4/AC-6). Apply the parsed `(op, threshold)` to the latest complete chunk and the
trailing `cycles` chunks to decide `pending|moved|unmoved K`. Emit one line per claim
(`<feature> <metric> <bar> [scope] — <state> (latest=<value>, N cycles)`), assembled
through `_fit_to_budget` (bin/flux:1723) with a `--verdict` header. No claims file →
print `flux ledger --verdict: no claims yet — \`flux claim add …\``.
verify: <!-- audit --> Using the **T0 harness** with **repo-scoped** claims (avoids the
tmp-exclusion of the fleet path, B3), plant timestamped sessions so a claim resolves to
`moved`, another to `unmoved 1`, another to `unmoved 2`; assert each rendered line. Add a
separate fleet-scoped test under `FLUX_LEDGER_ALLOW_TMP=1` covering `wrap_coverage` and
`meta_tax` (including the zero-adopting-spend `pending`). <!-- audit --> Assert `flux
ledger --verdict --json` prints the **text** verdict (json ignored, A1). A `first_edit`
claim over an edit-free window asserts `pending`, not a crash (AC-6).
done: AC-2/AC-6 when the moved/unmoved-1/unmoved-2 states, the None/inf guards, and the
`--verdict --json` behaviour all assert under `flux check`.

### T3 — claim-ts eligibility + prime cycle line
files: bin/flux, tests/test_flux_cli.py
do: (a) Make the `start > claim.ts` filter in T2 a named, tested boundary — a unit test
adds one *pre-claim* losing session to the fixture and asserts the verdict is unchanged
(AC-3). (b) In `_prime_inner` (bin/flux:740), after the state-key loop and before/near
the footer, add a flux-repo-only cycle line: guard on `_is_flux_repo(root)`; read newest
claim ts via `read_claims`; count fleet substantive sessions started after it, cached in
`.flux/cache/cycle.json` with a `cycle_refresh_hours` freshness window (`_guard_cfg`
default 6); if count ≥ `LEDGER_CYCLE`, append the one cycle-closed line. <!-- audit -->
The fleet count reuses `_fleet_scan` (R2) and honours `FLUX_LEDGER_ALLOW_TMP` (B3).
<!-- audit --> Wrap the block in its **own** try/except (A2) — `cmd_prime`'s blanket
catch (bin/flux:735) would blank the whole pack on an unguarded raise, so the local
handler must let `print(clip(...))` still run. Add the `# cycle_refresh_hours = 6` comment
to the `[guard]` template (bin/flux:670). Also add the `FLUX_LEDGER_ALLOW_TMP` bypass to
`_is_adopting_repo` (bin/flux:1500) — off by default, test-only.
verify: <!-- audit --> A test builds a flux-repo temp tree
(`.claude-plugin/plugin.json` name `flux`), sets `FLUX_LEDGER_ALLOW_TMP=1`, plants a
claims.jsonl with an old newest-ts + ≥10 harness fleet substantive sessions →
`_prime_inner` output contains exactly one cycle line; the same tree as a non-flux repo →
no line; <!-- audit --> a **corrupt `cycle.json` → no line but the FULL pack still prints
and prime returns 0** (AC-7, guards against the blanket-catch trap). Plus the AC-3
pre-claim test (adding one pre-claim losing session leaves the verdict unchanged).
done: AC-3, AC-4, AC-7 when all prime cases + the eligibility test pass under `flux
check`.

### T4 — seed this cycle's claims + README
files: .flux/claims.jsonl, README.md
do: Write the current cycle's real claims into `.flux/claims.jsonl` via `flux claim add`
(so the format is exercised, not hand-authored), one per shipped feature this cycle:
`02-status-diet ctx_p50 <75000 --scope repo`; `03-log help_reads ==0 --scope fleet`;
`04-guard over_cap ==0 --scope fleet`; `04-seal wrap_coverage >=0.8 --scope fleet`;
`00-loop meta_tax <0.5 --scope fleet`. (Phase-04's stale-key-days≤2 is structural, not a
ledger metric — it is verified by the key-age code path, not a claim; note this in the
plan's `open`, do not invent a metric for it.) Then one README paragraph: claims are
data, `flux claim add`, `flux ledger --verdict`, and the flux-repo cycle line.
verify: `flux ledger --verdict` in the flux repo lists all five seeded claims as
`pending` (no complete post-claim cycle yet — correct: they were just written); the file
has five parseable lines; README renders.
done: AC-5 when the five claims are present and `--verdict` lists them as `pending`.

## boundaries
do not change: the `_aggregate` keys, the `LEDGER_CYCLE`/`LEDGER_SUBSTANTIVE_MIN` void
rules, or the *meaning* of the meta-tax ratio — the verdict *consumes* these; a
second definition of "substantive" or "cycle" is the exact drift ADR 0003 forbids.
<!-- audit --> **Explicitly permitted (additive, not redefinitions):** (1) extracting
`_fleet_scan(since)` from `_ledger_fleet`'s loop so both it and the verdict share one
scan (R2/B4) — `_ledger_fleet`'s output must be byte-identical after; a test asserts it.
(2) an env-gated `FLUX_LEDGER_ALLOW_TMP` bypass in `_is_adopting_repo`, off by default
(B3). Neither changes production behaviour.
Do not add `flux claim close|list|edit` — this phase only needs `add` + `--verdict`;
retirement of a claim happens by a queue item + the user, per ADR 0003 ("capability
deletions stay a user decision"). Do not touch guard/seal behaviour (phase 04 is done).
out of scope: auto-proposing add/remove from verdicts (ADR 0003 "not taken: no model
edits skills from metrics"); a JSON form of `--verdict` (text only until something reads
it); making the cycle line fire in adopting repos (flux-repo-only by ADR); scoring the
stale-key-days claim as a ledger metric (structural, not mined).

## verification
`flux check` green (all new unit tests + the T0 harness). Plus what check
cannot see: (1) run `flux ledger --verdict` in the flux repo by hand — five seeded claims
appear as `pending`; (2) confirm the prime cycle line is absent today (newest claim ts is
now, zero post-ack cycles) and would appear once ≥10 fleet substantive sessions postdate
the seed — a behaviour the next cycle observes, recorded in `open` like phases 02/03/04.

## note on falsifiability at apply time
The three verdict *states* are fully falsifiable now against the T0 harness (T2/T3).
What is **not** verifiable at apply — by design, exactly like phases 02–04 — is whether
the seeded claims actually move: that is read next cycle by `flux ledger --verdict` once
≥10 fleet substantive sessions postdate the seed. This phase's own ADR-0003 claim
(*no claim survives two unmoved cycles unexamined; meta-tax < 0.5*) is judged two cycles
out. Record this in `open` at wrap so a cold session does not mistake `pending` for a bug.

## audit — 2026-09-03
verdict: ready with conditions
applied: 5 blocking, 6 recommended (+ 2 AC weaknesses folded, 1 AC-4 sharpened)

conditions (must hold at apply, all now specified in-plan):
- T0 lands first — it is a real prerequisite, not a verify line: the repo has **no ledger
  test or fixture today** and `_transcript` hardcodes one timestamp (B1/B2).
- core verdict tests are **repo-scoped** to sidestep the tmp-root fleet exclusion; the
  fleet path (prime line, wrap_coverage, meta_tax) runs under `FLUX_LEDGER_ALLOW_TMP=1` (B3).
- `_fleet_scan` is extracted and `meta_tax` is special-cased as a window ratio, not a
  per-chunk metric — the session dict has no repo tag (B4/R2).
- `_ledger_scope` is edited at **1746**, not 1855 (B5); the verdict branch sits at the top
  of `cmd_ledger` before `if fleet` (R6); `start`/`ts` compared minute-normalized (R1);
  None/inf guarded (R3/R4); the prime block owns its try/except so a bad cache never blanks
  the pack (A2/AC-7); `claim add` warns on a duplicate open feature+metric (R5);
  `--verdict --json` is text-only (A1).

blocking findings, all applied above (marked `<!-- audit -->`):
- B1 — no ledger fixture/test exists → new task T0.
- B2 — ledger reads HOME-derived PROJECTS_DIR; tests must redirect HOME → T0 harness.
- B3 — `_is_adopting_repo` excludes tmp roots → env-gated bypass; core tests repo-scoped.
- B4 — session dict has no repo tag; `meta_tax` not per-chunk-computable → `_fleet_scan`
  extraction + special-cased window rule for meta_tax.
- B5 — `_ledger_scope` cited at 1855; it is at 1746 → corrected in context + T2.

deferred:
- JSON form of `--verdict` — out of scope this phase (nothing reads it); `--verdict --json`
  simply ignores json, tested. Revisit if a consumer appears.
- `flux claim close|list|edit` and true dedupe/supersede — ADR 0003 keeps claim retirement
  a user+queue decision; T1 only warns on duplicates. Safe: the store is append-only and a
  duplicate is visible in `--verdict`, not silent.
- Behavioural verification that the seeded claims actually move — by design read next cycle
  (phases 02–04 pattern); recorded in `open`.

## outcome — 2026-09-04
shipped:
- `flux claim add <feature> <metric> <bar> [--scope S] [--cycles N]` → append-only
  `.flux/claims.jsonl` (`{ts,feature,metric,bar,scope,cycles}`); rejects unknown metric
  / unparseable bar (exit 2, no write), warns-but-appends on a duplicate open
  feature+metric. `read_claims` reuses read_log's tolerant loop, own record shape.
- `flux ledger --verdict` → one budgeted line per open claim: `pending / moved /
  unmoved N`, scored only over complete cycles whose `start` (minute-normalized) is
  strictly after the claim ts. `_fleet_scan(since)` extracted from `_ledger_fleet`
  (both share it now); `meta_tax` special-cased as a fleet window ratio (flux$/adopt$),
  not per-chunk; None (`first_edit` edit-free) and inf (no adopting spend) → `pending`.
  Verdict is the first branch in `cmd_ledger` (before `if fleet` and the config check);
  `--json` is ignored (text only).
- Flux-repo-only prime cycle line: `.flux/cache/cycle.json` (`cycle_refresh_hours`,
  default 6, keyed on newest-claim ack) counts fleet substantive sessions since the
  newest claim ts; ≥`LEDGER_CYCLE` prints one line pointing at `flux ledger --verdict`.
  The block owns its try/except so a bad cache never blanks the pack.
- `FLUX_LEDGER_ALLOW_TMP=1` bypass in `_is_adopting_repo` (off by default, test-only).
- Five claims seeded (02 ctx_p50<75000 repo · 03 help_reads==0 fleet · 04-guard
  over_cap==0 fleet · 04-seal wrap_coverage>=0.8 fleet · 00-loop meta_tax<0.5 fleet) —
  all read `pending` today (ts=now). README "Claims — attribution as data" paragraph.
- T0 test harness: `_transcript` extended (`ts`/`cwd`/`pad`/`raw_gate`/`wrapped`);
  `LedgerHarness` plants timestamped sessions under a redirected HOME at the git-toplevel
  slug (avoids the macOS `/private` symlink trap). 26 new tests; `flux check` 264 green.
deviated:
- The `_ledger_fleet` "byte-identical after extraction" boundary is guarded
  behaviorally (a test asserts the fleet table still renders both repos + meta-tax),
  not by a byte-for-byte diff against a pre-extraction capture — none exists in-repo and
  the extraction is a pure code move (identical tuple, unchanged render/JSON paths).
- `cycle.json` cache keyed on `ack` (newest claim ts) in addition to the planned
  `{n,computed_at}`, so a newly-added claim invalidates a stale count. Additive.
deferred:
- Whether the five seeded claims actually move is read NEXT cycle by `flux ledger
  --verdict`, once ≥10 fleet substantive sessions postdate the 2026-09-04 seed (phases
  02–04 pattern). `pending` today is correct, not a bug. This phase's own ADR-0003 claim
  (no claim survives two unmoved cycles unexamined; meta-tax < 0.5) is judged two cycles
  out.
- JSON form of `--verdict`, `flux claim close|list|edit`, and auto-proposing add/remove
  from verdicts — all out of scope by ADR 0003 (claim retirement stays a user+queue
  decision). Phase-04's stale-key-days≤2 is structural (key-age code path), not a claim.
