# The mattpocock install: measured, and NOT retired

2026-08-23. Phase 03's last queued item was "retire the mattpocock install".
It is closed as a **pre-registered null**: the bar was written down before any
number was read, and it did not clear.

## The bar, written first

Retire if **both**:

- **(a)** the unvendored skills — the ones flux does not carry a copy of, so
  retirement genuinely loses them — were invoked in **fewer than 5% of sessions**; and
- **(b)** the **duplicated** description text costs **more than 500 tokens** in
  every session.

(b) is the duplication claim, which is the reason the item was queued: flux
vendors six of Matt's skills, so with both plugins installed the same text is
supposed to be injected twice.

## The result

| leg | measured | bar | verdict |
|---|---:|---:|---|
| (a) unvendored skills invoked | **0.5%** of sessions (2 / 439) | < 5% | **clears** |
| (b) duplicated description text | **113 tok/session** (452 B) | > 500 tok | **fails** |

Both had to clear. **The install stays.**

Denominator check, because 439 counts every transcript file including bench and
scratchpad runs: on the ~175-session real-interactive corpus the ramp analysis
uses, it is 2/175 = 1.1% unvendored and 7/175 = 4.0% for any mattpocock skill.
Leg (a) clears on either denominator; nothing hinges on the choice.

## Why (b) failed — the duplication was mostly imaginary

flux vendors wayfinder, to-spec, to-tickets, ask-matt, review and grill. But
**four of those six are not model-visible upstream either**, and flux marks its
lifecycle skills `disable-model-invocation: true`. What actually reaches a
session's skill listing is:

- **15 model-visible mattpocock skills**, 3,669 B ≈ **917 tok/session**
- **1 model-visible flux skill**: `flux:review`

So exactly **one** pair genuinely duplicates — `mattpocock-skills:code-review`
against `flux:review`, 452 B. The other five vendored skills cost nothing in
context while the plugin is installed, because neither copy is injected.

## Usage, in full — 439 transcripts

| skill | calls | sessions | vendored in flux? |
|---|---:|---:|---|
| grilling | 3 | 3 | yes |
| writing-for-agents | 2 | 2 | **no** |
| code-review | 2 | 2 | yes |
| domain-modeling | 1 | 1 | yes |

Everything else — `/tdd`, `/research`, `/prototype`, `/codebase-design`,
`/diagnosing-bugs`, `/wizard`, `/resolving-merge-conflicts` — has **never been
invoked once**. Three of the 15 are Matt's own tooling and could not apply here
(`migrate-to-shoehorn`, `scaffold-exercises`, `git-guardrails-claude-code`).

## The number that tempts a second bar, and is not being used as one

The install costs **917 tok/session** for 15 skills invoked in 1.6% of sessions.
That is a **utilisation** argument, not the duplication argument that was
queued, and it is being recorded rather than acted on — reaching for a fresh
justification the moment the pre-registered one dies is the exact failure mode
ADR 0001 already fell into, and the api line was closed on this same rule.
If the question is reopened, pre-register the utilisation bar *before* looking
again — and note that this write-up has already published the number, so a
future bar cannot honestly be tuned to it.

## The finding worth keeping

**Vendoring and the install are alternatives, not a stack.** flux vendors copies
so that it works when the mattpocock plugin is absent; with it present, the
vendored copies are dead weight that costs nothing. The real question was never
"retire mattpocock" but "which of the two owns these six skills" — and at 113
tok/session of overlap, the measurement says it does not matter enough to
spend a decision on.
