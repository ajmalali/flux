# `zaps/api` before prime — baseline, and a pre-registered prediction

Date: 2026-08-23
Phase: 03 (generalize beyond kiosk)
Re-run with: `./bench/run.py ramp --dirs ~/.claude/projects/-Users-ajmalali-Dev-zaps-api`
Captured **before** `flux init` touched the repo, because the pre-prime corpus cannot
be re-measured later — the CLI's 30-day transcript cleanup ate kiosk's baseline
*during* the kiosk experiment (50 → 46 transcripts mid-run).

## Corpus

19 sessions, **15 reaching an edit**; 4 never edited and are excluded rather than
imputed. Session dates span **2026-06-30 → 2026-08-12**; the newest is 11 days old,
so api has had no session since the plugin existed. All 15 editing sessions are
"before" — the on/after cell is empty by construction.

## The baseline

| | median | p90 |
|---|---:|---:|
| ramp calls before the first edit | 28 | 79 |
| context growth before it (tok) | 49,769 | 144,393 |

Per-session ramp, split by bucket:

| bucket | calls (med) | tokens (med) | tokens (p90) | can prime/an index remove it? |
|---|---:|---:|---:|---|
| frontier | 2 | **1,111** | 7,678 | yes — status, plans, queues, `git log` |
| code | 14 | **16,926** | 25,844 | no — the source about to be changed |
| other | 7 | 941 | 3,466 | no — builds, tests, shell plumbing |
| docs | 0 | 0 | 1,132 | no — CLAUDE.md, ADRs, specs |

Pooled across the ramp: frontier is **9% of calls / 16% of result tokens**; code is
**65% / 73%**.

## api is not kiosk, and this is the point

The kiosk result (6 frontier calls / 15,770 tokens → 1 / 51) was a **PAUL-shaped
win**: a 299 KB `.paul/STATE.md` read whole at 48–60 KB a time. api also runs PAUL,
but its `STATE.md` is **33 KB, not 299 KB**, and the corpus says it is mostly not
read: of 19 transcripts, **2 mention `STATE.md` heavily (48 and 45 hits, both from
Jul 24–25) and 6 mention it exactly once**; the remaining 11 never name it. The
median api session spends **1,111 frontier tokens**, a fourteenth of kiosk's 15,770.

So the honest reading before we install anything: **there is almost nothing here for
`flux prime` to take.** A perfect frontier-removing pack saves an api session a
median of ~1.1k tokens out of a ~50k ramp — 2%.

## Pre-registration (written before `flux init`, so the after-reading cannot drift)

**Prediction:** prime does **not** materially move api's ramp. Expected median
frontier after prime: 1–2 calls, under ~1k tokens — indistinguishable from the 2 /
1,111 baseline, because that is already near the floor.

**What would falsify the generalization claim** (i.e. "the kiosk win transfers"):
nothing here. A null result in api is the *expected* result, and reporting it as a
flux win would be the same defect as ticking a target on missing data. The claim
Phase 03 can actually test is narrower: **prime is cheap and harmless where there is
no frontier to remove** — measured as ramp calls and growth not getting *worse*, and
`flux prime` staying a silent, sub-budget no-op.

**What api is genuinely the right repo to test**, and the one live case left in
ADR 0001: the ramp here is **73% code reads, a median 16,926 tokens per session**.
That is the *declared-files-per-task* idea, whose stated metric is the **code-bucket
ramp** — not the frontier, which is spent. api has the code bucket kiosk's write-up
could only point at. If ADR 0001 is ever revived, it is revived here, on this number.

**Baseline to beat, recorded now:** median code-bucket ramp **14 calls / 16,926
tokens**; p90 **25,844**.

## Caveats kept rather than smoothed

- **n=15**, one repo, and the two `STATE.md`-heavy sessions are the oldest in the
  corpus (Jul 24–25) — the p90 frontier of 7,678 rests on them. As they age out, the
  measured baseline will *fall on its own*, with no intervention. Any after-reading
  taken past ~2026-09-22 is comparing against a different corpus, not against this one.
