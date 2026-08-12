---
name: init
description: Bootstrap this repository for the flux harness. Idempotent — safe to run again after a plugin update.
disable-model-invocation: true
---

Bring one repository up to the state the flux harness expects. Every item below is
**check-then-create**: look at what is already there, act only on what is missing, and
give the item a state. A second run therefore writes nothing.

Work from the repository root (`git rev-parse --show-toplevel`).

## Report

One line per item, in order, using these states:

```
[exists]   CONTEXT.md
[created]  docs/adr/
[blocked]  ticket store — bd not installed
[declined] gitnexus index
```

Done when every item below has a line. An item that could not be settled is `[blocked]`
with the reason on the same line; nothing is left off the list.

## 1. Durable homes

- `CONTEXT.md` — absent: create it with a title, the sentence that terms are opinionated
  and that rejected synonyms are listed under _Avoid_, and an empty `## Language`
  section. Present: leave every byte as found.
- `docs/adr/` and `specs/` — create when absent.
- `.flux/handoffs/` — create when absent. The hooks write `.flux/session.json` themselves.
- `.gitignore` — append `.flux/` when no line already ignores it.

## 2. Tooling

Run this section before the status line: `bd setup claude` writes to
`.claude/settings.json` as well, so the merge in step 3 has to land on top of it.

- `jq` — the hook scripts parse their event JSON with it. Missing: `[blocked]`, tell the
  user `brew install jq`. The rest of the checklist still runs.
- `bd` — beads, the ticket store. Missing: `[blocked]`, tell the user
  `brew install beads`. Flux falls back to markdown tickets under
  `specs/<feature>/tickets/`, so this blocks nothing else in the checklist.
- Ticket store — `bd` present and no `.beads/` in the repo: run `bd init --skip-agents`,
  then `bd setup claude`. Keep the flag only if `bd init --help` lists it. Flux reaches
  beads through its own verbs, so the `AGENTS.md` that `bd init` writes by default would
  teach agents a workflow this harness does not use.

## 3. Status line

The script ships with the plugin. Resolve its path first — the placeholder is substituted
when this skill loads and can arrive with a trailing slash, so normalise it rather than
writing it into a config file as it stands:

```bash
STATUSLINE_PATH="$(cd "${CLAUDE_PLUGIN_ROOT}/bin" && pwd)/flux-statusline"
[ -x "$STATUSLINE_PATH" ] && echo "$STATUSLINE_PATH"
```

Both lines have to succeed before that path is written anywhere. Either one failing means
a broken install, and the item is `[blocked]` naming the path that failed.

Merge the key, never rewrite the file:

```bash
mkdir -p .claude
[ -f .claude/settings.json ] || printf '{}\n' > .claude/settings.json
jq --arg cmd "$STATUSLINE_PATH" '.statusLine = {type: "command", command: $cmd}' \
  .claude/settings.json > .claude/settings.json.new \
  && mv .claude/settings.json.new .claude/settings.json
```

`[exists]` when `.statusLine.command` already names that exact path. `[created]`
otherwise — including when it names a path from an older plugin version, which is how a
rerun repairs the line after a plugin update.

## 4. CLAUDE.md

`CLAUDE.md` already contains `<!-- flux -->`: `[exists]`, change nothing.

Otherwise append this file verbatim, creating `CLAUDE.md` first when it is absent:

    ${CLAUDE_PLUGIN_ROOT}/skills/init/claude-md-section.md

The marker pair is the only region of `CLAUDE.md` this skill owns. Text already in the
file keeps its exact wording and position.

## 5. Architecture map — existing codebases only

This item fires when the repository has more than 20 source files and `CLAUDE.md` carries
no architecture map:

```bash
git ls-files | grep -Ev '\.(md|json|lock|txt|ya?ml|toml)$' | wc -l
```

When it fires, dispatch one `Explore` subagent to read the codebase and return two things:

- A draft architecture map — the directories that carry weight, what each holds, and
  where the seams between them run.
- 5–10 glossary candidates drawn from the code's own vocabulary: words the code already
  uses for its own concepts, each with the meaning it carries in this codebase.

Show both to the user and write only what they approve: the map goes inside the flux
marker in `CLAUDE.md`, the approved terms go under `## Language` in `CONTEXT.md`. A draft
the user turns down is `[declined]`.

Below the threshold, or when the map is already there, the item is `[exists]` with the
count that decided it.

## 6. gitnexus index — an offer

Ask whether to index this repository with gitnexus, which answers code-graph questions
across it. Its licence terms are still unresolved for commercial work, so the offer
carries that caveat and `no` is the expected answer. `mcp__gitnexus__list_repos` says
whether this repository is already indexed: `[exists]` when it is, `[created]` when the
user says yes and it indexes, `[declined]` when they say no.

On yes, index with the flag that leaves the repository's agent-facing documents alone:

```bash
npx --yes gitnexus analyze --skip-agents-md
```

Without it, `analyze` appends a hundred-line block to `CLAUDE.md` and writes a root
`AGENTS.md`, which puts a second set of standing instructions beside this harness's own —
the same reason `bd init` runs with `--skip-agents` in step 2. It also installs project
skills under `.claude/skills/gitnexus/`; name those in the report so the user knows they
arrived.

## 7. Hand back

Print the report, then name the files the user may want to commit — whichever of
`CONTEXT.md`, `CLAUDE.md`, `.gitignore` and `.claude/settings.json` this run touched.
The commit is theirs to make.

## What this skill writes

`CONTEXT.md` when it is absent, `docs/adr/`, `specs/`, `.flux/handoffs/`, one
`.gitignore` line, the `statusLine` key of `.claude/settings.json`, and the
`<!-- flux -->` region of `CLAUDE.md`. Everything else in the repository is left as found.
