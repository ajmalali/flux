# The agent roster against the utilisation bar — and the end of flux's model-visible surface

**Date:** 2026-08-24
**Bar:** `ecfcffb`'s, verbatim — an always-on injection may cost at most **2,000 tokens
per session-of-use**, where
`cost = tokens injected per session / share of billed sessions with ≥1 invocation`,
and it must fail on **both** denominators (all-corpus, real-interactive) to fire.
**Pre-registration:** `88ce1a8`, committed before any number was read.
**Re-runnable:** `python3 scripts/skill-utilisation.py flux: --agents --since 2026-08-20
--roster-bytes 505`

## Verdict

**FAILS, at zero.** Both flux agents are deleted.

| | value |
|---|---|
| roster cost | **505 B = 126 tok** in every session, every repo |
| billed sessions (all-corpus, since install) | 273 |
| billed sessions (real-interactive) | 89 |
| invocations of `flux:flux-explorer` | **0** |
| invocations of `flux:flux-verifier` | **0** |
| utilisation | **0.00% on both denominators** |
| cost per session-of-use | **undefined — the denominator is zero** |

This is a harder failure than the skill listing's. There, the question was how many
multiples of the bar the listing missed by. Here there is no multiple to quote: nothing
was ever invoked, so no finite cost per session-of-use exists.

**Zero is not "0 since install" — it is 0 across the entire 537-transcript corpus.**
The only `flux:`-prefixed agent calls ever logged are three from 2026-08-11
(`flux:chore`, `flux:build`, `flux:deep`) — v1 agent names, a retired product,
disqualified for exactly the reason v1 skill commands were.

## What the measurement is worth, stated as weakness

The pre-registration required this section, because the numerator here is the kind of
evidence this repo used two days ago to dismiss `claude plugin details`.

**The numerator is not measured. It cannot be.** Transcripts carry 493 `skill_listing`
attachments and **zero** agent equivalents; the string `Available agent types` appears in
no transcript. The roster goes into the system prompt, which is never logged. So the
505 B is one of two things, and this run did both and got the same answer:

- **projected** from `agents/*.md` by reproducing the harness's render — 505 B;
- **read off one live session's rendering** — 505 B, exact agreement, **n=1**.

Agreement between a projection and a single observation is not a corpus. It is worth
more than the projection alone and much less than the skill listing's 493 recorded
renderings. That is the honest ceiling on this figure.

**"Billed" is also a proxy.** Nothing records a session as having *carried* the roster,
so where the skill script could test `bytes > 0` per session, agent mode assumes a
user-scoped plugin bills every session after its install date (`--since 2026-08-20`).
The script now refuses to run agent mode quietly without `--since`.

**The denominator, which is the half that decides this, is solid.** `subagent_type` on
`Task`/`Agent` tool calls is logged verbatim and counted directly. Zero is measured, not
projected — and zero is what fires the bar. The weak numerator only sets *how badly* it
fails, and at a zero denominator that is undefined regardless.

**One correction to publish:** `6c9a8f6` and the previous analysis stated
**473 B = 118 tok**. The real figure is **505 B = 126 tok** — the earlier count omitted
the `flux:` namespace prefix the harness prepends to each name. The direction of the
verdict is unaffected; the number was understated by 7%.

**Not imported from the skill measurement:** its Reading A / Reading B ambiguity. Both
flux agents were listed, so the two readings coincide. The crux that decided the skill
verdict does not arise here.

## The ladder had to be rewritten, and rewriting it is the finding

Every skill retirement in this repo was capability-neutral, because a skill can be
carried and not listed (`disable-model-invocation: true`). **Agents have no such key.**
So `ecfcffb`'s ladder could not be reused, and the respecified one has a property worth
stating plainly:

> **At zero utilisation, trimming and merging are arithmetically incapable of clearing
> the bar.** Any positive cost divided by a zero denominator fails. Shortening the two
> `description:` fields, or merging two agents into one, changes 126 tok to some smaller
> number that still fails by an undefined margin.

