# T4c — gitnexus vs `repowiki map` as the knowledge source

Status: **decided — `repowiki map` stays. ADR 0009 C2 is not superseded.**
Date: 2026-08-18. Supersedes nothing; annotates ADR 0009.

T4b adopted `repowiki map` after a bake-off against a tool that turned out not to work. The
T4c log entry then argued gitnexus was a materially better knowledge source and probably
superseded that choice. This memo is the measurement that argument asked for, plus the
operational findings that came out of trying to wire gitnexus in for real.

The headline: **gitnexus did not beat the ranked file list on the KPI the claim was made
against, and no repo map of either kind demonstrably beat carrying no map at all.**

## 1. Does the symbol map beat the file list in the pack?

Measured, not argued, as the task required.

**Setup.** Target repo: a clone of flux itself at `38bb6d9` (88 tracked files, 1,689 indexed
symbols) — a real repo with real cross-file structure, not the 3-file scratch repo where T4b's
bake-off degenerated. Three hand-written tickets, each requiring the model to locate code
across 2–4 modules it was not told about. One implement stage per run, same model
(`claude-sonnet-5`, effort high), same three gates, same repo reset to the same commit before
every run. The **only** thing that varied is the knowledge section of the context pack:

| variant | section contents |
|---|---|
| `none` | no knowledge section at all — the control T4b never ran |
| `repowiki` | the shipped ranked-file-list slice (ADR 0009 C2 as adopted) |
| `gitnexus` | symbols + execution flows from one `gitnexus query "<ticket brief>"` |

Pack sizes were close enough that the comparison is roughly cost-matched: 2,503 / 4,000 /
4,367 chars for the first ticket.

**Results.** KPI is `exploratory_calls` (Read/Grep/Glob), the M4 exit-benchmark metric.
All nine runs completed with all gates green and no retries.

| ticket | variant | exploratory_calls | turns | wall | output tokens |
|---|---|---|---|---|---|
| map-check | none | 9 | 37 | 167s | 13,659 |
| map-check | repowiki | **7** | **24** | 138s | 11,128 |
| map-check | gitnexus | **7** | **24** | 133s | 10,708 |
| gate-timing | none | **4** | **21** | 111s | 7,073 |
| gate-timing | repowiki | 11 | 37 | 410s | 9,048 |
| gate-timing | gitnexus | 8 | 32 | 244s | 14,604 |
| park-detail | none | 5 | 29 | 206s | 14,915 |
| park-detail | repowiki | **1** | 26 | 148s | 11,640 |
| park-detail | gitnexus | 8 | **17** | 338s | 28,182 |
| **total** | none | **18** | 87 | **483s** | 35,647 |
| **total** | repowiki | 19 | 87 | 696s | 31,816 |
| **total** | gitnexus | 23 | **73** | 716s | 53,494 |

**Reading.** Two findings, in order of how much they should change what flux does:

1. **gitnexus does not beat the file list.** It is *worse* on the KPI in total (23 vs 19), and
   it wins only the turn count, at the cost of the most output tokens and the most wall time.
   The claim T4c was raised on — that the symbol map would materially cut cold exploration —
   is not supported. The pack section it produces *looks* far better than a centrality ranking
   (for `map-check` it named `repomap.py`, `RepoMap`, `cli.py`, `build_parser`, `head_sha` and
   the two existing staleness tests, all with file:line), and it still did not translate into
   less exploration.
2. **Neither map beat carrying no map.** `none` tied `repowiki` on turns, beat both variants
   on wall time, and won one ticket outright. T4b's honest doubt — "no measurement exists that
   it saves any tokens" — is now measured, and the answer is still no.

**The direction disagrees per ticket**, which is the real result: both maps beat `none` on
`map-check`, `none` beat both on `gate-timing`, and `repowiki` produced a near-perfect 1 on
`park-detail` while `gitnexus` produced 8. Between-ticket variance is larger than any
between-variant difference at n=1 per cell. The correct conclusion is **not** "the file list
wins" — it is **"no effect is detectable at this sample size, so nothing here justifies
replacing a working component."**

**Therefore: do not repoint `flux/knowledge/` at gitnexus.** ADR 0009 C2 stands.

**Two honest caveats against this memo's own numbers:**
- n=1 per cell, 3 tickets, one repo, one model. This is enough to refuse a swap; it is not
  enough to conclude a repo map is worthless.
- `gate-timing` turned out to be a partly degenerate ticket: `GateOutcome.duration_ms` already
  existed, so the ticket largely asked for work already done. It still measures *how fast each
  pack lets the model discover that*, and all three variants faced it identically, so the
  comparison stays internally valid — but it was not the test that was intended.

**The question this raises is bigger than T4c and belongs to M1.** Whether the `[repo_map]`
pack section earns its place at all is exactly an A/B question, and the A/B harness is a T5
deliverable (plan.md §5 M1). This measurement should be re-run through it, with repeats, once
that exists. Recorded as the first concrete question for it to answer.

## 2. Adopt `gitnexus check --cycles --json` as a gate?

**Yes, as a documented opt-in — not in `flux init`'s defaults and not in this repo's suite yet.**

Validated end to end through flux's own gate machinery, not just at a shell:
`GateSpec(name="cycles", command=(...)).build().run(root)` returns `passed=True` on a clean
repo and `passed=False` on a two-module circular-import repo, with the cycle listed in
`detail`. Exit status is 0 clean / 1 on cycles, which is the only contract flux's gate layer
cares about. No new flux code.

