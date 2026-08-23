# The mattpocock install, reopened: a utilisation bar

2026-08-23, same day as the duplication null. `2026-08-23-mattpocock-install-cost.md`
closed the queued item on a pre-registered **duplication** bar that failed (113 tok
of real overlap vs the 500 required) and recorded, without acting on it, a different
number: 917 tok/session for 15 model-visible skills invoked in ~1.6% of sessions.
It ended with a condition on reopening:

> If the question is reopened, pre-register the utilisation bar *before* looking
> again — and note that this write-up has already published the number, so a future
> bar cannot honestly be tuned to it.

This is that reopening. **Everything above the `## Measurement` heading was written
and committed before a single fresh number was read** (commit history is the proof;
this file lands in two commits, bar then result).

## The honesty problem, stated plainly

917 and 1.6% are already on the record. Any threshold I now name for
"tokens per session" or "share of sessions" can be checked against them in my head
before I write it down, so naming one proves nothing. The bar has to come from
somewhere that predates the question and has no view on Matt's skills.

## The anchor

`bin/flux`, line 23, written in Phase 01:

```python
DEFAULT_STATE_BUDGET_TOKENS = 2000
```

That is the price flux charges **itself** for a permanent slot in every session's
context — the hard cap on `flux prime`, the pack this whole project exists to emit,
enforced in code because CLAUDE.md forbids an uncapped output path. It is the only
standing, written-down price this repo has ever set on always-on context, and it was
set months before anyone counted a mattpocock skill.

Crucially, flux's 2,000 buys something used in **every** session — prime fires on
SessionStart and is read before anything else happens. So the exchange rate flux
holds itself to is not "2,000 tokens is cheap"; it is:

> **≤ 2,000 tokens for a thing that pays off once per session.**

## The bar

**An always-on skill install may cost at most 2,000 tokens per session in which one
of its skills is actually invoked.**

    cost per session-of-use = (tokens injected per session) / (share of sessions with ≥1 invocation)

Retire if it exceeds 2,000, **on both denominators** — the 439-transcript corpus and
the ~175-session real-interactive corpus the ramp analysis uses. If the two
denominators disagree, the bar does not fire and the install stays; a verdict that
depends on which sessions you count is not a verdict.

## Why the form is a derivation and not a thumb on the scale

This is the one free choice in the bar, so it gets decided here, before the number,
and the losing reading gets named rather than buried.

The competing form is **raw cost**: 917 tok/session against a 2,000 cap, which
passes. It is a real argument and this is why it does not govern:

- flux's cap is not a claim that 2,000 tokens is affordable in the abstract. It is
  what the repo will pay for context that is *load-bearing every time*. A budget is
  a price for a thing, not a number floating free of what it buys.
- A thing that pays off in a small fraction of sessions is not entitled to the same
  absolute budget as a thing that pays off in all of them. It is entitled to that
  fraction of it. That sentence is the entire content of the word **utilisation**,
  and the prior write-up named this a *utilisation* argument for exactly that reason
  — before knowing what a utilisation bar would say.
- The raw-cost reading also proves too much: under it, any install under 2,000
  tokens is unfalsifiable no matter how dead it is, which would exempt the whole
  category from CLAUDE.md's standing rule that an unmoved feature gets deleted.

If a reader thinks the raw reading should have governed, the disagreement is over
this section, not over the arithmetic — which is where a disagreement about a bar
belongs.

## Pre-registered: what "retire" means, and what it may not hide

If the bar fails, the action is **the cheapest change that clears it**, in order:

1. **Trim** — keep only the skills with ≥1 recorded invocation, drop the rest. Costs
   a local fork of the plugin. Recompute the bar on the trimmed install; if it
   clears, stop here.
2. **Uninstall** — if no trim clears the bar.

And the saving may not be reported without its price. Retirement must enumerate the
skills that have been invoked at least once **and** are not already carried by flux,
because those are the capability the context saving is bought with. If that set is
non-empty, retiring without vendoring them is a capability loss and must be reported
as one, not as a clean win.

If the bar clears, the install stays and the line is closed a second time — and
closed for good, because a third bar after two honest nulls is not measurement, it
is shopping for a verdict.

## Measurement

*(written after the section above was committed)*

Corpus re-scanned today: **517 transcripts**, of which 230 are bench/scratchpad
(`flux-bench`, `private-tmp`, `scratchpad` — `ramp.BENCH_MARKERS`) and **287 are
real-interactive**. The prior write-up counted 439/~175; the corpus has grown since.

### Two corrections to the published numbers, both found by measuring again

