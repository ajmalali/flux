# loop — roadmap

Effort: build the self-improving loop (ADR 0003) and land the thirteen actions of the
2026-09-03 field read-out. One phase per session where possible. Each phase carries the
claim it will be judged on; phase 05 turns those claims into records.

Source of every number: `.flux/analysis/2026-09-03-field-readout.md`.

| phase | routing | what | claim (metric → bar) | read-out items |
|---|---|---|---|---|
| **01 flux ledger** | design | `flux ledger [--fleet] [--since] [--verdict]` — transcripts → targets table, budgeted, tested | ledger reproduces the read-out table within 5% on the same transcripts; meta-tax printed | loop step 1, 5 |
| **02 status diet** | mechanical | this repo's `status.md` 106 KB → ≤ 8 KB live state; dated history moves to `.flux/analysis/` | flux-repo ctx p50 94k → < 75k over the next cycle | 8 |
| **03 flux log + footer** | mechanical | `flux log <tag> "…"`; `flux init` writes `field-log.md`; pack footer `gate / subset / close / log` lines (≤ 200 bytes) | `flux --help` + skill-file reads per cycle: 10 → 0; field-log present in every adopting repo | 5, 6 |
| **04 guard + age + seal** | design | `flux guard` on `UserPromptSubmit`; key age in pack; `flux seal` on `SessionEnd` logs `[unwrapped]`, prime warns | sessions > 150 req: 5 → 0 per cycle; wrap coverage printed by ledger; stale-key days-max in pack ≤ 2 | 1, 2, 3 |
| **05 claims + cycle** | design | `.flux/claims.jsonl`, `flux claim add`, `ledger --verdict`, prime's one cycle line in the flux repo | ADR 0003's claim | loop steps 2, 4 |
| **06 handoff inline** | mechanical | prime inlines latest handoff under its own cap; `flux handoff` clips | calls before first edit: 11 → ≤ 8 (rpi-shaped repos) | 4 |
| **07 deletions** *(user decides first)* | mechanical | remove `routing` (key, table, stamp); remove 8 zero-use skills; fold `adopt` into `flux init` output; `flux run` on notice; close kiosk conflict metric | pack −1 line; skills dir 14 → 6; tests still green | 10, 11, 12, 13 |
| 08 optional | design | gate-bypass nudge on `PreToolUse`; session heartbeat | Bash output/session raw 12–19 KB → ≤ 5 KB; measured before rewrite | 7, 9 |

Order rationale: 01 is the sensor everything else is judged by; 02 is cheap and lowers
every later session's cost in this repo; 03–04 are the changes the data asked for
loudest; 05 closes the loop; 06 is the smallest ramp win; 07 waits on the user; 08 is
measure-first.

Rules carried from the read-out, binding on every phase:
- stdlib only, Python ≥ 3.9, single file; every emitted line under a byte cap;
- `flux prime` stays silent and cannot fail in non-flux repos — the guard and seal
  hooks inherit the same rule;
- count both invocation paths; void zero-turn / 429 sessions; never score a claim
  against data older than the claim;
- $ figures are API-equivalent (subscription account) — a token proxy, labelled so.
