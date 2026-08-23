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