Deletion is not the harshest rung on the ladder here. It is **the only rung that
exists**. That was written down in `88ce1a8` before the number was read, which is the
only reason it means anything — the direction was already public (`6c9a8f6` had
published 118 tok and 0 invocations), so the pre-registration bought the *action*, not
the suspense.

**The one assumption that could reopen this:** that no frontmatter key hides an agent
from the roster while keeping it invocable. If such a key exists, "carry but don't list"
returns and the correct action is that, not deletion. Inherited from the previous
session's finding; not independently re-verified here.

## Capability cost — the overlap is substantial, and it is not total

The bar requires enumerating this before acting, and requires reporting a residue as a
loss rather than arguing it away. Both hypotheses registered in `88ce1a8` held up.

**`flux-verifier` vs `flux check` / `flux run --filter` — overlap near-total.** Its
stated job, "so raw build/test output never lands in the main context", is already done
**in code**: `flux check` runs `apply_filter` (`[check].filter`, default `failures`) and
prints one summary line, and `flux run --filter failures -- <cmd>` reuses the same
filters for a scoped run. The CLI does it deterministically, at zero model tokens and
zero round-trip.
**Residue given up (a real loss):** flux-verifier's third rule — *if the failure looks
pre-existing, reproduce on a clean stash and say so, because that changes what the caller
does next.* That is judgment, `flux check` cannot do it, and it is gone.

**`flux-explorer` vs the built-in `Explore` agent — overlap substantial, and the corpus
settles the preference.** In the same 537 transcripts, by the same operator:
`general-purpose` **47** invocations, `Explore` **13**, `flux-explorer` **0**. The
built-in was reached for thirteen times while flux's was never reached for once.
**Residue given up:** flux-explorer pinned `model: haiku, effort: low` — a cost pin the
built-in does not offer — and mandated a `## findings` section of `path:line` bullets.
The `Explore` built-in already promises excerpts over file dumps, so the format rule is
mostly duplicated; the cost pin is not, and is a genuine, small loss.

Net: two real residues, both small, neither worth 126 tok in 273 sessions that used
neither agent once.

## What changed

- `agents/flux-explorer.md`, `agents/flux-verifier.md` deleted; the `agents/` directory
  no longer exists. Plugin **2.9.0**.
- Three skills that routed work to them were rewritten to route to what actually exists:
  `apply` → the built-in `Explore` + `flux check` / `flux run --filter`; `adopt` and
  `plan` → the built-in `Explore`.
- `scripts/skill-utilisation.py` gained `--agents`, which shares the bar and the
  bench/real split but labels its numerator `projected` (or `read off a live session
  (n=1)` under `--roster-bytes`) everywhere it prints it, and warns when run without
  `--since`.
- 153 tests green. The skill byte budget caught the first rewrite of `apply` at 6,169 B
  against a 6,000 B cap and forced it back down — the budget did its job unprompted.

## The line this closes

flux now injects **nothing** the model can see except `prime`.

Zero of fourteen skills are model-visible (`83d5012`). Zero agents exist. The whole
model-visible surface of the plugin is one capped hook with a 2,000-token budget the CLI
refuses to exceed. Every uncapped always-on path flux ever had has now been measured
against the same pre-registered bar, and **every one of them failed** —
`mattpocock` at 6.7x, `flux:review` at zero, the agent roster at zero.

The rule that generalises, and it is stronger than the one the skill measurement left:
**a listing slot is not a default, and neither is an agent.** Both are always-on costs
billed to every session, and both were bought here by inheritance — review was listed
because upstream's frontmatter listed it, and the two agents shipped in Phase 01 because
a plugin scaffold has an `agents/` directory. Neither ever carried a written falsifiable
claim that the model must see the thing. When one was demanded, none survived.

**Stop auditing context now.** Three sessions have been spent on it; the falsifiability
rule applies to measurement machinery too, and this line has no uncapped path left to
measure. The standing build item is the append-only JSONL-in-git state format, which
answers the `.flux/state.toml` conflict problem and is **unbuilt**.
