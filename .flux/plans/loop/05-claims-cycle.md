---
phase: 05-claims-cycle
routing: design
status: planned
files:
  - bin/flux                       # cmd_claim; ledger --verdict path; prime cycle line; COMMANDS + __doc__
  - .flux/claims.jsonl             # NEW append-only claim store (created by this phase, seeded T4)
  - tests/test_flux_cli.py         # claim add append; verdict moved/unmoved-1/unmoved-2; claim-newer-than-data rule; prime cycle line flux-only
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

- **Coherence with what already ships.** `guard`/`seal`/key-age (phase 04) all live in
  `bin/flux` under `_guard_cfg`; `cycle_refresh_hours` joins them in the `[guard]` block
  of the init template (bin/flux:670) as another commented-optional key. The `ledger`
  aggregate and fleet scan are reused verbatim — no second definition of "substantive",
  "cycle", or "meta-tax". `flux claim` is a new top-level command: add to `COMMANDS`
  (bin/flux:1866) and to `__doc__` (bin/flux:16). `--verdict` is a new flag parsed in
  `_ledger_scope` (bin/flux:1855), routed inside `cmd_ledger` before the table path.

## acceptance criteria

AC-1 — Given a repo with `.flux/`, when `flux claim add <feature> <metric> <bar>
[--scope S] [--cycles N]` runs, then a well-formed record with a `now_iso()` `ts` is
appended to `.flux/claims.jsonl`; an unknown metric name or an unparseable bar exits
non-zero with a one-line error and appends nothing.

AC-2 — Given a `.flux/claims.jsonl` with a claim whose eligible cycles are known (via a
checked-in golden transcript fixture), when `flux ledger --verdict` runs, then it prints
one budgeted line per claim with the correct state: `pending` (no complete post-claim
cycle), `moved` (latest cycle meets the bar), `unmoved 1` (one cycle, missed), or
`unmoved 2` (last two consecutive cycles missed).

AC-3 — Given a claim whose `ts` postdates some sessions in the fixture, when `--verdict`
runs, then those pre-claim sessions do not contribute to any cycle for that claim (the
"never score against data older than the claim" rule is observable: adding a pre-claim
losing session does not change the verdict).

AC-4 — Given the flux repo with a `claims.jsonl` whose newest `ts` is old enough that
≥10 fleet substantive sessions have started since, when `flux prime` runs, then the pack
contains exactly one cycle-closed line pointing at `flux ledger --verdict`; given an
adopting (non-flux) repo, or a flux repo with fewer than 10 post-ack sessions, the line
is absent; and prime still cannot fail on any cache/scan error (line simply omitted).

AC-5 — Given this cycle's shipped features (phases 02/03/04 + ADR 0003), when the phase
lands, then `.flux/claims.jsonl` holds their seeded claims (T4) so the *next* cycle's
`--verdict` has something to score.

## tasks

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
verify: `python3 bin/flux claim add 04-guard over_cap ==0 --scope fleet` in a temp
`.flux/` repo appends one parseable line with a `ts`; `flux claim add x bogus ==0` and
`flux claim add x over_cap nonsense` each exit 2 and append nothing (assert file byte
count unchanged). New unit tests cover append shape, both rejections, and default
scope/cycles.
done: AC-1 when both tests (append + rejection) pass under `flux check`.

