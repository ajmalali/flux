---
phase: 07-deletions
routing: mechanical
status: done
files:
  - bin/flux
  - skills/plan/SKILL.md
  - skills/wrap/SKILL.md
  - skills/resume/SKILL.md
  - skills/adopt/SKILL.md
  - skills/review/
  - skills/wayfinder/
  - skills/to-spec/
  - skills/to-tickets/
  - skills/ask-matt/
  - skills/research/
  - skills/writing-for-agents/
  - scripts/sync-vendored.sh
  - skills/VENDORED.md
  - README.md
  - .flux/plans/flux-v2/plan.md
  - .flux/plans/flux-v2/status.md
  - tests/
---

## objective
The dead `routing` machinery is gone, the eight zero-use skills are deleted (skills dir
14 → 6) with the re-sync script and docs updated so a re-sync won't resurrect them, and
`flux run` / the kiosk conflict metric are recorded as closed — with `flux check` still
green and the pack one line shorter.

This is the field read-out's four removals (items 10–13, F6/F11/F12). Size: **standard,
3 tasks** — T1 (routing) and T2 (skills) are the substance; T3 is doc-only. T2 is the
heavy, irreversible, outward-facing one (adopting repos lose `/flux:resume`, `/flux:review`,
etc.), so this phase warrants `/flux:audit` before apply.

