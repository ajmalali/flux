# flux's own skill listing, measured against the bar it derived

2026-08-23, same day as the mattpocock retirement. `2026-08-23-mattpocock-utilisation-bar.md`
retired an install on a bar taken from `DEFAULT_STATE_BUDGET_TOKENS = 2000`, and closed
by handing the bar back to flux:

> The bar was derived from flux's own budget, so it applies to flux. … **flux's skill
> listing is a separate, uncapped thing** … Today it is cheap by the roster measurement
> (one visible skill, `flux:review`, ~150 tok) and expensive by the estimator (~1,246).
> Which is a real open question … it is now the next thing the bar points at.

This is that measurement. **The bar is not re-derived here and may not be** — it was
pre-registered in `ecfcffb` before any mattpocock number was read, and re-deriving it
now, with flux's own listing in the dock, is exactly the tuning the pre-registration
exists to forbid. It is applied verbatim:

> An always-on skill install may cost at most **2,000 tokens per session in which one
> of its skills is actually invoked**, on both denominators — all-corpus and
> real-interactive. If the denominators disagree, the bar does not fire.

## What flux's listing actually is, measured rather than projected

The previous write-up read the listing off *this session's* roster. Transcripts turn out
to record it directly: an `attachment` of `{"type": "skill_listing", "content": …}`
carrying the rendered block verbatim. So the numerator is not an estimate at all.

- **480** transcripts carry a `skill_listing` attachment; **154** of them list a flux skill.
- In every session since the v2 plugin was installed, flux contributes **exactly one
  line, 436 bytes = 109 tok/session** — `- flux:review: …`. Not a median, not a range:
  436 in all 52 of them.
- That is **3.1%** of a median 12,063-byte (≈3,016 tok) whole-roster listing.
- Before v2 (v1 harness, ≤2026-08-18) flux listed **5** lines, **1,061 B = 265 tok**.

The other 13 skills carry `disable-model-invocation: true` and cost **0**: they appear
in no listing in any of the 520 transcripts.

## Utilisation

Corpus scanned today: **520 transcripts** — 230 bench (`ramp.BENCH_MARKERS`), **290
real-interactive**. Invocations counted both ways a skill can be reached: a `Skill`
tool-use naming `flux:…`, and a user-typed `<command-name>/flux:…`.

| window | transcripts | billed for the listing | ≥1 flux skill invoked | **`flux:review` invoked** |
|---|---:|---:|---:|---:|
| post-install real-interactive | 79 | 52 | **0** | **0** |
| post-install bench | 177 | 52 | 41 | **0** |
| whole corpus, real-interactive | 290 | 100 | 12 | **0** |
| whole corpus, all | 520 | 154 | 54 | **0** |

**`flux:review` has never been invoked. Not once, in 520 transcripts, by the model or
by the user.** It is the only skill flux advertises.

Of the 54 sessions with any flux invocation, **exactly one** invoked a skill that its
own session's listing contained — a v1-era `flux:plan`, back when the listing was five
lines. Every other invocation on record is of a skill the listing did not show:

- **Bench (41 sessions):** `flux:apply`, `flux:audit`, `flux:plan`, `flux:wrap`. All four
  are `disable-model-invocation: true`; fluxbench arms type them as slash commands. The
  listing enabled none of it, and bench sessions invoke flux by construction anyway.
- **Real, v1 era (12 sessions, 11 of them billed, 2026-08-11 → 08-17):** `flux:build`,
  `flux:flux-init`, `flux:show-work`, `flux:pause`, `flux:sync`, `flux:plan`, plus one
  `flux:grilling` — a name that has never existed, i.e. a failed invocation. All but
  `plan` are v1 harness commands that **no longer exist**; the v2 listing is not the
  thing that was used. This window is where the single listed-skill use lives, and it
  is why the whole-corpus Reading B cells below read 1.00%/0.65% rather than zero.
- **Real, since the v2 install: zero.** 79 real-interactive sessions, 52 of them billed
  109 tok, no flux skill invoked in any of them by any path. The two flux **agents**
  (`flux:flux-explorer`, `flux:flux-verifier`) are likewise at 0 real invocations
  post-install.

### The bar has an ambiguity here that it did not have there, and it decides everything

