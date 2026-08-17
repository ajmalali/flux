---
name: sync
description: Reconcile work that happened outside the harness — list the commits that name no ticket, give each one a retroactive closed ticket, flag what contradicts an ADR, and advance the sync baseline. Use when prime's drift line offers it; --skip accepts those commits as they are.
disable-model-invocation: true
---

Take the commits nobody ticketed and leave with history queryable again: every one of them
either named in a retroactive closed ticket or accepted on the record, the baseline advanced
to exactly the commits that were listed, and anything they contradict flagged for the human.

This is repair. The detection already happened — prime counted the drift at session start
and offered you two endings, `/sync` and `/sync --skip`, both of which are legitimate and
both of which are yours to honour (ADR-0001).

## 1. List the drift — never compute it

`bin/flux-drift` sits beside this skill in the plugin: the harness names this skill's
directory when it loads it, and the executable is two levels up from there.

    BIN=$(cd "<this skill's directory>/../../bin" && pwd)
    "$BIN"/flux-drift

One state line, then one `sha` TAB `subject` row per drifted commit, oldest first.

Do not write the walk yourself. The definition of "names no ticket" is `ticket_id_re` in
bin/flux-common: it discovers this repo's prefix, keeps `bd` alongside it, widens only where
the repo names neither, and matches the subject *and* the body. A `git log --grep` over
subjects for `FLX-[0-9]+` is narrower on both axes and wrong on an id like FLX-63o — and
because prime counts through the same function, every disagreement is silent. You would
either invent a ticket for a commit prime never counted, or leave a drift line standing
after a /sync that believed it had finished.

| state | what it means and what you do |
| --- | --- |
| `drift <base>` | The rows are the set to reconcile. Run `git rev-parse HEAD` now and keep it: that sha, not the HEAD you happen to hold at the end, is the only thing the baseline may be advanced to. |
| `synced <base>` | The baseline resolves and nothing since it is unattributed. Say so and stop — /sync writes nothing on a clean tree. |
| `unseeded` | No baseline recorded yet. Say that the harness starts counting at HEAD and stop without writes: history from before the harness is not drift, and the first heartbeat seeds the field from HEAD anyway. |
| `unresolvable <base>` | Section 2, before anything else. |
| `no-repo` | Not a git repository. Say so and stop. |

The set you were handed is complete. flux-drift walks unbounded, where prime and the
heartbeat stop at 200 commits to stay inside the hook budget — their number is a floor,
yours is the whole window. That is what makes `--skip` honest.

## 2. An unresolvable baseline is re-anchored first, and only on confirmation

`unresolvable` means the recorded baseline is no longer in this line of history — a rebase,
an amend, a reset, a branch rewritten under a worktree. Nothing else in the harness repairs
this: the heartbeat preserves the field and only /sync writes it, so drift detection for
this worktree is off until you fix it, reporting a confident `0` the whole time.

Propose the newest commit in history whose message names a ticket. The harness's own
convention is that a closing commit names its id, so that commit is the last moment the
store and the tree are known to have agreed:

    root=$(git rev-parse --show-toplevel)
    re=$(bash -c '. "$1"/flux-common; ticket_id_re "$2"' _ "$BIN" "$root")
    git -C "$root" log -n 200 --format='%H%x09%s' | grep -m1 -E "$re"

Same matcher again, from the same place. Subjects only is right here and nowhere else: you
are looking for a commit that *closed* a ticket, and that is a subject convention.

Print the candidate with the commits it implies — `git log --oneline <candidate>..HEAD` —
and adopt it only when the user says so. If no commit in history names a ticket, stop and
ask the human for a sha. Never infer one and apply it; a wrong anchor silently invents drift
or silently hides it, and both look like a clean run.

Once confirmed, write that sha as the baseline (section 6), re-run flux-drift, and continue
from the list it now prints.

## 3. `--skip` — the other legal ending

Committing outside the harness on purpose is an answer, not a defect. `--skip` runs the
listing and the baseline write and nothing in between:

1. Print the commits being accepted — the same enumerated rows, in full. A decision nobody
   can see is not a decision.
2. Ask first. This is the one path that discards work the harness would otherwise have
   recorded, so it is confirmed even though it looks like the cheap option.
3. On yes, advance the baseline to the HEAD captured in section 1 (section 6). Create no
   tickets, write nothing else, and say so.

