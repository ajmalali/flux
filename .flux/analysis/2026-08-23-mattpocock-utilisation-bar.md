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