- api's tree is dirty and carries **four competing context frameworks** — `.paul`
  (1.8 MB), `.carl`, `.gitnexus` (71 MB), plus `AGENTS.md`/`CLAUDE.md`/`CONTEXT.md`
  — and a `bd init` commit at HEAD whose `.beads/` files are deleted-but-uncommitted.
  Adding a fifth is a real cost, and the retirement half of Phase 03 is not optional
  garnish here; it is the part with an argument behind it.

---

## The gate measurement, against the bar set before it — 2026-08-23

`flux check`'s filtered gate was the one flux surface with a plausible unmeasured
claim in api (in kiosk it turns ~950 raw lines into one). The bar was fixed in
`plan.md` **before** the number was looked at: *median > 5,000 tokens of
lint/test/build output per session ⇒ install for `flux check` alone.*

Scanned all 19 api transcripts for Bash calls matching the repo's verification.
No `bench` subcommand was added for this — it is a one-off against a fixed bar, and
a CLI surface that no ledger metric depends on would be the sort of feature this
project deletes. Reproduce with `fluxbench.decay.scan_transcript`, summing
`result_chars` over non-sidechain `Bash` calls whose `arg` matches:

```
\b(npm\s+(run\s+)?(test|lint|build|format)|npx\s+(jest|eslint|tsc|nest\s+build)
 |jest|eslint|tsc\b|nest\s+build|npm\s+run\s+test:e2e)\b
```


| | value |
|---|---:|
| sessions that ran the gate at all | **8 of 19** |
| gate calls per running session | median 10 (max 44) |
| gate output per running session | **median 2,166 tok**, p90 7,023, max 7,023 |
| gate output over all 19 sessions | **median 0**, p90 4,410 |
| total gate output, whole corpus | 21,920 tok |

**Below the bar on both readings — 2,166 against 5,000, and 0 if the eleven sessions
that never ran the gate are counted. api stays clean; flux is not installed.**

### Why the gate is cheap here and expensive in kiosk

api's verification is already quiet: jest and eslint report failures tersely, and no
gate run appears anywhere in the corpus's fifteen largest Bash results. kiosk's
`npx nx run-many -t lint,typecheck,test` fans out across 31 projects / 83 tasks and
emits ~950 lines whether or not anything failed. The filter is worth a lot against a
fan-out runner and almost nothing against a plain `npm test` — the same repo-shaped
story as the frontier, with a different artifact.

### What api's context is actually spent on, recorded but not acted on

Total Bash result volume: **1,192,518 chars / ~298k tokens across 19 sessions**, about
**62.8k chars per session** — near `plan.md`'s ~74k baseline and well over its <25k
target. But the top of that distribution is neither the gate nor the frontier:

- `gh issue view` / `gh issue comment` — four of the fifteen largest results
  (15,267 / 11,303 / 8,733 / 8,411 chars). api's project state lives in **GitHub
  Issues**, not in a file, which is the structural reason its file-frontier is only
  1,111 tokens. These are already classified as frontier by `ramp.FRONTIER_SHELL`,
  and they land *after* the first edit — they are the work, not the orientation.
- **mattpocock skill files read whole out of the plugin cache** — three of the
  fifteen largest (18,719 / 14,013 / 9,724 chars). That is instruction loading, and
  it is the second-largest line item in the repo's Bash volume.

Neither is a `flux prime` problem and neither justifies an install. Recorded here
because the Bash-volume target is real and unmet, and this says where it actually
went — a claim for a later cycle, not this one.

## Conclusion

**flux does not generalize to zaps/api, and the reason is specific rather than a
shrug.** Both of its measurable surfaces are repo-shaped and api has the wrong shape
for both: no bloated state artifact to replace (1,111 tok frontier vs kiosk's 15,770),
and no fan-out gate to filter (2,166 tok vs kiosk's ~950 lines). api's state is in
GitHub Issues and its gate is quiet.

The value of the result is the boundary it draws: **flux is for repos with a heavy
resume read and a noisy gate.** Adoption is a measurement, not a rollout. api keeps
the clean tree it just paid 193 files and 32,927 lines for
(`zaps/api@chore/retire-competing-frameworks`) and gains no fifth framework.