What the baseline asserts afterwards is wider than before: not "everything before this is
ticketed" but "everything before this is accounted for — ticketed, or deliberately not".
Drift accrued after the skip still counts. This silences a set of commits, never the check.

`--skip` is never the fallback for a /sync that failed part way. A run that cannot summarize
the commits, or cannot create tickets, stops and says which commits are still unreconciled —
advancing the baseline there would lose them with no record that anything was skipped.

## 4. Read the commits, and group only where the work is plainly one piece

One retroactive ticket per commit is the default and usually the answer. Over-splitting costs
a row in the store; over-merging destroys the sha→work mapping that makes the record worth
having.

Read what each commit actually changed — `git show --stat <sha>`, and the diff itself where
the stat does not say enough. Where the repo is indexed, gitnexus `detect_changes` and
`impact` summarize a change faster and more accurately than reading a diff; plain diff
reading is the fallback, not a lesser answer.

Group two commits only when they are one piece of work: a fix and the test that proves it, a
rename that landed in two halves. Shared files are evidence and never the rule — file overlap
under transitive closure collapses every commit into a single cluster the moment a hub path
(CLAUDE.md, a spec, `.beads/issues.jsonl`) appears in two of them.

## 5. Retroactive tickets, created closed

One per cluster, in the repo's ticket voice, and closed in the same breath:

    bd create "<title>" -t task -l retroactive --stdin <<'BODY'
    <what changed and why, from the diff — the ticket this work would have had>

    Commits:
    - <sha> <subject>
    BODY

    bd close <id> --actor "$(basename "$PWD")" -r "reconciled by /sync"

The shas are the point: they are what makes the ticket a record of *this* work rather than a
description of it. The `retroactive` label marks a ticket reconstructed after the fact, so a
later reader does not mistake it for one that guided the work. The actor is the worktree, as
everywhere else in the harness.

Always closed. /sync reconstructs the record and never reopens the work, never proposes
follow-ups from what it read, and never judges the raw changes — anything worth doing next is
its own ticket, written the normal way.

## 6. Reconcile, then advance the baseline

**The check.** `ls docs/adr/` — the filenames state the decisions, so the listing is the
index. Open only the ones the combined changes touch, and read CONTEXT.md for the vocabulary
they use. Three outcomes, and only one of them is a write:

- A contradiction with an ADR or a glossary term is **flagged for the human**, never resolved
  here. An ADR is superseded deliberately, with a number, or it is not superseded (ADR-0010).
- Structural change that no ADR covers is raised as a **candidate ADR** — named, with what it
  would decide — not written into a document. There is no architecture file to update and
  that is the decision, not an omission (ADR-0010).
- Vocabulary the work introduced may be **added to CONTEXT.md**, which is where terms live.

**The write.** One field, and /sync is its only writer besides initialization:

    bash -c '. "$1"/flux-common; session_stamp "$2" last_synced_commit "$3"' _ \
      "$BIN" "$root" "<the HEAD captured in section 1>"

Through `session_stamp` rather than an edit to .flux/session.json: it is atomic and it
merges, so the branch, the drift count and the token reading the heartbeat wrote a moment ago
survive. Hand-writing that JSON replaces the file and drops them.

The sha is the one captured in section 1. Never `git rev-parse HEAD` at the end of the run —
if a commit landed while you worked, that advances the baseline over a commit you never
enumerated, which is the one thing neither ending is allowed to do.

**The escape hatch.** `bd export -o .beads/issues.jsonl` — the tracked JSONL is refreshed at
most once a minute after a write, so it lags a run that just created tickets, and a stale
hatch is worse than no hatch because it reads as current (CLAUDE.md). It stays dirty in the
tree; /sync makes no commits, and the report says what it left behind.

## 7. The handback

The completion criterion is that every unattributed commit is accounted for, so print the
accounting — one row per commit, with the grouping visible:

    <sha>  <subject>  →  <ticket id>

Then: what was flagged and against which ADR, any candidate ADR raised, where the baseline
moved from and to, and what is left dirty. Say that the drift line will be gone next session.

## Done

Every commit flux-drift printed is either named in a retroactive closed ticket or listed in
a `--skip` the user confirmed. The baseline is the HEAD that was listed, written through
session_stamp. The ADR and glossary check ran, and whatever it found was flagged rather than
fixed. A run that could not finish says which commits remain, leaves the baseline where it
was, and is a legitimate ending — a baseline advanced over commits nobody enumerated is not.