```toml
[[gates]]
name = "cycles"
command = ["npx", "-y", "gitnexus@1.6.9", "check", "--cycles", "--json", "-r", "."]
```

`-r .` is load-bearing. gitnexus resolves repos from a **machine-global registry**
(`~/.gitnexus/registry.json`) by alias, and with more than one repo indexed, omitting `-r` is a
hard error. `-r <alias>` would make a committed `flux.toml` machine-specific; `-r .` resolves
from the gate's cwd and stays portable.

**Why opt-in rather than a default.** The gate answers about the *indexed* commit, not the
worktree, so it is only meaningful if something keeps the index fresh — and flux does not
manage a gitnexus index (§1 declined to adopt one). Wiring it into `flux init` would impose a
Node + native-binary dependency on every target repo for a check most of them will not need.
A repo that wants it adds the three lines above and runs `gitnexus analyze --skip-agents-md`
in its own hook.

## 3. Does review hydrate from `detect-changes` instead of a raw `git diff`?

**No — the diff stays the required input. The flow overlay is an optional addition.**
This is the answer T5 needs before it designs the review stage, so it is settled here.

`detect-changes` genuinely adds something the diff cannot: which *execution flows* a change
perturbs, and at which step. On a mid-body edit inside `generate()` it named the symbol exactly
right and listed three correctly-identified affected flows. A function rename was caught
cleanly.

But it cannot be the reviewer's ground truth:
- **Attribution slips on short symbols.** A 2-line insertion into `is_stale()` (a 4-line method)
  was attributed to the *next* method, `render`, and `is_stale` itself was never listed. A
  reviewer handed that instead of the diff would review the wrong function.
- **There is no `--json`.** Output is human-readable text only, so flux would be parsing prose
  to build a pack — the opposite of the deterministic hydration design.md §2 Rule 3 requires.
- It needs a fresh index, per §2.

So the stage I/O table is unchanged: review reads the `git diff` of the stage commits. If a repo
has a gitnexus index, an overlay section may be appended *alongside* the diff, never instead of
it, and its symbol attribution is advisory.

## 4. CLI at hydration time, or MCP attached to the stage session?

**CLI, pinned by version.** The original recommendation was right, and the reason is now
stronger than the determinism argument it rested on.

The gitnexus MCP server attached to *this session* is version 1.6.1 and it cannot read the index
the current CLI writes: `Database file version: 42, Current build storage version: 40`. Through
that broken build, `context` raises an uncaught exception — and `query` returns
`{"processes": [], "process_symbols": [], "definitions": []}` **with exit 0**. An MCP surface
binds flux to an ambient npm install that drifts from the index format silently, and a stage
that hydrates from it would get an empty knowledge section that looks like a legitimate answer.

The determinism argument stands unchanged: an MCP query tool is still exploration — better
aimed, but non-deterministic and invisible to `pack_chars`, which breaks design.md §2 Rule 3.

**If gitnexus is ever adopted for hydration**, the shape must keep `hydrate()` a pure read of
files: a `flux index`-time step writes the ticket-scoped context to `.flux/cache/`, and
`hydrate()` reads that file. Shelling out to a machine-global index from inside `hydrate()`
would make packs unreproducible and `flux run --dry-run` a lie.

## 5. Operational findings (recorded so a future spike does not re-pay for them)

- **Pin the version.** `which gitnexus` was 1.6.1 while published latest was 1.6.9; `check` and
  `detect-changes` do not exist at all in 1.6.1. Every finding here used
  `npx -y gitnexus@1.6.9`. Same rule as `[repo_map] command`'s `uvx --from repowiki`.
- **An empty index reports success.** Analyzing a clone whose identity collided with an
  already-registered repo produced `0 nodes | 0 edges | 0 clusters | 0 flows` and **exit 0**
  with a success message. The state was sticky: `rm -rf .gitnexus`, `gitnexus remove`, `-f`,
  and a fresh `--name` all still yielded 0 nodes; only re-cloning recovered it. Not reproducible
  from a clean clone with the identical recipe, so the trigger is the initial identity
  collision. **Any adapter must treat a zero-node index as a hard error at generation time** —
  the same rule `knowledge/repomap.py` already applies to an empty map, and the reason it has it.
- **`analyze` rewrites `CLAUDE.md`/`AGENTS.md` by default.** `--skip-agents-md` was verified to
  leave the file byte-identical. CLAUDE.md is the session bootstrap; this is not optional.
- **Index cost.** `repowiki map` 0.5s cold. `gitnexus analyze` 3.1–5.0s cold and **7.4s after a
  one-line change** — it is not meaningfully incremental. A ~15x increase in `flux index`.
- **Dependency weight.** Node, a native `lbug` binary, ONNX runtime, and a 46MB on-disk index,
  against `repowiki map`'s single `uvx` call. No API key is needed (embeddings are off by
  default), so ADR 0010 is not implicated either way.

## 6. What survives

`src/flux/knowledge/` was built tool-agnostic — cache, git-HEAD staleness, slicing — and none of
that is touched by this decision. The seam did its job in the way that is easy to miss: it made
"should we swap the ranker?" a question that could be *answered with a measurement* instead of
an argument, and the measurement said no. That is the seam paying for itself just as much as a
swap would have been.
