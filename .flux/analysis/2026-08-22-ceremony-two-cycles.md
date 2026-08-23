# The lifecycle ceremony has had two reporting cycles and moved nothing

Date: 2026-08-22
Ledger rule: `plan.md` principle 5 — *each capability names the ledger metric it
must move; two reporting cycles with no movement ⇒ delete it.*
Runs: `~/.flux-bench/runs/meridian-003`, `~/.flux-bench/runs/meridian-004`

## Cycle 1 — meridian-003 (4 tasks, sonnet)

| arm | delivered | accept | $/task | ctx p50 | sessions |
|---|---|---|---|---|---|
| vanilla | 4/4 | 100% | $1.05 | 58,598 | 1.0 |
| flux (plan→audit→apply→wrap) | 4/4 | 100% | $2.92 | **49,930** | 4.0 |
| flux-lite (prime+apply) | 4/4 | 100% | **$1.05** | 62,047 | 1.0 |
| paul | 1/4 | 31% | $1.92 | 58,456 | 4.0 |

The `flux-lite` arm was written with its own falsifier in the file: *"If
flux-lite beats flux, the ceremony is overhead and plan.md's falsifiability rule
says it goes."* It beat it. But every arm that ran scored **100% acceptance**, so
the run could not have detected a quality difference even if one existed. Cycle 1
measured cost on work vanilla already does perfectly, and nothing else.

## Cycle 2 — meridian-004 (1 task, sonnet), designed to be favourable

`m5` was written for exactly this: a real feature (holds — a slot claimed for
fifteen minutes, then confirmed or evaporating) with three failure modes the
repo's own gate cannot catch. The ticket carries a **false claim about the
code** ("reporting already shares the availability rule, so holds will be skipped
automatically" — it does not; `utilization` filters nothing at all). The rule has
to land in **two places that already disagree**. And a released hold collapses
into `CANCELLED`, so "a hold is never utilisation" forces a decision the naive
path never notices it is making.

| arm | delivered | accept | $/task | ctx p50 | bash out | sessions |
|---|---|---|---|---|---|---|
| vanilla | 1/1 | **27/27** | $1.81 | 73,855 | **10,678** | 1.0 |
| flux | 1/1 | **27/27** | $5.03 | **58,326** | 47,372 | 4.0 |
| flux-lite | 1/1 | **27/27** | **$1.75** | 73,155 | 18,515 | 1.0 |

**All three arms produced the same fix**, down to the line: `if not
booking.is_active: continue`. Vanilla's docstring names the unavailable-vs-used
distinction unprompted. The flux arm's audit *did* catch the false claim, in as
many words —

> "The ticket's attached note claims the utilisation report 'shares the
> availability rule' and will skip holds 'automatically' — it does not: today's
> `utilization` sums every booking's clamped minutes with **no status filter at
> all** … a HOLD-only filter would still let a released hold through."

— and it was worth $0. The single-pass arms reached the same place by reading the
brief carefully.

Session costs make the shape plain: flux's plan $0.94 + audit $1.34 + apply $1.68
+ wrap $1.07. **The apply session alone ($1.68) matched flux-lite ($1.75) and
vanilla ($1.81).** The $3.35 of ceremony bought a slightly cheaper apply and
nothing measurable else.

## The structural finding, which matters more than either run

**fluxbench cannot, by construction, measure what the ceremony is for.**

`bench/README.md` and `verify.py` enforce a fairness rule: acceptance tests may
only bind to symbols the seed already exports or the brief actually states —
"binding to anything else measures whether the arm guessed the task author's
imagination." That rule is right, and it was bought with a real corrupted result
(m2's `refund_cents` signature). But it forces briefs to be **complete**.

A complete brief is precisely the case where planning and auditing have nothing
to recover. Ceremony's claim is about *incomplete* information — a plan whose
premises about the tree are wrong, a phase whose scope was decided three sessions
ago. Writing that into a task means writing a brief that withholds something, and
the harness's own fairness rule reads that as the author cheating.

There is one legal route left: the check constrains *symbols*, not *behaviour*. A
task could ship a terse bug report and pin the correct fix through seed API only,
leaving the invariant discoverable in the code and nowhere else. That is the only
version of this experiment worth running, and it is not what m5 was.

## Verdict

Two cycles, the second deliberately stacked in the ceremony's favour, and the
ledger metric did not move: same delivery, same acceptance, 2.8x and 2.9x the
cost. **Principle 5 fires.**

What the runs do *not* say, and must not be read as saying:

- **The ceremony has one datapoint on real work, and it is positive.** kiosk
  Phase 02 (2026-08-21): the audit returned three blocking findings on a plan
  that looked obviously fine — a pinned SHA that was the parent rather than the
  tip, a "local gate is a superset of CI" claim that was false, and an instruction
  to write something into a PR body that the branch contradicted. That is the
  incomplete-brief case, on a self-authored plan, which is the case meridian
  cannot represent. n=1, unblinded, and the plan's author and auditor were the
  same model.
- **flux's one consistent win is context**, in both cycles: ctx p50 21% below the
  single-session arms (58,326 vs ~73,500 here; 49,930 vs 58,598–62,047 there).
  Whether that is worth 2.9x the money depends on what fails at 74k, which this
  corpus never reaches and this account is underpowered to measure.
