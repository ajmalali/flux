# ADR 0002: state is an append-only log, and git merges it instead of conflicting

Date: 2026-08-24
Status: Accepted and **built** (`bin/flux`, 18 tests). Dogfooded on this repo the same
session — `.flux/state.toml` is gone here, `.flux/state.jsonl` replaces it.
Line: v2. Follows ADR 0001 (suspended).

## Decision

`.flux/state.toml` — rewritten whole on every `flux state set` — becomes
`.flux/state.jsonl`, **one JSON record per key per write**, appended, never rewritten:

    {"ts": "2026-08-24T11:31:07.412Z", "k": "phase", "v": "..."}

`flux init` writes `.flux/.gitattributes` with `state.jsonl merge=union`, so two
branches that appended both keep their records; **`flux state get` resolves the
result by replay (last write wins per key), so git never has to decide.**

Four consequences, each of which is the point rather than a side effect:

1. **`updated` is derived, not stored.** It was one guaranteed-divergent line per
   session on a file every branch rewrote — the conflict, in miniature.
2. **An empty value clears a key.** The rewritten file had no way to remove one
   except by hand-editing it.
3. **`flux state log [N]`** prints recent writes newest-first, capped at 20 records
   and 120 chars of value. The superseded value is still on disk: this is the one
   thing an append-only format buys that a rewritten file cannot.
4. **`flux state compact`** collapses the log to one record per live key, and
   `flux state set` does it automatically past `8 x` the rendered budget (64 KB at
   the 2,000-token default). CLAUDE.md forbids uncapped stored state, and an
   append-only file is uncapped by construction unless something caps it. Compaction
   output is deterministic — same records in, byte-identical file out — so two
   clones that compact independently agree.

**The budget still prices the pack, not the log.** `[state].budget_tokens` is checked
against the *rendered* key/value map, before appending, so an over-budget write leaves
the log exactly as it was. Billing storage instead would have strangled the format on
its first day.

## Context

**The measured problem.** kiosk carries ~100 branch refs. `.flux/state.toml` was
rewritten by every session on every branch, so every merge conflicted on the same five
lines of a file nobody edits by hand. On 2026-08-23 that was settled the cheap way —
`19861ee` untracked it (status.md, kiosk entry) — and the cost was named at the time:
**untracked state does not survive a clone and does not travel between machines.** The
same entry recorded that the append-only format "is still the better long-term answer"
and was unbuilt. This builds it.

**Where the idea comes from, and what was not taken with it.** `bd` (beads) was
investigated on 2026-08-22 and **rejected as a dependency** — a Go binary plus Dolt
breaks the binding "no dependencies, no install step, ever". Two of its ideas were
marked worth stealing regardless; this is the first, implemented in ~120 lines of
stdlib Python. The second (compute `blocked` on read rather than storing it) belongs
to ADR 0001 and stays suspended with it.

## Falsifiable claim and ledger metric

**Claim:** state can be committed in a many-branch repo without generating conflicts.

**Metric:** *merge conflicts touching `.flux/state.*` per reporting cycle* — target
**0**, measured in kiosk, which is the only adopting repo with the branch count to
produce one. The pre-change value is not zero-by-merit but zero-by-avoidance: the file
is untracked there precisely because it conflicted.

**Delete condition, per CLAUDE.md's two-cycle rule:** if after two reporting cycles
`state.jsonl` is *still* untracked in every adopting repo, the format bought nothing
that untracking did not, and it reverts to TOML — the log is one `flux state get` away
from being rendered back.

**The adoption step this needs, and it is not automatic:** kiosk's `.flux/.gitignore`
still names `state.toml`. Migration there must remove that line and commit the log, or
the metric can only ever read 0 for the wrong reason.

## What this does not claim

- **Not conflict-*free*.** `merge=union` removes conflicts on *concurrent appends*.
  A rebase that rewrites history, or a hand-edited log, can still conflict; replay
  survives it (unparseable lines are skipped, never raised — `prime` must render
  whatever is readable).
- **Not a resolution of simultaneous edits.** Two branches setting the same key both
  keep their record and the newer timestamp wins. That is last-write-wins, not merge
  semantics — the losing value is preserved in the log and visible in `flux state log`,
  which is the whole mitigation.
- **Ties are arbitrary.** `ts` carries milliseconds, so a tie needs two branches
  writing the same key in the same millisecond; it falls back to file order, which is
  fixed within a clone and may differ across one. Recorded, not solved.
- **Nothing about context cost.** The pack `prime` renders is byte-identical to what
  the TOML format rendered. This change buys durability across clones, not tokens.

## Migration

One-way, on first write: `flux state set` in a repo with a `state.toml` and no log
seeds the log from it (dropping the stale `updated`), **removes `state.toml`**, and
says so. Leaving it would leave a stale second copy of the one file a human reads to
learn where a project is; its content is in the log, and in git if it was tracked.
Before that first write, `read_state` still renders `state.toml` — every adopting repo
has one, and `prime` must not go blank waiting for a `set`.
