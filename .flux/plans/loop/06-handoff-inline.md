---
phase: 06-handoff-inline
routing: mechanical
status: done
files: [bin/flux, tests/test_flux_cli.py, .flux/flux.toml, .flux/claims.jsonl]
---

## objective
`flux prime` inlines the latest handoff's body into the pack (under its own cap),
and `flux handoff` writes under that same cap — so a cold session reads its handoff
without a first `cat`, and the inlined copy can never blow the pack budget.

## acceptance criteria
AC-1 — Given a repo with at least one `.flux/handoffs/*.md`, when `flux prime` runs,
its output contains a line from the latest handoff's body (e.g. the `## working tree`
heading), not merely `last handoff: <path>`.
AC-2 — Given a handoff file larger than the handoff cap, when `flux handoff` writes,
the written file is ≤ `handoff_budget_bytes`; and when `flux prime` inlines it, the
prime output is ≤ the state budget AND its last line is still `PACK_FOOTER`.
AC-3 — Given no handoff file present (or the read raises), `flux prime` emits no
handoff block, does not error, and still prints the header + footer.

## tasks
### T1 — cap the handoff, clip `flux handoff` to it
files: bin/flux, .flux/flux.toml
do: add `DEFAULT_HANDOFF_BUDGET_TOKENS = 1200` (≈4800 B, the ~1200-token cap named in
field-readout item 4) and a `handoff_budget_bytes(cfg)` helper mirroring
`state_budget_bytes` but reading optional `[state] handoff_budget_tokens` (default
1200). In `cmd_handoff`, change the final `clip(..., budget)` to clip to
`handoff_budget_bytes(cfg)` instead of the state budget. Add the `handoff_budget_tokens`
knob as a commented line under `[state]` in .flux/flux.toml (documentation only; default
holds when absent).
verify: unit test — write state whose `position` alone exceeds 4800 B, run `flux
handoff`, assert the written file's byte length ≤ 4800.
done: AC-2 (handoff side) when the written file is capped.

### T2 — prime inlines the latest handoff, footer protected
files: bin/flux
do: in `_prime_inner`, replace the current `last handoff: <path>` line with an inlined
block: read the latest handoff, `clip` its body to `handoff_budget_bytes(cfg)`, and
append it under a one-line source marker `last handoff (<basename>), inlined:`. Keep the
existing blanket try/except behaviour: if the read raises or returns empty, fall back to
the old `last handoff: <path>` naming line (AC-3). To guarantee the footer survives the
final budget clip regardless of handoff size, assemble the pre-footer body, clip it to
`budget - len(PACK_FOOTER.encode()) - 1`, then append `PACK_FOOTER` last (do NOT clip the
whole string after the footer is appended). Leave the `_append_cycle_line` call and its
ordering unchanged — it stays before the footer.
verify: unit test — seed a handoff, run `flux prime`, assert output contains `## working
tree` and the output's last line equals `PACK_FOOTER`; second test with an oversized
handoff asserts total output ≤ state budget and last line still `PACK_FOOTER`.
done: AC-1 and AC-2 (prime side) when both tests pass.

### T3 — tests green, seed the phase claim
files: tests/test_flux_cli.py, .flux/claims.jsonl
do: land the T1/T2 tests plus an AC-3 test (no handoffs dir → prime prints header+footer,
no handoff block, exit 0). Then seed this phase's falsifiable claim:
`flux claim add 06-handoff-inline first_edit "<=8" --scope fleet --cycles 2` (roadmap row
06: calls before first edit 11 → ≤ 8; `first_edit` is already an allowed claim metric and
ledger aggregate).
verify: `flux check` green; `flux ledger --verdict` lists `06-handoff-inline` as
`pending` (judged 2 cycles out, like the other five seeded claims).
done: AC-1..3 verified and the claim recorded.

## boundaries
do not change: the state budget (2000 tokens) or `state_budget_bytes`; the guard, seal,
key-age, or cycle-line behaviour; the handoff file's *sections/format* — only its clip
cap moves. Tempting but out: stripping the state-key lines that the inlined handoff
duplicates against prime's own `phase/position/next/…` — field-readout item 4 asks for
the whole handoff inlined; the ~200 B overlap is cheaper than a tool round-trip and
coupling prime to handoff's internal layout.
out of scope: phase 07 deletions (routing key, zero-use skills, `adopt` fold-in); any
change to what `flux handoff` *collects*.

## verification
`flux check` green, plus: run `flux prime` in this repo by hand and confirm the pack now
carries the inlined `## working tree` / `## recent commits` block from the latest handoff
and still ends with the `gate / subset / close / log` footer, with total bytes visibly
under the 8000-byte budget.

## outcome — 2026-09-06
shipped: `handoff_budget_bytes(cfg)` + `DEFAULT_HANDOFF_BUDGET_TOKENS = 1200` (optional
`[state] handoff_budget_tokens` knob, documented commented in .flux/flux.toml); `flux
handoff` clips to the handoff cap, not the state budget (AC-2 write side). `_prime_inner`
inlines the latest handoff under `last handoff (<basename>), inlined:`, body clipped to the
handoff cap, blanket try/except falling back to the old naming line on read-error/empty
(AC-3). Footer protected by reserving its bytes before the final body clip, then appended
last (AC-1 + AC-2 prime side). 5 new tests; replaced stale `test_prime_points_at_latest_handoff`.
267 green. Claim seeded `06-handoff-inline first_edit <=8 [fleet, cycles=2]` → reads pending.
deviated: added a degenerate-case guard the plan didn't name — when the budget is smaller
than PACK_FOOTER itself (only the artificial 10-token `test_pack_respects_budget`), the
footer-reserve subtraction goes negative and would overrun the cap, breaking the binding
budget invariant; guarded with `if budget > footer+1` (always true at the real 8000 B
budget) else fall back to a whole-string clip so budget always wins. Also dropped the
now-dead `budget = state_budget_bytes(cfg)` local in `cmd_handoff`.
deferred: nothing from this phase. Phase 07 deletions (routing key, zero-use skills,
`adopt` fold-in) and phase 08 remain, as scoped out.