### T2 — `flux ledger --verdict`
files: bin/flux, tests/test_flux_cli.py
do: Parse `--verdict` in `_ledger_scope` (bin/flux:1855, return it as a 4th value or a
flag). In `cmd_ledger`, when set, branch before the table path to `_ledger_verdict(root,
since)`. That function: read claims; for each, gather the scope's substantive sessions
(`repo` → this slug via `_ledger_sessions`; `fleet` → the `_ledger_fleet` pooled scan;
named → that repo's slug), drop sessions with `start <= claim.ts`, sort by `start`, chunk
by `LEDGER_CYCLE`, keep only complete chunks. Compute the claim's metric per chunk
(raw = `_aggregate(chunk)[metric]`; `wrap_coverage` = `wrapped/sessions`; `meta_tax` =
the fleet ratio, computed once for fleet-scoped claims). Apply the parsed `(op,
threshold)` to the latest chunk and to the trailing `cycles` chunks to decide
`pending|moved|unmoved K`. Emit one line per claim
(`<feature> <metric> <bar> [scope] — <state> (latest=<value>, N cycles)`), assembled
through `_fit_to_budget` (bin/flux:1723) with a `--verdict` header. No claims file →
print `flux ledger --verdict: no claims yet — \`flux claim add …\``.
verify: A checked-in golden fixture (extend the existing ledger fixture) yields
deterministic `moved`, `unmoved 1`, and `unmoved 2` lines for three seeded claims;
snapshot-assert the exact output. `--json` still emits raw rows (verdict is text-only for
now — assert `--verdict --json` documents/ignores json or errors cleanly, pick one and
test it).
done: AC-2 when the three verdict states assert against the fixture under `flux check`.

### T3 — claim-ts eligibility + prime cycle line
files: bin/flux, tests/test_flux_cli.py
do: (a) Make the `start > claim.ts` filter in T2 a named, tested boundary — a unit test
adds one *pre-claim* losing session to the fixture and asserts the verdict is unchanged
(AC-3). (b) In `_prime_inner` (bin/flux:740), after the state-key loop and before/near
the footer, add a flux-repo-only cycle line: guard on `_is_flux_repo(root)`; read newest
claim ts via `read_claims`; count fleet substantive sessions started after it, cached in
`.flux/cache/cycle.json` with a `cycle_refresh_hours` freshness window (`_guard_cfg`
default 6); if count ≥ `LEDGER_CYCLE`, append the one cycle-closed line. Wrap the whole
block so any exception omits the line and never breaks prime. Add the
`# cycle_refresh_hours = 6` comment to the `[guard]` template (bin/flux:670).
verify: A test builds a flux-repo temp tree (`.claude-plugin/plugin.json` name `flux`) +
a claims.jsonl with an old newest-ts + ≥10 fabricated fleet substantive sessions →
`_prime_inner` output contains exactly one cycle line; the same tree as a non-flux repo →
no line; a corrupt `cycle.json` → no line, prime returns 0. Plus the AC-3 pre-claim test.
done: AC-3 and AC-4 when all three prime cases + the eligibility test pass under
`flux check`.

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
rules, or the `_ledger_fleet` meta-tax computation — the verdict *consumes* these; a
second definition of "substantive" or "cycle" is the exact drift ADR 0003 forbids.
Do not add `flux claim close|list|edit` — this phase only needs `add` + `--verdict`;
retirement of a claim happens by a queue item + the user, per ADR 0003 ("capability
deletions stay a user decision"). Do not touch guard/seal behaviour (phase 04 is done).
out of scope: auto-proposing add/remove from verdicts (ADR 0003 "not taken: no model
edits skills from metrics"); a JSON form of `--verdict` (text only until something reads
it); making the cycle line fire in adopting repos (flux-repo-only by ADR); scoring the
stale-key-days claim as a ledger metric (structural, not mined).

## verification
`flux check` green (all new unit tests + the extended golden fixture). Plus what check
cannot see: (1) run `flux ledger --verdict` in the flux repo by hand — five seeded claims
appear as `pending`; (2) confirm the prime cycle line is absent today (newest claim ts is
now, zero post-ack cycles) and would appear once ≥10 fleet substantive sessions postdate
the seed — a behaviour the next cycle observes, recorded in `open` like phases 02/03/04.

## note on falsifiability at apply time
The three verdict *states* are fully falsifiable now against the golden fixture (T2/T3).
What is **not** verifiable at apply — by design, exactly like phases 02–04 — is whether
the seeded claims actually move: that is read next cycle by `flux ledger --verdict` once
≥10 fleet substantive sessions postdate the seed. This phase's own ADR-0003 claim
(*no claim survives two unmoved cycles unexamined; meta-tax < 0.5*) is judged two cycles
out. Record this in `open` at wrap so a cold session does not mistake `pending` for a bug.
