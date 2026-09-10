---
phase: task-index-01-index-core
routing: mechanical
status: done
files: [bin/flux, tests/test_task.py, README.md, .flux/plans/flux-v2/plan.md, .claude-plugin/plugin.json]
---

## objective
`flux task add/start/done/list/next/compact` exists over an append-only `.flux/tasks.jsonl`
replayed like state, `start` takes a lease under git's common dir that `next` honours across
worktrees, and `flux prime` derives its `task:`/`next:` lines from the index — ADR 0004 build
step 1, with tiers/escalate/await (step 2) and adoption (step 3) untouched.

Contract source: `.flux/adr/0004-task-index-execution.md` points 2, 5, 6, 7 and the storage
rules in `.flux/analysis/2026-08-26-execution-index-revival-design.md` §Storage. Glossary:
`CONTEXT.md`. Everything below that the ADR left open is **settled here**, not re-argued in apply.

## settled shapes (the part a cold session must not guess)

**Records** — one JSON line per op, appended, never rewritten; `merge=union` like `state.jsonl`.

```
{"ts":"2026-09-10T09:14:03.221Z","id":"t-k3nq","op":"add","title":"...","files":["a.py","tests/test_a.py"],"blocked_by":["t-8h2a"],"verify":"flux check","ref":".flux/plans/x/spec.md#s3"}
{"ts":"...","id":"t-k3nq","op":"start","where":"<hostname>:<worktree basename>"}
{"ts":"...","id":"t-k3nq","op":"done","by":"flux check green + 3 tests in test_a.py"}
```

- `files`, `blocked_by`, `verify`, `ref` are optional on `add`; `title` is required, ≤120 chars.
  `blocked_by` names the ids this task waits on (the ADR's "explicit blocks edges" — the
  field is named for its direction so it cannot be read backwards).
- **A single add record is capped at `TASK_RECORD_MAX_BYTES = 1024`**; `add` refuses over it
  (CLAUDE.md: no uncapped stored state). Any positional starting with `-` that is not a known
  flag is refused whole (the `state set` dash guard, reused).
- **Id** = `"t-" + base32(sha1(ts + "\n" + title))[:4].lower()` (ADR 0004 §6). A collision
  with an existing id → exit 1 "id collision, re-run" (32⁴ space; ms timestamp makes a re-run
  distinct). Never counted, never reused.
- **Replay**: group by id, ops in `(ts, file position)` order (`winners()` semantics). Status:
  no `add` → orphan, ignored; last op `done` → `done`; last op `start` → `active`; else `open`.
  `blocked = any(status(b) != "done" for b in blocked_by)` — computed on read, never stored.
  Unknown ids in `blocked_by` count as not-done (blocks forever, `list` shows `?t-xxxx`).
  Unparseable lines skipped, never raised (reuse `read_log`'s posture; new reader, since
  `read_log` filters on `k`).
- **Order** = `(add ts, id)` everywhere: `list`, `next`, compaction. Candidate = not done, not
  blocked, and no live *foreign* lease. `next` ranks candidates (1) `active` with a live lease
  held by *this* worktree, then (2) `open`, **or `active` with no live lease at all** (T1 has
  no leases yet; a lease cleared by `seal` or expired leaves the log saying `active`), in
  `(add ts, id)` order within each rank; none → exit 1 with `no runnable task` on stderr.
  Same input → same task, twice. <!-- audit -->
  `next --all` prints every runnable task, one per line, same order (ADR §2; the batch
  consumer is phase 2, the verb is free here).
- **Compaction** (`flux task compact`, and automatic in `add`/`done` when the log exceeds
  `STATE_LOG_BUDGET_MULTIPLE × state_budget_bytes`, i.e. the same 8× trigger as state; the
  auto-compaction notice goes to **stderr** — `add`'s stdout is the id alone, unlike
  `state set` which prints its notice on stdout): one <!-- audit -->
  record per id — the `add` record with the terminal fields folded in: `"status":"done"`,
  `"by"`, `"done_ts"` for done; `"status":"active"`, `"where"`, `"start_ts"` for active;
  bare add for open. **Replay expands folded fields into synthetic ops at their own stamps**
  (`start` @ `start_ts`, `done` @ `done_ts`) and sorts them with the real ops — never "initial
  state then later ops": a clone that compacted after `done` merged with a branch that
  appended an earlier `start` must still replay to `done`. Folded active/done records carry
  `"starts": [where…]` (every `start` since the last `done`) so the `[2 starts]` flag
  survives compaction. Output sorted by `(ts, id)`, `ensure_ascii=False`, deterministic →
  byte-identical across clones. Done tasks are never dropped (ADR §7: no archive file), so
  compaction bounds **op noise only**, not the file: past ~400 done tasks the log stays over
  8× and every `add`/`done` rewrites it — accepted, and the notice prints only when
  `before > after`. <!-- audit -->