**1. The listing is 11 skills, not 15.** All 15 model-visible skills are model-visible
by frontmatter, but only 11 appear in this session's actual skill roster; the four
`misc/` ones (`git-guardrails-claude-code`, `migrate-to-shoehorn`,
`scaffold-exercises`, `setup-pre-commit`) are not advertised, and nothing in their
frontmatter explains it. So the real injected cost is **2,649 B = 662 tok/session**,
not 918. The bar is evaluated at both.

**2. Usage attribution had to be tightened, and it moved the count both ways.**
Counting bare slash-command names over-credits: `/code-review` in the `subagents`
project (2 calls) is the **built-in** `code-review`, not Matt's, and one call was
`flux:grilling` — a name that does not exist, a mis-invocation of flux's own copy.
Only invocations that name `mattpocock-skills:` explicitly are counted below. That
also surfaced two skills the prior write-up recorded as never invoked.

| skill | calls | sessions | already carried by flux? |
|---|---:|---:|---|
| grilling | 3 | 3 | yes — `skills/grill/references/grilling.md` |
| writing-for-agents | 2 | 2 | **NO** |
| research | 2 | 2 | **NO** |
| code-review | 2 | 2 | yes — `flux:review` |
| domain-modeling | 1 | 1 | yes — `skills/grill/references/domain-modeling.md` |

Never invoked once, in 517 transcripts: `tdd`, `prototype`, `codebase-design`,
`diagnosing-bugs`, `resolving-merge-conflicts`, `wizard`, and the four unadvertised
`misc/` skills.

**Sessions with ≥1 invocation: 9.** 9/517 = **1.74%** all-corpus; 9/287 = **3.14%**
real-interactive.

### The bar

| tok/session | denominator | share | tok per session-of-use | bar | verdict |
|---:|---|---:|---:|---:|---|
| 662 (11 listed) | real-interactive | 3.14% | **21,110** | 2,000 | **fails** |
| 662 | all-corpus | 1.74% | 38,028 | 2,000 | fails |
| 918 (all 15) | real-interactive | 3.14% | 29,274 | 2,000 | fails |
| 918 | all-corpus | 1.74% | 52,734 | 2,000 | fails |

Every cell fails, and the two denominators agree, which is the condition the bar
required. The most generous reading available — the smaller listing against the
denominator that excludes every bench session — still misses by **10.6x**.

### The pre-registered escalation: trim first

Trimming changes both numerator and denominator, so each is recomputed:

| option | kept | tok/session | sessions of use | tok per session-of-use | verdict |
|---|---|---:|---:|---:|---|
| **T1** all 5 invoked skills | grilling, code-review, domain-modeling, research, writing-for-agents | 326 | 9/287 = 3.14% | **10,382** | fails (5.2x) |
| **T2** only the unvendored invoked | research, writing-for-agents | 103 | 4/287 = 1.39% | **7,388** | fails (3.7x) |

**No trim clears the bar**, so the pre-registered action is uninstall.

### How severe the bar is, stated rather than hidden

At 3.14% utilisation the bar permits 2,000 × 0.0314 = **63 tok/session ≈ 251 B** —
about one skill line of average length. A reader should see that before accepting
the verdict: this bar says that at a ~3% hit rate you may carry roughly one skill,
and that is not a rounding detail, it is the claim. It follows from the derivation
rather than being chosen, which is the whole point of deriving it, but it is a
strong claim and it is the part to argue with.

### Cross-check against `claude plugin details`, which disagrees

The harness ships its own cost estimator, found while executing this decision:

```
$ claude plugin details mattpocock-skills@claude-plugins-official
  Skills (25)   Always-on: ~1,620 tok added to every session
$ claude plugin details flux@flux-market
  Skills (14)   Always-on: ~1,246 tok added to every session
```

It says 1,620, not 662. The gap is that it charges an always-on cost for **all 25**
skills, including the 10 marked `disable-model-invocation: true`, and it does the same
to flux — billing all 14 of flux's skills though 13 are `disable-model-invocation`.

**The direct evidence says the estimator over-counts.** In the session that made this
decision, the model-visible skill roster contains exactly **one** flux skill,
`flux:review` — the only one of the 14 without the key. The other 13 are absent from
context entirely while the estimator bills ~1.1k tokens for them. Matt's 10 dmi:true
skills are likewise absent. So `plugin details` is a **static inventory projection**,
not a measurement of what reaches a session; `disable-model-invocation` is invisible
to it.

Recorded because it cuts both ways and neither reading changes the verdict:

- If the roster measurement is right (662 tok), the bar fails by **10.6x**.
- If the estimator is right (1,620 tok), it fails by **25.8x**.

The estimator's number is used nowhere below, but it is the number a reader running
that command will see, and an analysis that quietly ignored it would look wrong.

## Verdict: retired

