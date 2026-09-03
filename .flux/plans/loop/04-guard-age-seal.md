---
phase: 04-guard-age-seal
routing: design
status: done
files:
  - bin/flux                       # cmd_guard + cmd_seal; key-age in _prime_inner; last-session/guard markers
  - hooks/hooks.json               # UserPromptSubmit -> flux guard; SessionEnd -> flux seal
  - tests/test_flux_cli.py         # guard threshold/anti-nag/no-op; key-age markers; seal unwrapped; prime warn
  - README.md                      # one paragraph: the two new hooks and what they do
---

## objective
Close the three gaps the field read-out named loudest at the session boundary, all as
hook-safe additions to `bin/flux` under the existing byte discipline:

1. **`flux guard`** on `UserPromptSubmit` — the session has no brake. radiator ran to
   471k context / 300 requests / 8 h because nothing told the model or the user they had
   left the smart zone (F7). guard counts the current session's main-thread requests the
   *same way the ledger does* and, past a threshold, injects one line naming the count
   and the wrap+clear action. → target: `sessions > 150 req: 5 → 0` per cycle.
2. **key age in the pack** — prime shows state keys with no notion of age, so a `blocker`
   written once rode the pack for 5 days and 10 sessions after it was resolved (F5).
   Prime stamps every stale key with its age. → target: stale-key days-max in pack ≤ 2.
3. **`flux seal`** on `SessionEnd` — radiator wrapped 3 of 13 sessions; $386 of work
   ended with no state write and the next pack lied for six sessions (F1, F2). The wrap
   skill is not model-invocable, so nobody notices a missed wrap until the next session
   trusts a stale `next`. seal detects an unwrapped substantive session, logs it to the
   field-log, and leaves a marker prime reads to warn the *next* session that the pack
   may be stale. → target: wrap coverage printed by the ledger (already is; seal raises
   the number).

Read-out items landed: 1 (context runaway → guard), 2 (stale keys → age), 3 (unwrapped
sessions → seal). Roadmap row 04, routing **design**.

## context (do not re-derive)
- **The three claims (roadmap row 04):** `sessions > 150 req: 5 → 0` per cycle; wrap
  coverage printed by the ledger; stale-key days-max in the pack ≤ 2. The first two are
  read next cycle by `flux ledger` (its `sessions > 150` and `wrap coverage` columns —
  `_scan_session` already computes both, bin/flux:1290/1443/1466); the third is
  structural at apply (markers present) plus behavioural later. Not falsifiable at apply
  time — recorded in phase 05, exactly like phases 02/03.
- **guard counts what the ledger counts, or the claim judges a different number than the
  feature acts on.** guard reuses `_scan_session(transcript_path)["requests"]` verbatim
  (bin/flux:1309) — main-thread, deduped on `message.id`, sidechain excluded
  (bin/flux:1290/1382–1390) — so its threshold and the ledger's `sessions > 150` column
  are one definition. `_scan_session` opens with `errors="replace"` and skips unparseable
  lines, so a live transcript with a half-written final line is safe to scan mid-session.
  **seal does NOT scan a transcript** — see the SessionEnd budget note below.
- **Hook input contract (confirmed against the Claude Code hooks docs, `## coherence`).**
  Every hook receives one JSON object on stdin carrying the common fields `session_id`,
  `cwd`, `hook_event_name`, and `transcript_path`; SessionEnd also carries `reason`
  (`clear` | `resume` | `logout` | `prompt_input_exit` | `other`). The per-event docs do
  not always re-list `transcript_path`, so guard treats it as **best-effort**: it prefers
  stdin's `transcript_path`, and falls back to
  `PROJECTS_DIR/_slug_for_path(root)/<session_id>.jsonl` (bin/flux:1175/1219 — the reliable
  on-disk name). Any failure (empty stdin, unparseable JSON, no resolvable transcript,
  path absent) is a **silent no-op, return 0** — the rule prime lives by. seal needs no
  transcript at all (below).