- **Leases**: `start` writes `<git-common-dir>/flux/leases/<id>.json` =
  `{"ts": iso, "where": "<host>:<wt>", "worktree": "<realpath root>"}`. Common dir via
  `git(["rev-parse", "--git-common-dir"], cwd=root)` — **the call must run at root**: git
  answers relative to cwd (`.git` at toplevel, `../.git` from a subdir, absolute in a linked
  worktree), so join the answer to root. `git()` returns `""` on failure; then `_lease_dir`
  returns `None`, `start` exits 1 (`cannot lease: not a git repo`), and `next`/`seal`/prime
  treat leases as absent — never fall through to `<root>/flux/leases/` inside the tree.
  Lease age via `_iso_epoch` (UTC both sides). A lease is **live** iff the file parses to a
  dict with `ts` and `worktree`, `ts` is younger than `[task] lease_hours` (default 12,
  optional knob read by a new `_task_cfg(cfg, key, default)` — `_guard_cfg` is hardcoded to
  `[guard]`; do not generalise it), and `os.path.isdir(worktree)` (a deleted worktree's
  lease is dead, not a 12 h block). Unparseable → `_lease_read` returns `{}` → dead and
  overwritable. Worktree paths compared with `os.path.realpath` on both sides (macOS
  `/var` vs `/private/var`). `next` skips tasks with a live lease whose `worktree` ≠ this
  root; `start` refuses such a task (exit 1, names `where`), overwrites a dead or own lease;
  `done` on a task with a live foreign lease → exit 1 (the other session owns it); `done`
  order is append → compact → unlink lease (a crash after append leaves a harmless lease on
  a done task). `flux seal` (SessionEnd) unlinks every lease whose `worktree` == this root
  **and every unreadable one**, in its own try/except placed right after the `cfg is None`
  check — `_seal_inner` early-returns when `cache/last-prime` is missing, so cleanup must
  run before that. Prime's helper honours leases with the same candidate function `next`
  uses, and returns before any git call when `tasks.jsonl` is absent (this runs on every
  SessionStart in the fleet). flux never creates a worktree (ADR §5). <!-- audit -->
- **Conflict flag**: `list` marks a task whose replayed ops contain two `start` records with
  different `where` and no `done` between them as `[2 starts: a, b]` (ADR §5, second machine).
- **Budgets**: `list` output clipped to `state_budget_bytes`; `next` output is at most one
  add record per line (already capped); the prime `task:` line is clipped to
  `TASK_LINE_BUDGET = 200` bytes with `clip(line, 200, marker="…")` — the default marker is
  multi-line and would split a pack line. <!-- audit -->

**CLI**

```
flux task add   "<title>" [--files a,b] [--blocked-by t-x,t-y] [--verify "<cmd>"] [--ref <path>]
flux task start <id>
flux task done  <id> --by "<what verified it>"
flux task list  [--open | --done | --all]      # default: everything not done
flux task next  [--all]
flux task compact
```

`add` prints the id alone on stdout (so `$(flux task add …)` composes). `done` without
`--by` is usage error 2. `start`/`done` on an unknown id → exit 1. `done` is allowed from
`open` (a verification-only task never needs `start`, ADR §4) and refused if already done.
`start` on a blocked task → exit 1 naming the blockers. **`start` on a `done` task → exit 1**
(last-op-wins replay would otherwise make it an undocumented `reopen`, which is phase 2).
No `.flux/flux.toml` (or a corrupt one — `read_config` returns `None` for both) → the
`cmd_state` precedent: `flux task: no .flux/flux.toml here — run \`flux init\` first`, exit 1.
Flag parsing: a flag with no value → usage 2; flag **values** are taken verbatim (the dash
guard applies to positionals only); `title` ≤120 is characters, the record cap is bytes.
Output grammar, pinned so tests/README/prime agree:
- `list`: `<id>  <status>  <title>` + suffixes ` @<where>` (active), ` (blocked by t-x, ?t-y)`,
  ` [2 starts: a, b]`; `--done` rows append ` — by: <by>`; last line
  `N open, M blocked, K done`. Statuses print as `open`/`active`/`done`; a blocked task is
  `open` with the suffix.
