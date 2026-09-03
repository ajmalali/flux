# ADR 0003: flux measures itself — the ledger is a verb, claims are data, judgment stays in a session

Date: 2026-09-03
Status: Accepted, **unbuilt**. Plans under `.flux/plans/loop/`. Line: v2. Follows
ADR 0002 (built) and honours ADR 0001's ruling (the frontier justification is spent).

## Decision

The improvement loop that has run by hand since 2026-08-20 — mine transcripts, compute
the targets table, compare each feature to the metric it named, propose add/remove,
decide, build, measure again — becomes flux's own machinery, split by principle 1:

- **Sense is a verb.** `flux ledger` reads the Claude Code transcripts for the current
  repo (`~/.claude/projects/<slug>/*.jsonl`, or every `.flux` repo with `--fleet`) and
  prints the targets table per cycle, budgeted. Stdlib, deterministic, $0. It is the
  2026-09-03 analyzer moved into `bin/flux` and tested.
- **Attribution is data.** Every feature declares the metric it must move as a record
  in `.flux/claims.jsonl` (append-only, same mechanics as ADR 0002):
  `{"ts", "feature", "metric", "bar", "cycles": 2}`. `flux ledger --verdict` evaluates
  each open claim against the last N cycles and prints *moved / unmoved 1 / unmoved 2*.
  Principle 5 stops depending on a session remembering it.
- **Value is logged live, not mined.** `flux log <audit-hit|pack-miss|want> "…"`
  appends one line to `.flux/field-log.md`; `flux init` creates the file; the pack
  footer names the verb. Transcripts hold activity, never counterfactuals
  (`.flux/analysis/2026-08-25-realwork-preregistration.md`); this is the only channel
  for "what to add".
- **Judgment is one session per cycle, pre-registered.** A cycle closes at ten
  substantive sessions across adopting repos, not on a calendar. In the flux repo only,
  `flux prime` adds one line when a cycle has closed. That session reads the verdict,
  proposes, and **writes the next cycle's claims before any change lands**. Capability
  deletions stay a user decision.
- **The loop polices itself.** The ledger enforces the rules each prior error taught:
  count both invocation paths; void zero-turn and rate-limited sessions instead of
  scoring them; never evaluate a claim against data older than the claim; and report
  the meta-tax — flux-repo spend over adopting-repo spend — as a metric with its own
  bar. In the v2 era that ratio was 415 : 217.

## Context

The 2026-09-03 field read-out (`.flux/analysis/2026-09-03-field-readout.md`) found
that every number needed to run principle 5 was recoverable from transcripts in about
a second of stdlib Python, and that nobody had computed them for two weeks because the
computation lived in a session's head. It also found the value instrument missing in
two of three dogfood repos, `routing` dead for 18 writes without anyone noticing, and
the flux repo spending twice as much on itself as on the work it was measuring. A
loop that depends on a session choosing to run it will not run.

## Not taken

- **No background model calls.** No scheduled agent mines logs; no model edits skills
  from metrics. Goodhart, cost, and the "no auto-fix" line in plan.md's out-of-scope.
- **No SDK, no MCP.** The sensor is a file reader; the sink is stdout under a budget.
- **No calendar cadence.** rpi produced 16 sessions in a week, radiator 13 in two days;
  a week is either too long or too short. Sessions are the clock.

## Falsifiable claim and ledger metric

**Claim:** with the loop built, no feature survives two unmoved cycles unexamined, and
the meta-tax falls below 0.5. **Metric:** `flux ledger --verdict` lists zero claims at
"unmoved 2" without a queue item naming them; fleet meta-tax ratio. **Falsified if**
two cycles after phase 05 ships the verdict names a stale claim nobody acted on, or the
ratio has not moved — then the ledger is one more artifact nobody reads and this ADR
is retired like the execution index before it.