- **Hook output contract.** A UserPromptSubmit hook that exits 0 and prints to stdout has
  that stdout injected into the model's context for the turn (exactly how prime's pack
  reaches context on SessionStart; the precise structured form is
  `{"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":"…"}}`,
  but a plain `print()` is injected the same way — guard uses the plain form). Below
  threshold guard prints nothing and injects nothing. guard must **never** exit non-zero:
  **exit 2 blocks the prompt**, and guard is a nudge, not a gate (F7 is user-policed by
  design — we hand the user the signal flux lacked, we do not take the wheel).
- **SessionEnd runs under a very tight timeout and its stdout is ignored** (the session is
  ending). So seal must be **O(1) and transcript-free** — it cannot afford to
  `_scan_session` a multi-MB transcript at teardown, and it cannot inject context. seal's
  only jobs are a durable field-log entry and a tiny marker prime reads next start, both
  derived from cheap `.flux/cache/` breadcrumbs, never from parsing the transcript.
  Correctness is best-effort by design: a missed seal loses one warning, never corrupts
  state, and the ledger recomputes wrap coverage authoritatively from transcripts next
  cycle regardless.
- **Wrap breadcrumb (new, cheap).** seal cannot scan for a wrap, so the wrap must announce
  itself when it happens: `flux state set` (on a successful write) and `flux handoff` (on
  success) each `_touch_wrap(root)` — write `now_iso()` to `.flux/cache/last-wrap`, O(1).
  A real wrap always runs one of these (the `/flux:wrap` skill ends by calling both), so
  the breadcrumb covers every wrap path without seal parsing anything. prime already keeps
  `.flux/cache/last-prime` (bin/flux:769, written every SessionStart), so seal reads this
  session's start as `last-prime`'s mtime and decides `wrapped = last-wrap newer than
  last-prime` and `substantive = (now − last-prime mtime) ≥ substantive_seconds`. No
  `session_id` match, no `transcript_path`, no scan.
- **Where the pack is built:** `_prime_inner` (bin/flux:657) renders the narrative keys in
  a fixed loop (bin/flux:686–690: `for key in ("phase","position","next","routing","open")`)
  off `read_state(root)` — which returns a flat `{key: value}` and drops per-key
  timestamps. The age data is one call away: `winners(read_log(state_log_path(root)))`
  (bin/flux:190) already returns `{key: (ts, value)}`, newest write per key, ISO stamp.
  The whole pack is `clip()`-ed to the state budget at bin/flux:701, so an age suffix and
  a one-line seal warning ride that clip for free.
