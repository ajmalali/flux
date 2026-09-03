# 01-flux-ledger — outcome

status: DONE
gate: `flux check` green — 207 tests (was 184; +23 in `tests/test_ledger.py`).
built: `flux ledger [--since DATE] [--fleet] [--json]` in `bin/flux` (`_scan_session`
+ `cmd_ledger` + `_ledger_fleet`), README paragraph, checked-in golden fixture
`tests/fixtures/ledger_golden.jsonl`.

## AC-1 side-by-side — `flux ledger --since 2026-08-20` in rpi-rfm69 (TOTAL row)

| metric | read-out 2026-09-03 | ledger (TOTAL) | delta / note |
|---|---|---|---|
| substantive sessions | 16 | **16** | exact |
| ctx / request p50 | 87k | **87k** | exact (within 5%) |
| sessions > 150 req | 0 | **0** | exact |
| wrap coverage | 11/16 | **11/16** | exact |
| est $ (window) | 193 | **193** | exact |
| tool calls before first edit (med) | 11 | **11** | exact |
| cache-write share | 20% | 22% | +2pt (median of session shares) |
| Bash bytes / session (med) | 18.6k | 21k | read-out took the median over **all 18**
  in-range sessions incl. the 2 void; ledger excludes void/minor per AC-2, so its
  median is over the 16 substantive. Over all-18 the ledger reproduces 18.6k exactly. |
| re-reads / session (med) | 0 | 1 | same cause (0.5 over all-18, rounds to 0) |
| $/session (med) | 6.8 | 7.9 | same cause (6.8 over all-18, exact) |
| gate: flux-check vs raw | 24 / 35 | 16 / 25 | the read-out's 24/35 was an **unsaved
  ad-hoc grep** — it counted cross-repo `grep`/`echo` false positives and
  archsense-backend pytest runs over a wider session set. The ledger counts only
  executed test-runner invocations in-repo. Direction preserved: raw (25) > filtered
  (16), the model bypasses the gate. Not reproducible to the digit; documented. |

Every metric the read-out computed **reproducibly** matches within 5%. The four that
differ all trace to two deliberate, documented choices: (1) void/minor sessions are
excluded from denominators (AC-2), where the read-out's `agg()` took medians over all
size≥5KB sessions; (2) the gate ratio's oracle was a hand grep that was never saved
and included noise this scanner rejects.

## Actual output

```
flux ledger — rpi-rfm69 · since 2026-08-20 · est $ API-equivalent (subscription proxy)
cohort         sess  ctx_p50   cw%  >150  rerd    bash ->edit    wrap  gate r/flx  reads  $/sess   est$
cycle 1          10      90k   20%     0     1     22k     10     8/10    20/11        1     9.7    144
cycle 2·part      6      79k   34%     0     0     18k     13     3/6      5/5         7     6.7     48
TOTAL            16      87k   22%     0     1     21k     11    11/16    25/16        8     7.9    193
16 substantive · 2 voided · 0 minor (<5 req)
```

## AC-3 — `flux ledger --fleet` (from the flux repo)

One row per adopting repo, a `meta-tax` line, budget-clipped (754 bytes < 8 000-byte
state budget), whole run in ~1.5 s over 330 MB of transcripts (AC-3 bar: < 10 s).
Benchmark fixture clones under `.flux-bench/runs/` are excluded; discovery resolves
each repo by the transcript's own `cwd` (the slug-reversal DFS is kept, bounded, and
used only as a fallback — a pathological scratchpad-worktree slug can fan out
combinatorially, so it is capped and gives up rather than hang).

```
flux ledger --fleet · since 2026-08-20 · est $ API-equivalent (subscription proxy)
cohort         sess  ctx_p50   cw%  >150  rerd    bash ->edit    wrap  gate r/flx  reads  $/sess   est$
kiosk             1      43k   38%     0     0      6k      5     0/1      0/0         0     1.5      1
broadcast         2      78k   32%     0     0     10k      8     2/2      0/2         5    12.1     24
rpi-rfm69        16      87k   22%     0     1     21k     11    11/16    25/16        8     7.9    193
flux             27     102k   22%     0     0     73k     14    24/27   116/54        5    15.1    444
radiator-revi…   15     167k   17%     5     0     71k     23     4/15    55/7         9    36.0    706
meta-tax: flux $444 / adopting $925 = 0.48x
```

Fleet reproduces the read-out's shape: rpi hits every target; radiator misses the
three that matter (167k ctx, 5 sessions > 150 req, 4/15 wrapped); flux spends ~half
again what it costs itself vs the repos it serves (meta-tax 0.48x). radiator shows 15
substantive vs the read-out's 13 and flux 27 vs 26 — the read-out's "≥5 req" count
and the ledger's substantive filter draw the line one or two sessions apart.

## AC-4 — non-flux repo

`flux ledger` in a repo without `.flux/` prints one line (`no .flux/ here — nothing to
measure`) and exits 0. Pinned in `test_non_flux_repo_exits_zero_and_says_so`.

## Deviations from the plan

- **Gate ratio not reproduced to the digit** (see AC-1 table). The read-out oracle was
  not reproducible; the plan's own verification asked for the side-by-side "with the
  deltas", which this is. `flux check` in the ledger is `check` + `run` subcommands
  (both are the filtered path); raw-gate excludes commands that merely *mention* a
  runner (grep/echo/sed/…).
- **Denominator choice**: medians are over substantive sessions only (AC-2), which
  moves bash/re-reads/$-per-session off the read-out's all-sessions medians. This is
  the more correct reading of the plan; documented above.
- No change to `flux prime`, the state format, or `bench/` (boundaries respected).