**The mattpocock-skills install is uninstalled**, and unlike the two nulls before it
this is an action, not a stand-down. `flux prime`'s own budget — the only price this
repo had already set on a permanent context slot — will not buy a 662-token listing
that pays off in 3% of sessions.

### What it cost, in full, as pre-registered

Two skills had recorded use and were **not** already carried by flux: `research`
(2 calls, in `subagents`) and `writing-for-agents` (2 calls, in this repo). Retiring
without them would have been a context saving bought with a capability loss. So both
are now **vendored** — `scripts/sync-vendored.sh`, same pin (1.2.3 / `2ab9580…`), MIT
attributed — and the dangling `/research` and `/writing-for-agents` references inside
the already-vendored `wayfinder` and `ask-matt` now rewrite to `/flux:research` and
`/flux:writing-for-agents` instead of pointing at a plugin that is gone.

Both ship `disable-model-invocation: true`. **The bar is applied to flux's own copies,
not just to Matt's plugin**: a model-visible pair would cost 103 tok/session at 1.39%
utilisation = 7,388 per session-of-use, which is option T2 above, which failed. Taking
them into flux's listing after retiring them from Matt's would be the bar's verdict
laundered through a different plugin.

The honest ledger:

| | before | after |
|---|---:|---:|
| always-on skill-listing cost | 662 tok/session | **0** |
| (same, by `plugin details`' projection) | ~1,620 tok/session | ~130 tok/session |
| grilling / domain-modeling / code-review | mattpocock | `/flux:grill`, `/flux:review` |
| research / writing-for-agents | mattpocock, model-invocable | `/flux:research`, `/flux:writing-for-agents`, **user-invocable only** |
| never-invoked skills carried | 10 | 0 |

**The one real loss**: `research` and `writing-for-agents` can no longer be reached by
the model on its own initiative — 4 autonomous calls across 287 sessions is what that
costs. They stay a slash command away. Everything else that was ever invoked is
covered; everything not covered was never invoked.

The `disable-model-invocation` choice is what makes the vendoring nearly free, and it
is the one place the two accountings differ on the *outcome* rather than the size:
by the roster measurement the vendored pair costs 0, by `plugin details` it costs
~130 tok/session — which would itself fail the bar (130 / 1.39% = 9,353 per
session-of-use). The roster measurement governs, for the reason given above, but if
the estimator turns out to be right then these two copies should be dropped and the
capability loss reported instead. That is a falsifiable claim about flux's own tree
and it is written here so it can be checked.

**Reversible in one command** if this proves wrong:
`claude plugin install mattpocock-skills@claude-plugins-official`.

### A consequence worth writing down

`scripts/sync-vendored.sh` sources from the plugin cache. Checked after uninstalling:
`~/.claude/plugins/cache/claude-plugins-official/mattpocock-skills/1.2.3` **survives** —
`claude plugin uninstall` removes the install record, not the marketplace cache — so a
re-sync still works today. But that directory is now orphaned: nothing refreshes it and
`claude plugin prune` may take it. A future re-sync should pass a checkout of
claude-plugins-official as `$1`. Noted in `skills/VENDORED.md`. This is the cost of
vendoring from an install you then retire, and it is the last thread tying flux to
Matt's plugin having been present.

## The finding worth keeping

The previous write-up concluded *"vendoring and the install are alternatives, not a
stack."* This one is the proof, executed: the right question was never "retire
mattpocock" but **"which of the two owns these skills, and does the model need to see
them?"** — and those are two questions, not one. Ownership went to flux for everything
with recorded use. Visibility went to nobody, because the bar that retired the plugin
retires the listing slot too.

That generalizes past this decision, and it is the rule to reuse: **carrying a skill
is nearly free; listing it is not.** A skill behind `disable-model-invocation: true`
costs zero tokens until it is called, so the case for *keeping* a capability is almost
never the same as the case for *advertising* it. Installs bundle the two together and
charge for both. Vendoring separates them.

### The question this hands to flux

The bar was derived from flux's own budget, so it applies to flux. `flux prime`'s pack
is capped at 2,000 and fires every session — it clears by construction. **flux's skill
listing is a separate, uncapped thing**, and CLAUDE.md's rule that flux may not add an
uncapped output path never contemplated it. Today it is cheap by the roster
measurement (one visible skill, `flux:review`, ~150 tok) and expensive by the
estimator (~1,246). Which is a real open question, not a rhetorical one, and it is
now the next thing the bar points at. It is left open deliberately rather than settled
here: this session was asked to decide mattpocock, and deciding flux's own listing on
the back of it — with no measurement of flux skill utilisation — would repeat exactly
the mistake this file was written to avoid.

Third bar declined in advance, per the pre-registration: **the mattpocock line is
closed.**