## acceptance criteria
<!-- audit --> AC-1 rewritten: the old wording ("no longer records or errors … accepted-and-ignored
<!-- audit --> or rejected") was self-contradictory and unsatisfiable — adding unknown-key
<!-- audit --> validation would break two existing sample-key tests (D1). The pack print comes from
<!-- audit --> a hardcoded literal at bin/flux:786, NOT STATE_KEY_ORDER (B1). Corrected below.
- **AC-1** — Given a primed flux-repo session, when `flux prime` runs, then the pack
  no longer prints a `routing:` line and prints one fewer state line than before.
  <!-- audit --> `flux state set … routing "x"` still SUCCEEDS silently — `cmd_state` keeps
  <!-- audit --> accepting arbitrary keys; routing is simply no longer surfaced. No new
  <!-- audit --> validation is added (that would break the sample-key tests — see D1).
- **AC-1b** <!-- audit --> — Given THIS repo after apply, when `flux state get` runs, then it
  <!-- audit --> shows no live `routing` record: the dev repo currently carries a live
  <!-- audit --> `routing = mechanical` (15 routing records, latest live), which `order_state`
  <!-- audit --> would otherwise keep dumping in the alphabetical tail even after :786 is fixed (B3).
- **AC-2** — Given the repo after apply, when you `ls skills/`, then exactly six skill
  directories remain — `adopt, apply, audit, grill, plan, wrap` — and none of the eight
  deleted names appears in `bin/flux`, `scripts/sync-vendored.sh`, `skills/VENDORED.md`,
  or `README.md`.
- **AC-3** — Given the updated `scripts/sync-vendored.sh`, when it is read end-to-end,
  then it copies/hides/rewrites only `grill` (the sole surviving vendored skill) and a
  re-sync run would not recreate any deleted directory.
- **AC-4** — Given `flux init` in a repo that already carries project state, when it
  runs, then its output carries the adopt recipe inline (no need to open the adopt skill
  file to know the next steps); `adopt` remains as the canonical deeper reference.
- **AC-5** — Given `.flux/plans/flux-v2/plan.md` and `status.md`, when read, then neither
  describes `routing` as live machinery, and `status.md` records `flux run` as on-notice
  (delete next cycle if still 0 uses) and the kiosk conflict metric as closed-unmeasurable.
- **AC-6** — `flux check` (`python3 -m unittest discover -s tests`) is green.
- **AC-7** <!-- audit --> — Given `.flux/plans/flux-v2/plan.md` and `CLAUDE.md` after apply,
  <!-- audit --> when read, then NEITHER describes a skill roster that no longer exists (B4/R6):
  <!-- audit --> plan.md no longer lists `/flux:resume` or the 7 deleted vendored skills as live
  <!-- audit --> (§11-12, §45, §50, §60, §82-85, §105, §188, §195, §205, §326), says "four lifecycle
  <!-- audit --> skills" not five and "six user-invocable" not 14, and names `grill` as the sole
  <!-- audit --> vendored skill; CLAUDE.md:27 ("Vendored skills … minus the lifecycle five") is
  <!-- audit --> corrected to reflect grill-only vendored + four lifecycle skills.

## tasks

### T1 — Excise `routing` from the CLI, skills, and design doc
files: `bin/flux`, `skills/plan/SKILL.md`, `skills/wrap/SKILL.md`, `skills/adopt/SKILL.md`,
`.flux/plans/flux-v2/plan.md`, `.flux/state.jsonl`
<!-- audit --> (`skills/resume/SKILL.md` removed from T1's list — T2 `git rm`s it, so editing it
<!-- audit --> here is discarded work (R4). `tests/` removed — no test asserts routing specially (D1).)
do:
- `bin/flux` — routing lives in **THREE independent places** (B1); all three must change:
  1. <!-- audit --> Edit the **hardcoded pack print tuple** at `:786`
     (`for key in ("phase", "position", "next", "routing", "open"):`) to drop `"routing"`.
     **This is the edit that removes the pack line** — it does NOT reference `STATE_KEY_ORDER`.
  2. <!-- audit --> Drop `"routing"` from `STATE_KEY_ORDER` (:68). This is the write-path/ordering
     tuple; note `cmd_state` `set` (:1038–1093) does NOT consult it and writes arbitrary keys,
     so this edit alone changes nothing user-visible — do it for hygiene, not effect.
  3. Remove the `[routing]` block from `FLUX_TOML_TEMPLATE` (:682).
  <!-- audit --> Do NOT add unknown-key validation to `cmd_state` — `set` must keep accepting
  <!-- audit --> arbitrary keys, or the sample-key tests `test_flux_cli.py:442-446`
  <!-- audit --> (empty-value-clears) and `:540-548` (compact "8 records -> 2") break (B2/D1).
  Existing `.flux/flux.toml` files with `[routing]` keep loading — `load_toml` (:96-119) uses
  `setdefault` and nothing reads `cfg["routing"]`, so removing the template block is cosmetic.
- <!-- audit --> Clear THIS repo's live routing record (B3): `flux state set routing ""`
  <!-- audit --> (empty value clears a key — see the sample-key test). Without this, `flux state get`
  <!-- audit --> keeps dumping `routing = mechanical` from `order_state`'s alphabetical tail even
  <!-- audit --> after :786 is fixed. Run this as part of apply, before the wrap's own state set.
- Skills: from `plan/SKILL.md` remove the `routing` stamp in the frontmatter template, the
  routing-explanation paragraph, the `routing "…"` arg in the close command, <!-- audit --> AND
  the "routing stamp" phrase in the frontmatter `description:` at `:3` (R3); from `wrap/SKILL.md`
  remove `routing` from its `flux state set` line; from `adopt/SKILL.md` remove `routing` from its
  `flux state set` line (:64) <!-- audit --> AND the ":19 `flux init` prints the same routing line"
  sentence, which points at the removed `[routing]` template block (R3).
- `plan.md`: amend §46 (`/flux:plan … stamps routing`) and §124 (model-routing at session
  boundaries) so the doc no longer presents routing as live. Per CLAUDE.md, amend — don't
  contradict silently. <!-- audit --> (The wider plan.md skill-roster amendments are in T2/AC-7.)
verify: `grep -rn "routing" bin/flux skills/plan skills/wrap skills/adopt` returns only
intentional leftovers (nothing in the `:786` pack tuple / `STATE_KEY_ORDER` / toml template
/ skill state-set lines / plan frontmatter);
`grep -n routing skills/audit/SKILL.md` still shows the model-routing-RISK line untouched;
<!-- audit --> `flux state get | grep routing` returns nothing (B3);
`python3 -m unittest discover -s tests` green (incl. the two sample-key tests, unchanged);
a manual `flux prime` in this repo shows no `routing:` line and one fewer state line.
done: AC-1, AC-1b, AC-6 when the above hold.

### T2 — Delete the 8 zero-use skills; keep the re-sync + docs coherent; fold adopt into init
files: `skills/resume/`, `skills/review/`, `skills/wayfinder/`, `skills/to-spec/`,
`skills/to-tickets/`, `skills/ask-matt/`, `skills/research/`, `skills/writing-for-agents/`,
`scripts/sync-vendored.sh`, `skills/VENDORED.md`, `README.md`, `bin/flux`,
`.flux/plans/flux-v2/plan.md` <!-- audit -->, `CLAUDE.md` <!-- audit -->
do:
- `git rm -r` the eight skill directories: `resume` (flux-owned) + the seven vendored
  ones (`review, wayfinder, to-spec, to-tickets, ask-matt, research, writing-for-agents`).
  Survivors must be exactly `adopt, apply, audit, grill, plan, wrap`.
- `scripts/sync-vendored.sh` — the script runs under `set -euo pipefail` (:4), so ANY line
  still touching a deleted dir aborts the whole re-sync. Remove:
  - the `copy_skill` lines for the seven deleted vendored skills (:22–28);
  - the `hide_skill` lines (:44–46) <!-- audit --> and the now-callerless `hide_skill`
    function definition (:39–43) and its stale explanatory comment block (:30–38);
  - <!-- audit --> **line 92** `perl -pi -e 's{^name: code-review$}…' "$DST/review/SKILL.md"`
    — this targets the deleted `review` dir; left in, it errors under `set -e` and aborts the
    re-sync, breaking AC-3 (R1);
  - <!-- audit --> the per-file rewrite loop at `:65–83` — verified a no-op for grill (grill
    contains none of those tokens), so it can go entirely (R2).
  <!-- audit --> KEEP grill's actual wiring: the heredoc + refs `cp` at `:48–64` and the local
  <!-- audit --> cross-link rewrites at `:86–89`. `grill` stays fully wired; a re-sync recreates
  <!-- audit --> nothing deleted.
- `skills/VENDORED.md`: rewrite to state that `grill` is now the only vendored skill;
  drop the review/research/writing-for-agents visibility narrative (still recoverable in
  git history / the analysis files it cites).
- `README.md`: remove references to the deleted `/flux:*` skills.
- <!-- audit --> `.flux/plans/flux-v2/plan.md` — amend the skill-roster claims so the binding
  <!-- audit --> design doc stops describing skills that no longer exist (B4, CLAUDE.md's amend rule):
  <!-- audit --> §11-12/§45 "five … lifecycle skills" → four (plan/audit/apply/wrap; resume gone);
  <!-- audit --> §50 (`/flux:resume` in the lifecycle list) and §60 ("`/flux:resume` routes to apply");
  <!-- audit --> §82-85 + §188/§195/§205/§326 (the vendored roster + wayfinder→to-spec→to-tickets
  <!-- audit --> altitude) → grill-only; §105 "All 14 are user-invocable" → six.
- <!-- audit --> `CLAUDE.md:27` — "Vendored skills (`skills/` minus the lifecycle five)" and the
  <!-- audit --> "lifecycle five" wording go stale: correct to grill-only vendored + four lifecycle
  <!-- audit --> skills (R6).
- Fold adopt's recipe into `flux init` output: expand `_report_prior_state` in `bin/flux`
  (:734-745) so it prints the short adoption recipe inline (init still opens no files), meaning a
  session need not `cat` the adopt skill to know the steps. Keep `adopt/SKILL.md` as the
  canonical deeper reference — do not duplicate its full body; inline only the recipe.
  <!-- audit --> `_report_prior_state` currently has NO clip/budget (unlike `cmd_init_scan`), so
  <!-- audit --> "keep the existing budget discipline" is a no-op — you must ADD a cap or you create
  <!-- audit --> the uncapped output path CLAUDE.md bans (R5). Wrap the recipe in
  <!-- audit --> `clip(…, _scan_budget(root))` (or an equivalent explicit byte cap) and state the cap
  <!-- audit --> in the wrap.
verify: `ls skills/ | sort` is exactly the six survivors;
`grep -rn -E "resume|review|wayfinder|to-spec|to-tickets|ask-matt|research|writing-for-agents"
scripts/sync-vendored.sh skills/VENDORED.md README.md bin/flux` returns nothing (except
`grill`-adjacent matches, which are fine); <!-- audit --> `grep -rn -E "resume|wayfinder|to-spec|
to-tickets|ask-matt|research|writing-for-agents" .flux/plans/flux-v2/plan.md CLAUDE.md` returns
nothing live (B4/R6); reading `sync-vendored.sh` top-to-bottom shows only `grill` handled and no
reference to a deleted dir; <!-- audit --> a dry mental run of the script under `set -e` hits no
deleted path; `flux init` in a state-carrying repo prints the (capped) recipe.
done: AC-2, AC-3, AC-4, AC-7 when the above hold.

### T3 — Record `flux run` on-notice and close the kiosk conflict metric (docs only)
files: `.flux/plans/flux-v2/status.md`, `.flux/plans/loop/00-roadmap.md`
do:
- In `status.md`, add a line marking `flux run` as **on notice**: 0 uses in 44 sessions;
  delete next cycle if it stays at 0 (item 12). No code change — the command and its
  `[run]` config stay for now.
- Record the **kiosk conflict metric as closed-unmeasurable** (item 13, F12): 1 commit
  touching `state.jsonl`, 0 merges since 2026-08-24, so the metric has no denominator.
  The state.jsonl union-merge machinery itself (bin/flux gitattributes/merge driver)
  stays — only the *metric* is closed.
verify: `status.md` shows both notes; `grep -n "on notice\|unmeasurable" .flux/plans/flux-v2/status.md`.
<!-- audit --> `00-roadmap.md` is listed in `files` but needs NO edit this phase: its `07` row (:17)
<!-- audit --> already states the acceptance ("skills dir 14 → 6; pack −1 line"). Leave it; the wrap
<!-- audit --> may flip the phase to done there. It is in `files` only to declare it was considered (R7).
done: AC-5 when both notes are present.

## boundaries
do not change:
- `skills/grill/` and its `references/` — grill had recorded use (F11) and stays vendored;
  it is the one skill `sync-vendored.sh` must keep wiring.
- `skills/audit/SKILL.md:11` — its "routing, anything touching money…" line means
  model-routing *risk*, not the state key; it is not part of item 10.
- the `state.jsonl` union-merge machinery (merge driver / `.gitattributes`) — T3 closes a
  metric, not the mechanism.
- `[run]` config and `cmd_run` — `flux run` is put on notice, not deleted this phase.
out of scope:
- deleting `flux run` itself (that is next cycle if it stays at 0);
- phase 08 items (gate-bypass nudge, heartbeat);
- <!-- audit --> adding unknown-key validation / rejection to `cmd_state` — explicitly NOT done;
  `set` keeps accepting arbitrary keys so the two sample-key tests stay green (B2/D1);
- <!-- audit --> the analysis files (`.flux/analysis/2026-08-23-*.md`, `…status-history.md`) that
  reference deleted skills — historical record, correctly left as-is (D2);
- seeding a new `.flux/claims.jsonl` record — deletions are validated structurally
  (14 → 6, pack −1 line) and by green tests, not by a metric that must *move*; the
  existing F4 skill-file-read behavior is watched by prior claims, so no new claim here
  unless a real ledger metric surfaces (note this decision in the wrap).

## verification
`flux check` green (T1/T2 will touch tests). Beyond what check sees:
- a real `flux prime` in this repo prints no `routing:` line and one fewer state line;
- `ls skills/` shows exactly the six survivors;
- reading `scripts/sync-vendored.sh` confirms a re-sync would resurrect nothing deleted;
- `flux init` in a state-carrying repo shows the adopt recipe inline.

## audit — 2026-09-07
verdict: ready with conditions
applied: 4 blocking, 5 recommended
conditions (fold into apply, all now in the plan above):
- routing lives in THREE places, not one — the pack line comes from the hardcoded literal
  at `bin/flux:786`, not `STATE_KEY_ORDER`; `cmd_state set` writes arbitrary keys and gets
  no new validation (B1/B2/D1). AC-1 rewritten; T1 rewritten to name all three edits.
- this dev repo's own live `routing = mechanical` record is cleared with
  `flux state set routing ""` during apply (B3, AC-1b) — else `flux state get` still shows it.
- `plan.md` (skill roster §11-12/§45/§50/§60/§82-85/§105/§188/§195/§205/§326) and `CLAUDE.md:27`
  are amended so no doc describes a roster that no longer exists (B4/R6, AC-7).
- `sync-vendored.sh:92` (the `review` perl) + the stale `hide_skill` def/comment must be pruned
  or the re-sync aborts under `set -euo pipefail`; grill's real wiring is `:48-64`+`:86-89`,
  not the `:65-83` rewrite loop (R1/R2).
- `_report_prior_state` has no existing cap — the folded recipe must ADD one (`clip`/byte cap)
  or it becomes the uncapped output path CLAUDE.md bans (R5).
- resume dropped from T1's edit list (T2 deletes it — R4); T1 no longer chases nonexistent
  routing tests (D1).
deferred:
- D1 (no test asserts routing specially) — folded as a *warning* not a task: the risk is the
  inverse (don't break the sample-key tests), captured in T1/boundaries.
- D2 (analysis-file references to deleted skills) — historical record, out of scope, left as-is.

## outcome — 2026-09-07
shipped:
- **routing gone (AC-1, AC-1b, AC-6).** All three sites cut in `bin/flux`: the hardcoded
  pack-print tuple (:786), `STATE_KEY_ORDER`, and the `[routing]` block in
  `FLUX_TOML_TEMPLATE`. Skills (`plan`×4, `wrap`, `adopt`×2) and `plan.md` §46/§124
  amended. This repo's live `routing = mechanical` cleared with `flux state set routing ""`.
  `cmd_state set` unchanged (still accepts arbitrary keys) — the two sample-key tests stay
  green. Pack prints one fewer line; `flux state get` shows no routing.
- **8 zero-use skills deleted (AC-2).** `resume` + 7 vendored (`review, wayfinder, to-spec,
  to-tickets, ask-matt, research, writing-for-agents`). Survivors are exactly `adopt, apply,
  audit, grill, plan, wrap`.
- **re-sync + docs coherent (AC-3, AC-7).** `sync-vendored.sh` wires only `grill` (the
  `review` perl, the `hide_skill` machinery, and the `:65-83` rewrite loop all removed;
  `bash -n` clean; no deleted-dir path survives `set -e`). `VENDORED.md`, `README.md`,
  `plan.md` roster (§12→four lifecycle, §105→six user-invocable, §82-91→grill-only), and
  `CLAUDE.md:27` corrected. No doc names the eight deleted skills as live.
- **adopt folded into `flux init` (AC-4).** `_report_prior_state` prints the short adoption
  recipe inline, wrapped in `clip(…, _scan_budget(root))` — closing the uncapped-output gap
  the audit flagged (R5). `adopt/SKILL.md` remains the full reference.
- **metrics recorded (AC-5).** `status.md`: `flux run` on-notice (0/44, delete next cycle);
  kiosk conflict metric closed-unmeasurable (no denominator; union-merge machinery stays).
- `tests/test_flux_cli.py` `LIFECYCLE` dropped `resume` (four lifecycle skills).
- **`flux check` green — 267 tests.**

deviated:
- AC-2 is literal ("none of the eight names appears" in the four files); my first pass left
  the deleted names in the deletion-record prose of `sync-vendored.sh` + `VENDORED.md`.
  Caught in qualification, replaced with a git-history / 07-deletions pointer. Only surviving
  `review` token is the pre-existing English verb ("review the diff by hand").
- `00-roadmap.md` listed in `files` but not edited — per the audit (R7) its 07 row already
  states the acceptance; left for this wrap to flip the phase to done there.

deferred:
- **No new claim seeded** (planned decision, not an omission): deletions are validated
  structurally (14→6, pack −1 line) and by green tests, not by a metric that must move. A
  ledger claim would be added only if a real metric surfaced.
- Deleting `flux run` itself and phase-08 items (gate-bypass nudge, heartbeat) stay out of
  scope — next cycle / next phase.
