# Field read-out — flux v2 on real work, 2026-08-20 → 2026-09-03

Source: every Claude Code transcript under `~/.claude/projects/` for the repos that
carry a `.flux/` (kiosk, rpi-rfm69, broadcast, radiator-revivers-landing-page), the
flux repo itself, and zaps/api + pre-adoption kiosk as controls. Analyzer:
scratchpad `analyze.py` / `pass2.py` (session-level usage, tool mix, flux CLI calls,
skill invocations, pack-vs-first-action, state-key age). Dollar figures are
**API-equivalent at Opus list price** — the account is a subscription, so they are a
token proxy, not a bill. Requested by the user on 2026-09-03; the broadcast
pre-registration said not to read its logs until close — it contributed 2 sessions.

## 1. What ran

| repo | sessions (≥5 req) | est $ | $/session (med) | ctx/request p50 (med of sessions) | sessions >150 req | wrapped | flux CLI calls | lifecycle skill uses |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| rpi-rfm69 | 16 | 193 | 6.8 | 87k | 0 | 11/16 | 50 | plan 6 · audit 4 · apply 5 · wrap 8 · grill 1 |
| radiator | 13 | 645 | 30 | 170k (primed: 191k) | **5** | **3/13** | 24 | grill 1 |
| broadcast | 2 | 24 | 12 | 78k | 0 | 2/2 | 6 | grill · plan · apply |
| kiosk (post-adopt) | 0 real | — | — | — | — | — | 0 | — |
| flux itself (v2 era) | 26 | 415 | 12.8 | 94k | 0 | — | 158 | — |
| *kiosk pre-v2 (control)* | 38 | 2125 | 33 | 192k | 12 | — | — | — |
| *api (control)* | 12 | 504 | 14 | 94k | 3 | — | — | — |

flux spent more on itself ($415) than on rpi-rfm69 + broadcast together ($217).

## 2. Targets table, measured

| metric | baseline | target | rpi-rfm69 | radiator | broadcast |
|---|---|---|---|---|---|
| median context / request | 148k | < 80k | 87k | 170–191k | 78k |
| cache-write share of spend | 29% | < 15% | 20% | 17% | 32% |
| sessions > 150 requests | 19 | 0 | 0 | **5** ($487 of $645) | 0 |
| redundant re-reads / session | 3.4 | < 1 | 0 | 0 | 0 |
| Bash output / session | 74k chars | < 25k | 18.6k | 30k | 10k |
| $ / completed phase | $45 | < $25 | ~$26 (range 11–44) | n/a | $24 |
| tool calls before first edit (med) | 20 (kiosk) | — | **11** | 21 primed / 26 unprimed | — |

rpi-rfm69 is the shape flux was built for and it hit or grazed every target. radiator
is the shape it was not (a design-critique loop on a 1M-context model) and it missed
the three that matter. Cache-write share moved nowhere in any repo.

## 3. Findings

**F1 — the /clear + prime loop is the real mechanism, and it only works after a wrap.**
The user cleared context 15× in rpi and 10× in radiator and typed "continue" / "what's
next"; every primed session's first calls were `cat` the handoff → read the plan the
pack named (15/15 in rpi). Where wrap had run, first edit came after 11 calls vs 20 in
kiosk-before. Where it had not, the pack lied: radiator's `next` read *"Decide the two
homepage defects in status.md, then launch prep"* for **six consecutive sessions**
while the work was on design round 5→9; rpi's `next` was overridden by the user in 5
of 16 sessions and named `/flux:plan 05-radio-handler` for four sessions in a row
after the user had moved to 04c/04d.

**F2 — radiator wrapped 3 of 13 sessions; $386 of work ended with no state write.** No
`/flux:wrap` was ever typed there (CLAUDE.md says to; the skill is not model-invocable
so the model cannot do it on its own). The state carrier became a hand-kept 21 KB
`status.md` + a 46 KB `04-design-pass.md` + a 9 KB hand-written handoff — read whole
at every session start. That is the bloated-state-artifact pattern prime exists to
replace, reconstituted one directory down because the 2 000-token pack cannot hold a
narrative. **The flux repo does the same to itself**: `status.md` is 106 KB and the
last seven sessions read 25–89 KB of it at start; flux-repo median context rose from
70k (pre-v2) to 94k.

**F3 — the model routes around the gate.** Raw gate invocations vs `flux check`:
rpi 35 vs 24, radiator 59 vs 9. Raw output landed 12.2 KB / 18.7 KB in context vs
3.6 KB / 3.5 KB through the filter. `flux run` was used **0 times** in 44
adopting-repo sessions. Subset iteration (one pytest file, `npm run check | tail`)
goes raw because nothing in context says the filtered path exists.

**F4 — the CLI is rediscovered every session.** `flux --help` ran in 5 radiator
sessions + 1 broadcast; the model `cat`-ed skill files out of the plugin cache in 4
sessions (rpi ×2, radiator, broadcast) because `disable-model-invocation` hides them.
Each such read is 4–12 KB the pack was supposed to make unnecessary.

**F5 — stale keys ride the pack unflagged.** rpi's `blocker` was written once
(2026-08-27) and never again; it announced *"T1(b)/T3/T4 BLOCKED until … an
ACK-payload-returning primitive"* for 5 days and 10 sessions after 04a shipped exactly
that primitive. The pack has no notion of age.

**F6 — `routing` is dead.** 18 writes in rpi, 17 say `design`; the one `mechanical`
phase (04b) ran on Opus like every other session. Nothing reads the key; the user
picks models with `/model`. It costs one pack line and a stamp in every plan.

