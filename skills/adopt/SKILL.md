---
name: adopt
description: Bring a repo into flux — migrate whatever project knowledge it already carries (PAUL, agent-os, a hand-kept STATE.md or ROADMAP.md, just a CLAUDE.md) into .flux/ state and plans, then optionally retire the old framework by archiving it. Run once per repo.
disable-model-invocation: true
---

# flux adopt

A repo already knows things. Adoption moves the part that is still *true* into a pack
a cold session can read in one screen, and leaves the rest where it is. Run once.

## 1. Inventory, don't read

```
flux init --scan
```

Deterministic: it finds and sizes prior state and opens nothing. If `.flux/flux.toml`
doesn't exist yet, run `flux init` now — adopt fills what init scaffolds.

## 2. Sort it into live and history

The whole job is this distinction, and almost everything is history.

- **Live** — where the work actually stands, what comes next, what is blocked or
  unproven. This is the only thing that reaches `flux state set`, and it is five
  values. A 300 KB state file usually yields four sentences.
- **Semi-live** — the roadmap or design the current effort is still executing
  against. Becomes `.flux/plans/<effort>/plan.md` (the binding design) and
  `status.md` (queue and current state), rewritten to what still holds — not copied.
- **History** — completed phases, past decisions, summaries, research, transcripts.
  Stays exactly where it is. It is not migrated, not summarised, not deleted.

Migration is lossy on purpose. Say what you dropped and where the original still
lives — that sentence is what makes the loss safe.

## 3. Read from the ends, and narrowly

Never load a large state file whole; that spends the context adoption exists to save.
Map it first, then read only the live sections:

```
grep -n '^#\{1,3\} ' STATE.md        # the section index
sed -n '10,88p' STATE.md | cut -c1-300  # one section, line length capped
```

**Cap line length, not line count.** These files are append-layered and their lines
run long — kiosk's `STATE.md` is 300 KB over 631 lines, with a single 17 KB line, so a
plain `head -60` returned 100 KB. `head`/`tail` alone are not a budget; `cut -c1-300`
is. Prefer targeted questions to the built-in `Explore` agent over reading at all,
and take its pointers back rather than its pages. Read history only where it explains something live.

## 4. Trust the tree over the framework

The old state was written by whoever stopped last, and stopped states go stale. Check
it against `git log --oneline -20`, the current branch, the dirty files, and the gate.
Where they disagree, the repo is right and the document is a claim. Adopting a stale
"phase complete" is how a fresh session confidently resumes work that was abandoned.

## 5. Write the pack

```
flux state set phase "..." position "..." next "..." \
  open "what is unproven, blocked, or untested — or empty"
```

`position` is reality including the half-done parts, minus anything prime derives
live (branch, dirty count, ahead/behind are in the header); `next` is executable by someone
with no memory of this repo; `open` carries every unverified claim you found, because
it reappears at every session start until someone kills it. Then run `flux check` once
— that both validates the detected gate and flips its `verified` stamp.

## 6. Read it back as a stranger

`flux prime` renders exactly what a new session will see. Does it say where the work
is, what is unproven, and what to do first — with none of this conversation? If not,
fix it now. Everything downstream reads this and nothing else.

## 7. Retiring the old framework — only if asked

Ask; don't assume. And recommend the honest order: **adopt, run one real phase on
flux, then retire.** Retiring the working system before the replacement has proven
itself in this repo is how a repo ends up with neither.

When the user does confirm:

- **Archive, never delete.** `git mv .paul .flux/archive/paul/` — history preserved,
  reversible, and the pack still points at where the detail went. `rm` only if the
  user explicitly insists, and only after saying what is being destroyed.
- **Require a clean tree first.** Commit before moving, so the move is one reviewable
  change and nothing is lost with it.
- **State and framework are separate decisions.** `.paul/` (the project's knowledge)
  and `.claude/paul-framework/` (the machinery) retire independently — the user may
  well want the knowledge archived and the machinery gone, or the reverse.
- **Machine-level installs are not yours.** Plugins, marketplaces, `~/.claude`
  settings and global commands live outside the repo. Name what should go and let the
  user remove it.

## Repos with nothing to migrate

Adoption still applies — the sources are the repo itself. `flux init`, then build the
pack from README, CLAUDE.md, recent commits and the branch: what this project is,
where it stands, the obvious next move. Then `flux check` to prove the gate. That is a
complete adoption; there is no missing ceremony.