The bar says a listing may cost at most 2,000 tok "per session in which **one of its
skills** is actually invoked". Applied to mattpocock that phrase was unambiguous: all
five skills with recorded use were also listed, so both readings of it coincide and the
write-up never had to choose. flux breaks them apart, because **every flux skill ever
invoked is one the listing does not contain**. So the reading has to be chosen, and it
is being chosen *after* seeing the numbers, which is the weakness in this write-up and
is stated here rather than buried:

- **Reading A — any skill in the namespace.** Credit the listing whenever any
  `flux:` skill is invoked, listed or not.
- **Reading B — the skills it lists.** Credit the listing only when a skill it
  actually showed the model is invoked.

Denominator, on both readings: only sessions that **carried** the listing can have been
billed by it. You cannot be charged in a session where the plugin was not installed.
(This is a third correction to the mattpocock arithmetic; see below.)

| window | reading | billed | used | util | tok per session-of-use | verdict |
|---|---|---:|---:|---:|---:|---|
| post-install, real-interactive | **B** | 52 | 0 | 0% | **undefined (∞)** | **fails** |
| post-install, all-corpus | **B** | 104 | 0 | 0% | **undefined (∞)** | **fails** |
| whole corpus, real-interactive | **B** | 100 | 1 | 1.00% | **18,196** | **fails 9.1x** |
| whole corpus, all-corpus | **B** | 154 | 1 | 0.65% | **23,986** | **fails 12.0x** |
| post-install, real-interactive | A | 52 | 0 | 0% | undefined (∞) | fails |
| post-install, all-corpus | A | 104 | 41 | 39.4% | 276 | **passes** |
| whole corpus, real-interactive | A | 100 | 11 | 11.0% | 1,654 | **passes** |
| whole corpus, all-corpus | A | 154 | 52 | 33.8% | 461 | **passes** |

