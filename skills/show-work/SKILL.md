---
name: show-work
description: Review one completed ticket as a diff-scoped behavior diagram, a plain-English summary, and an acceptance-criteria checklist carrying the command that proved each. Use after /flux:build, or to review the current branch.
disable-model-invocation: true
---

Take one finished piece of work and leave with a page a human reads in a minute: one
diagram of what now behaves differently, five sentences of why, and every acceptance
criterion the ticket named, marked pass or fail beside the command that settled it.

The subject is the diff. Not the feature, not the system the feature lives in — the diff.
Everything below is a constraint on that scope, and the constraints are the value: a
diagram of the whole architecture is easy to produce, impossible to check, and tells a
reviewer nothing about what changed today.

## 1. Scope the diff

The input is a ticket id. Absent, the subject is the current branch against its merge-base,
and you say so in the artifact — a branch review is a legitimate ending, but it is a
different claim from a ticket review and is never printed as one.

**With a ticket id.** Its commits name it in the subject (ADR-0011), so the store gives the
brief and the log gives the change:

```bash
bd show <id> --json                     # ACs it serves, tasks, Verify lines
git log --format='%h %s' --grep='<id>'  # the commits that claim it
```

Diff the span from the first of those commits to the last:

```bash
git diff "$(git log --format=%H --grep='<id>' | tail -1)^" \
         "$(git log --format=%H --grep='<id>' | head -1)"
```

Read the file list before the hunks. Commits naming the ticket that sit either side of
unrelated ones make that span carry work the ticket never did — when the file list shows
that, drop the span, read the commits one at a time with `git show`, and say in the
artifact which commits the diagram covers.

Nothing found for the id: say so and stop. A ticket with no commit has nothing to show, and
drawing one from its Tasks would render intent as if it were behaviour.

**Without one.**

```bash
git diff "$(git merge-base main HEAD)"...HEAD   # main, or this repo's default branch
```

Then read the acceptance criteria. The ticket's `Spec:` line names them by number and the
text lives in the spec it names — read those lines, not the spec.

## 2. Pick the diagram, from the shape of the change

One diagram type, chosen by what the diff actually alters — never by preference, and never
by which one is easiest to draw from the file names.

| The diff changes | Type | The reader's question it answers |
| --- | --- | --- |
| a request, event, or message path | `sequenceDiagram` | who calls whom, and in what order |
| logic, branching, or state | `flowchart` | which way control now goes |
| schema, tables, or stored shape | `erDiagram` | what is stored, and how it relates |

A mixed diff picks the type for the change a reviewer would ask about first; the rest goes
into the summary as prose. Two types in one artifact is step 3's split, not a hedge.

## 3. Draw only what changed

Five rules. They are hard, and the last is the one that gets rationalized.

**≤12 nodes.** Count nodes, not edges, and count the greyed ones. Twelve is what a person
holds without tracing; past it the diagram becomes a thing to study rather than to read.

**Only changed behaviour.** Every node earns its place by appearing in the diff or by being
what a changed edge touches. Untouched neighbours are context, allowed only where the change
is unreadable without them, and drawn greyed.

**NEW and CHANGED stay distinguishable.** Every edge label carries a marker — `NEW` or `CHG`
— and the arrow reinforces it where the type allows: in a `flowchart`, `==>` new, `-->`
changed, `-.->` untouched context; in a `sequenceDiagram`, `->>` for both and `-->>` for
context. `erDiagram` styles nothing, so there the label marker is the whole signal. A legend
line under the diagram states the convention in use.

**Grey means untouched, and grey is the only colour.** One mid-grey that reads on a light
and a dark background — `classDef ctx fill:none,stroke:#888,color:#888` — because the page
renders in the viewer's theme, not yours, and a palette tuned in one is illegible in the
other. Everything else takes mermaid's default.

**Labels use CONTEXT.md vocabulary.** Frontier, claim, drift, handoff, prime, heartbeat,
qualify — as the glossary defines them, never a synonym it lists under _Avoid_, and never a
function name standing in for a concept. A diagram labelled in code identifiers is a second
reading of the diff rather than a summary of it.

**Too big for twelve honest nodes: split.** Two diagrams, cut at a seam the change already
has — one flow each, one subsystem each — both under the cap, each captioned with what it
covers. Never one dense diagram, and never a real node dropped to make the count.

## 4. Write the artifact

Three parts, in this order, and nothing else.

**The diagram**, with its legend, and its sibling where step 3 split it.

**What changed and why** — five sentences or fewer, plain English. What behaves differently
now, and what it was for. No file paths, no function names, no restatement of the diagram in
prose. If five sentences will not hold it, the diff is two reviews.

**The acceptance-criteria checklist.** One row per AC the ticket names:

| AC | What it requires | Result | Evidence |
| --- | --- | --- | --- |
| AC-9 | one diagram ≤12 nodes scoped to the diff… | pass | `bash tests/run.sh` — 14 passed |

The evidence command is the `Verify:` of the task that serves that AC — named by the task's
`Done:` line where it says so, and otherwise matched from the ticket's `Spec:` line, which
names every AC the ticket serves. Most tickets do not name ACs per task, so the fallback is
the common path rather than the exception. **Run it fresh
here and read what it prints.** A pass inherited from the build session's report is not a
pass, it is that session's memory of one — and the point of the checklist is that a reviewer
need not trust the run being reviewed. A command that cannot run in this session (a live
check, a `human-verify` checkpoint) is marked `unproven` with the reason, never `pass`. A
failure is reported as a failure: this skill reviews the work, it does not defend it.

Every AC the ticket names appears in that table with a result and a command. That is the
completion criterion — a checklist missing a row is the run unfinished, not a shorter run.

## 5. Publish, then hand back

Load the `artifact-design` skill before writing the file. It is required for every artifact
and it decides the treatment. Write HTML, with the diagram in a `<pre class="mermaid">` block
— that skill is explicit that Markdown is for Markdown-bound destinations and never a way to
skip the design pass, and a review is read by a person, not piped anywhere. Give the diagram
container a light neutral background in both themes: mermaid paints its own node fills, and a
diagram dropped straight onto a dark page ground is dark text on dark.

Keep the treatment steady across reviews. These accumulate into a gallery, and a house style
is what lets a reader compare two of them instead of re-learning each one.

Write the file to the session scratchpad, publish it, and print the link. Title it for the
ticket — `FLX-12 Show Work` — so a gallery of these is scannable, and keep the favicon stable
across republishes of the same review.

Re-publishing the same path in the same session redeploys to the same URL. A later session
has a new scratchpad path, so find the existing review with the publish tool's `list` action
and update in place — otherwise the same review exists twice and the link the user already
holds goes stale without saying so.

Close by naming the result: the pass, fail and unproven counts, and the link.

## Done

One published artifact, with one diagram inside the cap, five sentences or fewer, and every
acceptance criterion the ticket names carrying a result and the command that produced it,
run in this session. A review reporting a pass it did not watch is the failure this skill
exists to make impossible.