**F7 — context runaway is user-policed.** radiator sessions reached 471k context,
300 requests, 8 h wall. The user intervened by hand three times: *"can I close this
session and start new session?"*, *"this is exceeding the smart zone"*, *"make sure
everything is ready for a handoff"*. flux has no guard; the ledger's own
`sessions > 150 requests` target is exactly this.

**F8 — audit paid, every time it ran.** Three plan audits in rpi (04a, 04b, 04d):
1 blocking (a step told the executor to reuse a decoder that does not exist as
described — dead import), 13 recommended, each a real trap: a "mirror `send()`'s
wait" step that would have popped and discarded the reply; a `done` gate on a test
that is red host-side by design; an AC whose verify passed without the edit; a
fixture built via `__new__` that would lack the new members. **C2 of the
pre-registration is met on the first project.**

**F9 — work does not stay in one repo.** rpi phases 03/04 wrote `radio_bench.py` /
`ota_bench.py` into archsense-backend; state about them lived in rpi's pack; the user
asked for a handoff *to the other repo* and said "it doesn't have anything to do with
flux". radiator also had two parallel sessions stomp each other's untracked files
twice (`git add -A`).

**F10 — the instrument was missing.** Only broadcast has a `field-log.md`. rpi and
radiator produced the pack-misses above and nobody could log them. `flux init` does
not create it.

**F11 — skill utilisation since v2, all projects:** plan 21 · wrap 33 · apply 18 ·
audit 15 · grill 10. **Zero:** resume, adopt, review, wayfinder, to-spec, to-tickets,
ask-matt, research, writing-for-agents. (adopt was performed in radiator by the model
reading the skill file off disk, not by invocation.)

**F12 — kiosk's conflict metric has no denominator:** 1 commit touching
`state.jsonl`, 0 merges since 2026-08-24. No real kiosk work has happened on v2.

## 4. Pre-registration read-out (2026-08-25 claims)

- **C1 (wrap pays)** — supported where wrap ran (F1), falsified where it did not
  (radiator). The failure is a stale `next`, not a wrong `position`.
- **C2 (audit pays on incomplete plans)** — **met** (F8): 3/3 audits landed real hits.
- **C3 (plan only when unsettled)** — weakly supported: 04b was routed mechanical,
  planned anyway, and was the priciest phase ($44) with the longest unwrapped session.
- **C4 (carrier is the whole story)** — holds; no line anywhere shows flux moving code
  quality rather than the model's view of the tree.

KEEP plan / audit / wrap stands. The problem is not the ceremony's value, it is that
wrap is optional and invisible, so it is skipped exactly in the sessions that need it.

## 5. What to do — each with the metric it must move

### Add
1. **`flux guard` on a `UserPromptSubmit` hook.** Read `transcript_path`, take the last
   assistant `usage`, and when context > 120k or requests > 120 emit one line:
   *"context 231k / 300 req — close: `flux check && flux state set … && flux
   handoff`, then /clear"*. Silent in non-flux repos. → `sessions > 150 requests`
   (radiator 5 → 0), median context.
2. **Wrap-debt on `SessionEnd`** (`flux seal`): if no state write happened during the
   session, append `[unwrapped] <id> <n req>` to `.flux/field-log.md`; next `prime`
   prints *"previous session ended without wrap — reconcile `next` against git log"*.
   → wrap coverage becomes a measured number; pack-miss.
3. **Key age in the pack**: `blocker: (unchanged 5d, 10 sessions) …`. Timestamps are
   already in `state.jsonl`. → pack-miss (F5).
4. **Inline the latest handoff under its own cap** (~1 200 tokens) and make
   `flux handoff` clip; every primed session `cat`s it first anyway. → calls before
   first edit, ramp bytes.
5. **Pack footer with the verbs**: `gate: flux check · subset: flux run -- <cmd> ·
   close: flux check && flux state set … && flux handoff`. → `--help` reads (6 → 0),
   skill-file reads (F4), Bash output (F3).
6. **`flux log [audit-hit|pack-miss|want] "…"`** and `flux init` creates
   `field-log.md`. No ledger metric — it *is* the instrument (F10).
7. *(optional, measure-first)* **Gate-bypass nudge**: `PreToolUse` on Bash, when the
   command equals the configured gate command, add context "run `flux check`
   instead"; escalate to `updatedInput` rewrite only if the nudge does not move
   → Bash output / session (raw 12–19 KB → ~3.5 KB).

### Change
8. **Apply flux to flux**: cap `status.md` at ~8 KB of live state; the dated
   write-ups already have a home in `.flux/analysis/`. → flux-repo median context
   94k → ~70k (F2).
9. *(optional)* Session heartbeat in `.flux/cache/`; prime warns of another session
   active < 30 min ago. Unmeasured; fixes the double stomp (F9).

### Remove
10. **`routing`** key, `[routing]` table, plan stamp (F6). Principle 5, zero movement.
11. **Eight zero-use skills**: resume, review, wayfinder, to-spec, to-tickets,
    ask-matt, research, writing-for-agents. Fold `adopt`'s recipe into `flux init`
    output. Listing cost is already 0; the cost is maintenance surface and the model
    reading them off disk.
12. **`flux run`** goes on notice: 0 uses in 44 sessions. Item 5 is its last chance;
    delete next cycle if it stays at 0.
13. **kiosk conflict metric**: close as unmeasurable (F12) unless kiosk work resumes.