**Under Reading A the bar does not fire and `flux:review` stays listed** — and not
merely because it passes somewhere: post-install it *fails* real-interactive and
*passes* all-corpus, which trips the pre-registered escape clause verbatim ("if the two
denominators disagree, the bar does not fire and the install stays; a verdict that
depends on which sessions you count is not a verdict"). That is the honest off-ramp and
a reader who takes it should re-list `review`; it is a one-line revert.

**Reading B governs, and the tie-break is quoted from the pre-registration rather than
invented today**, which is the only thing that makes choosing it now defensible:

- *"A budget is a price for a thing, not a number floating free of what it buys."* The
  109 tok buys exactly one thing — the model being shown `flux:review`. It does not buy
  `flux:apply` existing (0 tok, `disable-model-invocation`), the CLI, or the hook. A
  session that typed `/flux:apply` got nothing from the 109 tok, so dividing by it
  measures nothing.
- *Proves too much* — the same test that killed the raw-cost reading. Under Reading A a
  plugin could list fifty dead skills and still pass on one live **unlisted** one, which
  makes a listing unfalsifiable no matter how dead it is. That is precisely the
  exemption the pre-registered section refused to grant.

And under Reading B the escape clause is not merely avoided, it is nowhere near: every
window, every denominator, bench included, all-time included, agrees. Two further facts
make the Reading A cells self-evidently unfit for the numerator they are divided into,
though the argument above does not need them:

- Its post-install all-corpus pass is carried entirely by **41 bench sessions** — `claude
  -p` fluxbench arms *scripted to type* `/flux:plan`, `/flux:apply`. For mattpocock the
  bench corpus was neutral (0 invocations) and all-corpus was strictly the harsher
  denominator; for flux it is self-dealing.
- Its whole-corpus real-interactive pass is carried by **11 v1-era sessions** invoking
  `flux:build`, `flux:show-work`, `flux:pause`, `flux:sync`, `flux:flux-init` — commands
  of a **retired product** that no longer exist. Utilisation of v1 cannot pay for v2's
  listing.

Strip either one and Reading A fails too. The mattpocock listing failed by 6.7x
(corrected below). flux's fails by division by zero.

## The pre-registered escalation, applied

Step 1 is **trim to the skills with ≥1 recorded invocation**. For flux that set is
**empty**, so the trim is: `disable-model-invocation: true` on `review`, exactly as the
other 13 carry. Cost goes 109 → **0 tok/session**; the bar clears. Step 2 (uninstall) is
not reached and would be wrong: what flux sells is the `prime` hook — capped at 2,000,
fires every session, clears by construction — and a CLI on PATH. Neither is a listing.

**The capability cost is zero, and this time that is measured, not argued.** Retiring
mattpocock cost 4 autonomous invocations across 287 sessions. Delisting `flux:review`
costs **0 autonomous invocations across 520 transcripts**. It stays carried and stays
one keystroke away as `/flux:review`.

Two things checked before accepting that, because both could have made non-use benign:

- **Was it substituted?** No. The built-in `/code-review` was invoked in **1**
  real-interactive session ever and **0** since the v2 install. Nobody reviews with a
  review skill here. `flux:review` is not losing to a rival; the capability is dormant.
- **Was it a decision or an oversight?** An oversight. `scripts/sync-vendored.sh` applies
  `hide_skill` to `research` and `writing-for-agents` only; `review` was copied straight
  from upstream, whose frontmatter had no key. Its visibility was inherited from Matt's
  packaging, never chosen. The fix therefore lands in the script as well as the file —
  otherwise the next re-sync silently re-lists it.

## What would reverse this

One recorded invocation of `flux:review` that the model initiated **because it saw the
line**. At 2,000 tok/session-of-use, 109 tok/session buys a listing slot at a utilisation
of 5.45% — roughly one use every 18 sessions. It has had 52 and delivered none.

## Cross-check against `claude plugin details`, which still disagrees

    Skills (14)   Always-on: ~1,246 tok added to every session   (review: ~150)

It bills all 14, including the 13 `disable-model-invocation` ones, so **delisting `review`
will not move this number at all** — the estimator cannot see the key, which is precisely
the finding recorded last time (`plugin-details-overcounts`). Recorded because a reader
running that command sees 1,246 both before and after; the measured listing goes 109 → 0.
If the estimator is ever right, flux's listing costs ~1,246 tok/session at 0% utilisation
and the verdict is not softer but harder.

## Re-runnable, and three corrections to the mattpocock arithmetic

The previous measurement was not reproducible, and its number was wrong. This one ships
as `scripts/skill-utilisation.py <namespace-prefix> [--since YYYY-MM-DD]`, stdlib-only,
printing both readings side by side so the crux above is visible to whoever runs it next
rather than resolved silently. Re-run against the retired install, it corrects the
published figure three times over — each correction found by building the tool, none of
them changing a verdict:

| | real-interactive tok/session-of-use | vs bar |
|---|---:|---|
| as published (`07365f6`) | 21,110 | 10.6x |
| counting **both** invocation paths (`Skill` tool *and* user-typed `<command-name>`) | 12,668 | 6.3x |
| billing only sessions that **carried** the listing (213, not 287) | 12,573 | 6.3x |
| **governing reading — listed skills only** (drops ask-matt, to-spec, to-tickets, wayfinder, implement, handoff: invoked but never listed) | **13,421** | **6.7x** |

The first was a scanner that saw only one of the two ways a skill is reached, and it
cost 6 sessions of `/mattpocock-skills:ask-matt`. The second is the denominator fix
above. The third is Reading B applied consistently — it *raises* mattpocock's number,
which is worth noting: the reading that condemns flux's listing is not one that flatters
this repo's prior decision, it is harsher on both. Nothing else moves; no trim clears at
6.7x either, and ask-matt was already vendored, so the capability ledger is untouched.

## The finding

The mattpocock file's rule was *carrying a skill is nearly free; listing it is not.*
flux passed that rule 13 times out of 14 and failed it on the one skill it never chose —
it inherited the visibility along with the vendored file. **A listing slot is not a
default; it is a claim that the model needs to see the thing, and it should be made
deliberately, per skill, and be falsifiable.** flux's own answer, for every one of its
14 skills, is now no: the session hears about flux exactly once, from `flux prime`, which
is capped, load-bearing every session, and the only always-on context this project ever
budgeted for.

**Left open, same bar, not decided here:** the **agent** roster — `flux:flux-explorer`
and `flux:flux-verifier`, **473 B = 118 tok/session**, uncapped, 0 real invocations since
the install. It is a bigger line than the skill listing was, it is the same category of
uncapped always-on path, and agents have no `disable-model-invocation` equivalent, so the
trim step may not exist for them. Measuring it is a separate task and settling it on the
back of this one would repeat the mistake both these files were written to avoid.