- `next`: one line per task, `<id>  <title>` then ` · files: a,b`, ` · verify: <cmd>`,
  ` · ref: <path>` for the fields present.
New imports: `hashlib`, `base64`, `socket` (stdlib; not `uuid`). <!-- audit -->

**Prime** (`_prime_inner`, own try/except like the cycle line — a broken index must never
blank the pack): when the index has ≥1 task that is not done, the `phase` line is omitted and
`task: <id> <title> · N open, M blocked, K done` is printed in its place (after the cold
note, before `position`). If state `next` is unset and a runnable task exists, print
`next: <id> <title>  [from index — flux task next]` and suppress the `(unset — …)` hint.
State `next`, when set, still wins (ADR §7: override and fallback). The derived line is
emitted **in the key loop's `next` slot** (not where the unset hint is appended, after the
handoff block) and carries no `[Nd]` suffix, so pack order does not depend on which path
fired. <!-- audit --> **With no index or an
all-done index the pack is byte-identical to today** — the fleet must not see a change.

## acceptance criteria
AC-1 — Given an initialised repo, when `flux task add "A"`, `add "B" --blocked-by <A>`,
`start <A>`, `done <A> --by "x"` run in sequence, then `next` prints A (active) after
start, B after done, and `list` shows the statuses `active`/`open (blocked by …)`/`done`
at each step; `next` run twice with no write between prints the same id.
AC-2 — Given task A started in worktree W1, when `flux task next` runs in worktree W2 of the
same repo, then A is skipped; after `flux seal` runs in W1 (or the lease is older than
`lease_hours`), W2's `next` returns A.
AC-3 — Given a log with 3 done, 1 active, 1 open task across 9 records, when `flux task
compact` runs, then the file has exactly 5 records, `list --all` is unchanged before/after,
and compacting again is byte-identical.
AC-4 — Given `.flux/tasks.jsonl` with one open task, when `flux prime` runs, then the pack
has a `task:` line and no `phase:` line; given no `tasks.jsonl`, the pack is byte-identical
to the pre-phase output for the same state; given an all-done index that is **committed**
(an untracked `tasks.jsonl` changes the header's dirty count, so the test commits it first),
the pack is byte-identical to the no-index pack. <!-- audit -->
AC-5 — Given a 1.1 KB `--verify` string, when `flux task add` runs, then it exits 1, writes
nothing, and names `TASK_RECORD_MAX_BYTES`; given `flux init` on a repo whose
`.flux/.gitattributes` already exists without the tasks line, then the line
`tasks.jsonl merge=union` is appended.

## tasks
### T1 — Add the task op-log and the six verbs
files: bin/flux (new section after `cmd_state_log`/`migrate_legacy`, ~lines 1150–1180; `COMMANDS`; `GITATTRIBUTES`; `write_gitattributes`; docstring), tests/test_task.py (new; `from test_flux_cli import FluxRepoCase, run_flux, flux_module`)
do: constants `TASKS_LOG_NAME = "tasks.jsonl"`, `TASK_RECORD_MAX_BYTES = 1024`, `TASK_TITLE_MAX = 120`; `tasks_path(root)`, `read_task_log(path)` (skip non-`{` and unparseable lines, keep dicts with str `id` and `op`), `replay_tasks(records) -> OrderedDict id → {title, files, blocked_by, verify, ref, status, where, by, ts, starts:[where…]}` honouring folded compaction fields, `task_blocked(tasks, id)`, `task_order(tasks)`, `task_id(ts, title)`, `append_task(path, rec)`, `compact_tasks(path)` per the settled shape, `cmd_task(args)` dispatching add/start/done/list/next/compact with the exact exit codes above; `GITATTRIBUTES` gains `tasks.jsonl merge=union`, `write_gitattributes` appends the missing line when the file exists (existing state line untouched; write a leading `\n` when the file lacks a trailing newline, else the two lines fuse). Note: `write_gitattributes` runs on every `state set` and in `migrate_legacy`, so 2.12.0 modifies tracked `.flux/.gitattributes` on the first wrap in every fleet repo — intended; say so in the README Update row. <!-- audit --> Leases are T2 — in T1 `next` ignores leases and `start` writes none.
verify: `python3 -m unittest tests.test_task -v` — tests for: id format `^t-[a-z2-7]{4}$` and determinism (same ts+title → same id via `flux_module().task_id`), add prints id only, title required/≤120, record cap refusal writes nothing (AC-5), dash-guard refusal, blocked computed (AC-1 sequence), unknown blocker blocks forever and renders `?t-…`, next deterministic + exit 1 when none, `next --all` order, done requires `--by`, done refused twice, start refused on blocked, garbage line skipped, compaction count/idempotence (AC-3), auto-compaction past 8× budget (set `budget_tokens = 20` in flux.toml to make it cheap), `list` clipped at budget, gitattributes append (AC-5). Then `flux check` green.
done: AC-1, AC-3, AC-5 when those tests pass and the full suite stays green (267 + new).

### T2 — Add leases under git's common dir, honoured by next/start, cleared by done/seal
files: bin/flux (`_lease_dir(root)`, `_lease_read/_write/_clear`, `_lease_live(lease, cfg)`, `_where(root)`; edits in `cmd_task` start/next/done and in `_seal_inner`; `FLUX_TOML_TEMPLATE` gains a commented `[task]` block with `# lease_hours = 12`), tests/test_task.py
do: per the settled lease shape. `_where` = `socket.gethostname().split(".")[0] + ":" + basename(root)`. `next` skips tasks with a live foreign lease; own live lease on an active task makes it the first candidate. `start` refuses on a live foreign lease (exit 1, message includes `where`), overwrites a dead or own lease. `done` removes the lease file if present. `_seal_inner` walks the lease dir and unlinks entries whose `worktree` equals this root — all inside the existing try/except so seal can never fail. `list` conflict flag from two `start` ops with different `where` and no intervening `done`.
verify: tests using `git worktree add <sibling mkdtemp>/w2 -b w2` on the case repo (W2 lives outside `self.repo` — inside it changes the dirty count — and tearDown runs `git worktree remove --force` before the temp dir is cleaned, else git keeps a dangling registration; lease `worktree` assertions compare against `os.path.realpath(self.repo)`): <!-- audit --> start in W1 → `next` in W2 skips (AC-2); `seal` in W1 (stdin `{}`) frees it; a lease with `ts` 13h old is ignored; done removes the lease file; `start` in W2 on W1's live lease exits 1; conflict flag renders after two `start` records with different `where` (write the second record directly to the log — that is what a merge from another machine looks like). Existing `TestSeal` untouched and green.
done: AC-2 when those tests pass and `flux check` is green.

### T3 — Prime derives task/next from the index; docs and version
files: bin/flux (`_prime_inner`, new `_task_pack_lines(root, cfg, state)` with its own try/except; docstring `Commands:` line), README.md (Commands table: two rows, `flux task add/start/done` and `flux task next/list`), .flux/plans/flux-v2/plan.md (§"The execution index": one dated amendment paragraph — ADR 0004 supersedes the section; surface is add/start/done/list/next/compact, no `block` verb, no per-task token estimate or `[task].budget_tokens` refusal, per its "considered and rejected"), .claude-plugin/plugin.json (2.11.1 → 2.12.0 — a CLI change the fleet must receive; see README §Update)
do: per the settled Prime shape. The `task:` line is built by the helper and clipped to `TASK_LINE_BUDGET`; the `phase` loop skips `phase` only when the helper reports ≥1 not-done task; the derived `next:` line replaces the unset hint only when state `next` is empty and a runnable task exists. Update the docstring `Commands:` line and add the `flux task …` usage lines beside `flux state log`.
verify: tests: pack with one open task has `task:` and no `phase:` (AC-4a); pack with no `tasks.jsonl`, and with an all-done index, is byte-equal to the pack captured before the index existed in the same repo (AC-4b — capture stdout before touching tasks, compare after); state `next` set wins over the derived line; a corrupt `tasks.jsonl` (one garbage line, no records) leaves the pack identical; `task:` line ≤200 bytes with a 300-char title. `TestHelp` only asserts `"flux" in stdout`, so it cannot catch a docstring error — eyeball `bin/flux --help` once. Then `flux check` green, and by hand: `bin/flux prime` in this repo at HEAD vs with the change applied, compared **from the second line** (the header's dirty count differs while `bin/flux` is edited); no index here, so lines 2+ must be identical. <!-- audit -->
done: AC-4 when those tests pass, README/plan.md/plugin.json committed with the code.

## boundaries
do not change: `state.jsonl` reading/writing (`read_log`, `winners`, `replay`, `compact_log`) — reuse the *pattern*, not the functions; the task log has ids and ops, not keys. `flux handoff` — the ADR's "handoff carries await steps whole" is phase 2. `_seal_inner`'s existing unwrapped-warning logic — only add lease cleanup beside it. The prime pack for repos without an index — byte-identical is an AC, not a nicety.
out of scope: tiers (`tracer`/`fill`), `escalate`, `await`/`reopen`, `--tier`, any skill edit (plan/apply/wrap rewrite is phase 2); a `block` verb (edges are declared at `add`; phase 2 decides if editing edges is needed); id-collision retry logic; a `[task] fill_model` knob; any claim seeding (`flux claim add` is phase 3 — no ledger metric moves until broadcast adopts); `flux run` deletion (on notice, separate decision).

## verification
`flux check` green (expect ~267 + ~30 new), plus what tests cannot see:
- In a scratch clone with two `git worktree`s, run the AC-2 sequence by hand and confirm
  `<common-dir>/flux/leases/` is where the file lands and that it is untracked (`git status`
  clean in both worktrees).
- `bin/flux prime` in **this** repo before and after the change, diffed from line 2: empty. <!-- audit -->
- `claude plugin update flux@marketplace` after push shows 2.12.0 and `flux task next` runs
  from a fresh shell in another **adopted** repo (it should say `no runnable task`, exit 1,
  not traceback; in a non-flux repo it says `no .flux/flux.toml here`, exit 1) — the
  deployment-gap check from 2026-09-08. <!-- audit -->

## audit — 2026-09-10
verdict: ready with conditions
applied: 5 blocking, 15 recommended
conditions: T1 must ship the `next` candidate rule as amended (active-without-lease is a
candidate) before T3, or prime's derived `next:` and `flux task next` disagree between T1 and
T2; the by-hand prime diff and the AC-4 all-done case compare from line 2 / on a committed
index, never on a dirty tree.
deferred:
- Clock skew across machines can order a merged `start` before its `add` by ts, replaying to
  `open` — ADR 0002 already records cross-machine ties as arbitrary; note, don't fix.
- `flux init --force` rewrites `flux.toml` from the template, so the commented `[task]` block
  appears only on re-init; the code default applies otherwise — pre-existing behaviour.
- The `write_gitattributes` append reaches the fleet only at 2.12.0 regardless of which task
  lands it — no action.


## outcome — 2026-09-10
shipped: `flux task add/start/done/list/next/compact` over append-only
`.flux/tasks.jsonl`, replayed like the state log (content-addressed `t-xxxx` ids,
1024-byte record cap, blocked/next computed on read, 8× auto-compaction to stderr).
`start` leases under `<git-common-dir>/flux/leases/`, honoured by `next`/`start`/`done`
and cleared by `seal`. `prime` swaps `task:` for `phase:` when the index has live work
and fills a derived `next:`. gitattributes gains `tasks.jsonl merge=union` (appended,
not clobbered). README + plan.md amendment + plugin.json 2.12.0. 306 tests green
(267 + 39). ACs 1–5 all met; by-hand two-worktree lease run and the line-2 prime diff
both confirmed.
deviated:
- `_where()` and the `start` record's `where` field landed in T1, not T2 — the conflict
  flag needs `where` on the record independent of lease files.
- `— by: <what>` renders on done rows in every view, not only `--done` (harmless, more
  informative).
- `N open` counts every not-done task (open + active); `M blocked` is a subset. The
  plan's grammar named no separate active count; documented in `task_counts`.
- The derived `next:` line is clipped to `TASK_LINE_BUDGET` too — leaving it uncapped
  would be a new uncapped output path (CLAUDE.md).
- `_lease_dir` is memoised process-wide — without it, `next`/prime spawned one
  `git rev-parse` per candidate task on every SessionStart.
- `TASKS_LOG_NAME` sits in the top constants block (not the task section) so
  `GITATTRIBUTES_LINES` names it rather than hardcoding the filename twice.
- `flux task list` on an empty index prints a hint at exit 0, not a bare count line.
deferred: nothing from this phase's scope. ADR 0004 phases 2 (tiers/escalate/await/
reopen, `next --all` batch consumer) and 3 (adoption, `flux claim add` seeding) are
untouched by design. Post-push, still to confirm: `claude plugin update flux@marketplace`
shows 2.12.0, and `flux task next` runs from a fresh shell in another adopted repo (the
2026-09-08 deployment-gap check).