- **`.flux/cache/` is the marker home** and is gitignored (bin/flux:620–623 writes
  `cache/`). `_cold_gap_seconds` already keeps `cache/last-prime` there (bin/flux:769).
  Two more tiny JSON markers join it — `cache/guard.json` (guard's anti-nag memory) and
  `cache/last-session.json` (seal → prime handoff). Rebuildable scratch, never committed.
- **`_append_field_log(root, tag, text)`** (added phase 03, bin/flux near cmd_log) is the
  one writer for `.flux/field-log.md`, and `flux log` accepts an **open bareword tag** on
  purpose so seal can log `unwrapped` without re-touching cmd_log (phase 03 `## coherence`
  called this out). seal calls `_append_field_log(root, "unwrapped", "...")` directly —
  it does not shell out to `flux log`.
- **Config is optional, defaults live in code.** A new `[guard]` table in flux.toml is
  read with fallbacks so every already-adopted repo (rpi, radiator, broadcast, kiosk,
  this repo) keeps working with no edit: `warn_requests` (120), `renudge` (25),
  `stale_days` (2), `substantive_seconds` (180). `flux init` scaffolds a commented
  `[guard]` block in the template for discoverability; missing table or missing key falls
  back to the code default. Threshold rationale: the claim bar is `> 150 → 0`, so the
  brake must engage *before* 150 — 120 leaves ~30 requests of runway to wrap + clear.
  `substantive_seconds` (3 min) is the "was this a real work session?" gate for seal — a
  quick question that never needed a wrap must not cry unwrapped.

## acceptance criteria
AC-1 (guard fires late, stays quiet early) — Given a flux repo and a `transcript_path`
whose scan yields ≥ `warn_requests` main-thread requests, when `flux guard` runs with the
hook JSON on stdin, then it prints exactly one nudge line to stdout naming the live count
and the wrap+clear action, and returns 0. Given a transcript under the threshold, guard
prints nothing and returns 0. Given a non-flux repo, or empty/unparseable stdin, or a
`transcript_path` that does not exist, guard prints nothing and returns 0. guard never
returns non-zero.

AC-2 (guard does not nag) — Given guard has already warned this session at N requests,
when it runs again with the same `session_id` and a count between N and N + `renudge`,
then it prints nothing; when the count reaches N + `renudge` (or more), it warns again and
records the new count. When the `session_id` differs from the marker's, the counter
resets (a new session warns on its own first crossing). The anti-nag memory lives in
`.flux/cache/guard.json` and its absence or corruption degrades to "warn now".

AC-3 (stale keys wear their age) — Given a state key whose last write is older than
`stale_days`, when `flux prime` renders the pack, then that key's line carries a compact
age suffix ` [Nd]`; a key written within `stale_days` carries no suffix. The suffix adds
only a few bytes, the pack still clips to budget, and the header/`phase:`/`next:` line
positions existing prime tests assert on do not move.

AC-4 (seal records an unwrapped session, transcript-free) — Given `.flux/cache/last-prime`
is older than `substantive_seconds` (a real work session) and `.flux/cache/last-wrap` is
absent or older than `last-prime` (no wrap this session), when `flux seal` runs with the
SessionEnd JSON on stdin, then `.flux/field-log.md` gains one `unwrapped` entry (reason +
approx duration) and `.flux/cache/last-session.json` records `{wrapped:false, warn:true}`.
Given `last-wrap` is newer than `last-prime` (a wrap happened), seal writes
`{wrapped:true, warn:false}` and appends nothing. Given `last-prime` is within
`substantive_seconds` (a quick session), seal writes `{warn:false}` and appends nothing —
a two-turn session that never needed a wrap must not cry unwrapped. seal parses no
transcript. Non-flux repo / bad stdin → silent no-op, return 0.

AC-5 (prime warns after an unwrapped session) — Given `.flux/cache/last-session.json`
records `warn:true`, when `flux prime` runs, then the pack carries one warning line that
the last session ended unwrapped and the pack's `next`/`open` may be stale. Given the
marker records `warn:false`, or is absent, prime prints no such line. The warning rides
the pack budget and prime reads only the marker (no scan).

AC-6 (gate + hook-safety) — `flux check` is green (was 216; new tests raise it). The
existing prime/init/state/log tests pass unchanged. In a repo without `.flux/`, all three
hook targets (`flux prime`, `flux guard`, `flux seal`) print nothing and return 0.

## tasks
### T1 — `flux guard` on UserPromptSubmit
files: bin/flux
do: add `cmd_guard(_args)` wrapped like prime — `try: return _guard_inner(); except
Exception: return 0`. `_guard_inner`: read+parse stdin JSON (helper `_hook_input()`
returning `{}` on any failure); `root = repo_root()`, `cfg = read_config(root)`; if cfg is
None → return 0 (silent). Resolve the transcript (helper `_hook_transcript(data, root)`):
prefer `data["transcript_path"]` if it is a file, else
`os.path.join(PROJECTS_DIR, _slug_for_path(root), data["session_id"] + ".jsonl")`; if
neither resolves to a file → return 0. `row = _scan_session(path)`; `count =
row["requests"]` (0 if row is None). Read
`[guard]` config with fallbacks (`warn_requests` 120, `renudge` 25). Load
`.flux/cache/guard.json` (`{session_id, last_warn}`, `{}` on any error). If `session_id`
differs → treat `last_warn` as 0. Warn iff `count >= warn_requests` **and** (`last_warn ==
0` or `count >= last_warn + renudge`); on warn, `print` one line — e.g.
`flux guard: this session is at N requests (past the smart zone). Wrap now — flux check &&
flux state set … && flux handoff — then /clear.` — and write `guard.json` with
`{session_id, last_warn: count}`. Below threshold or inside the re-nudge window: print
nothing. Register `"guard": cmd_guard` in `COMMANDS`; add to the module docstring's command
list. Never return non-zero.
verify: feed hook JSON on stdin pointing at a synthetic transcript with 130 assistant
requests → one nudge line, rc 0; run again same session at 140 (renudge 25) → silent;
at 145 → silent; at 155 → warns again; different session_id at 130 → warns. Under-threshold
transcript, non-flux repo, empty stdin → silent, rc 0.
done: AC-1, AC-2.

### T2 — key age in the prime pack
files: bin/flux
do: in `_prime_inner`, before the key-render loop, build
`aged = winners(read_log(state_log_path(root)))` (guard the file-absent path — legacy
state.toml has no per-key ts, so `aged` is `{}` and no suffix is added, which is correct).
Read `stale_days` from `[guard]` (default 2). Add a helper `_key_age_days(iso)` → whole
days between the key's ISO ts and now (UTC), or None if unparseable. In the render loop,
after appending a key's line, if `aged.get(key)` yields an age > `stale_days`, append
` [%dd]` to that line. Keep the suffix off any key whose value is empty (already skipped)
and off derived/absent keys. No new budget path — the suffix rides the existing `clip()`.
verify: seed a state log with an `open` key written 8 days ago and a `next` written today →
`flux prime` shows `open: … [8d]` and `next:` with no suffix; the header line and the
`phase:`/`next:` lines keep their positions; the 40-byte-budget prime test still clips.
done: AC-3.

### T3 — `flux seal` on SessionEnd (transcript-free)
files: bin/flux
do: add `_touch_wrap(root)` — write `now_iso()` to `.flux/cache/last-wrap` (mkdir -p the
cache dir; swallow errors). Call it from `cmd_state` on a successful `set` write and from
`cmd_handoff` after the handoff file is written — O(1), the breadcrumb every wrap leaves.
Add `cmd_seal(_args)` wrapped like prime/guard (`try/except → 0`). `_seal_inner`: parse
stdin (`_hook_input()`) for `reason` (default `"other"`); `cfg = read_config(root)`; None →
return 0. Read `substantive_seconds` (default 180). Read the two cache mtimes/contents:
`prime_at = mtime(.flux/cache/last-prime)` (this session's start; if absent → treat as
non-substantive, return 0 after writing a `warn:false` marker); `wrap_at =
iso→epoch(read .flux/cache/last-wrap)` (None if absent). Compute `wrapped = wrap_at is not
None and wrap_at >= prime_at`; `substantive = (now − prime_at) >= substantive_seconds`;
`warn = substantive and not wrapped`. Always write `.flux/cache/last-session.json` =
`{"warn": warn, "wrapped": wrapped, "reason": reason, "ts": now_iso()}`. If `warn` →
`_append_field_log(root, "unwrapped", "reason=%s, ~%dm session, no state write" % (reason,
minutes))`. Register `"seal": cmd_seal` in `COMMANDS` and the docstring. seal opens no
transcript.
verify: with `last-prime` backdated 25 min and no `last-wrap` → `flux seal` (SessionEnd
JSON on stdin) appends one `unwrapped` field-log line and writes `warn:true`; with a
`last-wrap` newer than `last-prime` → no field-log line, `warn:false`; with `last-prime`
30 s old → no field-log line, `warn:false`; non-flux repo / empty stdin → no file written,
rc 0. Then: a successful `flux state set` writes `.flux/cache/last-wrap`; `flux handoff`
does too.
done: AC-4.

### T4 — prime reads the seal marker and warns
files: bin/flux
do: in `_prime_inner`, after the state keys (and near the existing cold-gap note), read
`.flux/cache/last-session.json` (helper, `{}` on any error). If it records `warn: true`
(the flag pinned in T3), append one line —
`warn: last session ended unwrapped — its next/open may be stale; verify before trusting
the pack.` Do not scan any transcript in prime (it must stay fast); the marker is the only
input. The line rides the pack `clip()`.
verify: with a `warn:true` marker → prime shows the warn line; `warn:false` or no marker →
no warn line; header/first-line assertions unmoved.
done: AC-5.

### T5 — hook wiring + config scaffold
files: hooks/hooks.json, bin/flux
do: add to `hooks/hooks.json` (do **not** name it in plugin.json — it is auto-loaded;
naming it disables the plugin silently) a `UserPromptSubmit` entry running
`"${CLAUDE_PLUGIN_ROOT}/bin/flux" guard` (timeout 10) and a `SessionEnd` entry running
`"${CLAUDE_PLUGIN_ROOT}/bin/flux" seal` (short timeout — seal is O(1) and SessionEnd's
budget is tight; set 5), keeping the existing SessionStart → prime. In
`FLUX_TOML_TEMPLATE`, add a commented `[guard]` block documenting the four keys
(`warn_requests`, `renudge`, `stale_days`, `substantive_seconds`) and their defaults (all
optional). Bump `plugin.json` version so `claude plugin update flux@marketplace` takes.
verify: `python3 -c "import json; json.load(open('hooks/hooks.json'))"` parses; the three
events are present; `flux init` in a temp repo writes a flux.toml carrying the commented
`[guard]` block; a fresh `[guard]`-less repo still runs guard/seal on their defaults.
done: wiring in place; AC-6's hook-safety verified in T6.

### T6 — tests
files: tests/test_flux_cli.py
do: add `TestGuard(FluxRepoCase)` — a helper that writes a synthetic transcript with K
assistant records (reuse/adapt the ledger test's transcript builder if importable, else a
local minimal one: `{"type":"assistant","message":{"id":"m%d","usage":{...}}}` lines) and
runs `flux guard` with hook JSON piped to stdin; cases: warn at/over threshold, silence
under, anti-nag window + renudge, session-id reset, non-flux + empty-stdin no-op, never
non-zero. `TestKeyAge(FluxRepoCase)` — append state records with backdated `ts`, assert
the ` [Nd]` suffix on the stale key and none on the fresh one, and that a header/`next:`
assertion still holds. `TestSeal(FluxRepoCase)` — backdate `.flux/cache/last-prime` 25 min
with no `last-wrap` → seal appends `unwrapped` + marker `warn:true`; write `last-wrap`
newer than `last-prime` → no log + `warn:false`; `last-prime` 30 s old → no log +
`warn:false`; non-flux no-op; then `flux prime` after a `warn:true` marker shows the warn
line and after `warn:false` does not; and assert a successful `flux state set` (and `flux
handoff`) creates `.flux/cache/last-wrap`. Reuse `run_flux`/`FluxRepoCase`; pipe stdin via
the existing runner (add an `input=` path if the runner lacks one).
verify: `python3 -m unittest discover -s tests` green; count > 216.
done: AC-6.

## boundaries
do not change: `_scan_session`, `cmd_ledger`, `_ledger_row` — guard *consumes*
`_scan_session`, it does not alter it (a change there moves the ledger's own columns).
`read_state`'s flat-dict contract (T2 reads timestamps via `winners`/`read_log` directly,
not by widening `read_state`). `cmd_log`/`_append_field_log` (seal calls the helper; the
open-tag decision is already made). The state format, `plan.md`, `status.md` beyond the
session-close update, and the roadmap. `cmd_state`/`cmd_handoff` gain **only** a one-line
`_touch_wrap(root)` breadcrumb side-effect (append-a-cache-file, error-swallowed) — no
change to what they write to state or print. Do not make guard block the prompt (nudge
only) or have seal parse a transcript / inject context (SessionEnd budget is tight, its
stdout ignored). Do not require any repo to edit flux.toml — defaults live in code.
out of scope: `flux claim`, `claims.jsonl`, `ledger --verdict`, prime's cycle line
(phase 05); handoff inline (phase 06); removing `routing`/skills, folding `adopt` (phase
07); the gate-bypass `PreToolUse` nudge and session heartbeat (phase 08). Do not tally the
field-log's `unwrapped` entries here — that is phase 05's ledger read. Do not touch
radiator/kiosk; they pick up the hooks from the plugin update on their next session.

## verification
`flux check` green (count > 216), plus, in a temp flux repo:
- `flux guard` with hook JSON at a 130-request synthetic transcript prints one nudge and
  rc 0; re-run same session inside the re-nudge window is silent; a fresh session_id warns;
  under-threshold / non-flux / empty-stdin are silent, rc 0.
- a state log with an 8-day-old key → `flux prime` shows ` [8d]` on it, nothing on a
  same-day key, header/`next:` positions unchanged.
- `flux seal` with `last-prime` backdated 25 min and no `last-wrap` → one `unwrapped`
  field-log line + `warn:true` marker; the following `flux prime` carries the unwrapped
  warning; a `last-wrap` newer than `last-prime` (a wrap ran) → no field-log line, prime
  quiet; and a successful `flux state set`/`flux handoff` drops the `last-wrap` breadcrumb.
The **claims** are not falsifiable at apply time: `sessions > 150 → 0` and wrap coverage
are read next cycle by `flux ledger` in the adopting repos (its `sessions > 150` and wrap
columns) and recorded in phase 05; stale-key days-max ≤ 2 is structural here (markers
present) and behavioural later. Record all three in `## outcome`.

## coherence
Checked against `00-roadmap.md` row 04 (design): the three deliverables — `flux guard` on
UserPromptSubmit, key age in the pack, `flux seal` on SessionEnd logging `unwrapped` and
prime warning — and the three claims match verbatim. Against
`.flux/analysis/2026-09-03-field-readout.md` §3: guard answers F7 (context runaway,
user-policed today), age answers F5 (stale keys ride unflagged), seal answers F1/F2
(unwrapped sessions, the wrap skill not being model-invocable). Against CLAUDE.md's binding
conventions: single-file stdlib-only (all logic in `bin/flux`, no deps); byte caps enforced
(age suffix, guard nudge, and seal warning all ride the existing pack/state `clip()`; the
field-log `unwrapped` text goes through `_append_field_log`'s clip; markers are fixed-size
JSON scratch, gitignored); `flux prime` never fails / never nags in non-flux repos — and
guard/seal inherit the same rule verbatim (blanket try/except → 0, cfg-None silent no-op,
bad-stdin no-op); every feature names its ledger metric (guard → `sessions > 150`; seal →
wrap coverage; age → structural + behavioural). Decisions made explicit rather than left to
apply: (1) guard **nudges, never gates** (no non-zero exit — exit 2 would block the prompt)
— F7 is user-policed by design and the read-out's target is a *count to drive down*, not a
wall. (2) The warn threshold (120) sits below the claim bar (150) so the brake has runway;
both are `[guard]` keys, tunable without a code change. (3) guard reuses `_scan_session`
so it counts the exact number the claim is scored by; **seal does not** — SessionEnd's
tight teardown budget forbids a transcript scan, so seal decides wrapped/substantive from
O(1) `.flux/cache/` breadcrumbs (`last-wrap` written by every real wrap; `last-prime`
written every SessionStart), and its output is advisory (the ledger recomputes wrap
coverage authoritatively next cycle). (4) `transcript_path` is best-effort in the hook
stdin, so guard falls back to `session_id`→slug; seal needs no transcript at all. No
contradiction found with plan.md's targets table or the binding conventions.

## outcome
(unwritten — filled at apply.)

## outcome — 2026-09-03
shipped: `flux guard` (UserPromptSubmit) reuses `_scan_session["requests"]` — the ledger's
  exact count — and nudges past `[guard].warn_requests` (120), anti-nagging via
  `cache/guard.json`+`renudge`, never exiting non-zero. `flux seal` (SessionEnd) is
  transcript-free: it reads `cache/last-wrap` (dropped by `_touch_wrap` on every `state
  set`/`handoff`) vs `cache/last-prime` mtime, logs `unwrapped` to the field log past
  `substantive_seconds` (180), and writes `cache/last-session.json`. prime stamps stale
  state keys ` [Nd]` (from the state-log ts, `stale_days` 2) and warns when the seal marker
  says the last session ended unwrapped. hooks.json carries all three events; the toml
  template scaffolds a commented `[guard]` block; plugin.json 2.10.1 → 2.11.0. `flux check`
  green at 238 tests (+22; was 216). All six ACs PASS.
deviated: README got three CLI-table rows (guard, seal, prime additions) rather than the
  frontmatter's "one paragraph" — the file was declared but no task specified it; honored
  the declared scope in the table's existing style.
deferred: the three claims are not falsifiable at apply, exactly as the plan pinned —
  `sessions > 150 → 0` and wrap coverage are read next cycle by `flux ledger` in the
  adopting repos (its `sessions > 150` and wrap columns), stale-key days-max ≤ 2 is
  structural here + behavioural later; all recorded for phase 05. Nothing dropped from scope.
