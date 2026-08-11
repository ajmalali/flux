# flux

This repo is the flux harness: a Claude Code plugin that is simultaneously its own
marketplace. It is built by dogfooding its own conventions, one ticket at a time.

## Where things live

- Spec and acceptance criteria: `specs/harness/spec.md`
- Tickets: `specs/harness/tickets/NN-*.md` — frontmatter `status` advanced in place (pre-beads store)
- Decisions: `docs/adr/` — read before changing anything they cover
- Glossary: `CONTEXT.md` — use those terms exactly; they are opinionated
- Plugin: `.claude-plugin/`, `skills/`, `agents/`, `hooks/hooks.json`, `bin/`, `output-styles/`, `tests/`

## Working rule

One ticket per fresh session (ADR-0003). The next ticket is the lowest-numbered one
with `status: open` whose blockers are all `status: done`:

    grep -l 'status: open' specs/harness/tickets/*.md | head -3

Work only within that ticket's Tasks and Boundaries, run each task's Verify command
fresh, then set its frontmatter to `status: done`. Ticket frontmatter is the source of
truth for progress — nothing else tracks it.

## Verification

- Manifests: `claude plugin validate . --strict` — this checks the *marketplace* only.
  After touching any component, also run `claude plugin validate
  .claude-plugin/plugin.json`, which walks skills, agents and hooks (ADR-0008)
- Tests: `bash tests/run.sh` (runner is created by FLX-02)
- Hook and bin scripts must pass `shellcheck`, complete in <500ms, and exit 0 on
  malformed input, missing `bd`, or missing `.flux/` (ADR-0001, fail-open)
- The plugin is installed from this path as `flux@flux` (user scope); after adding
  components, `/reload-plugins` picks them up without a restart

## House rules

- Fetch current Claude Code docs (hooks, statusline, plugin schemas) before writing
  JSON or hook scripts — field names change; do not write them from memory
- `.flux/` is machine state and gitignored; durable knowledge goes only in
  `CONTEXT.md`, `docs/adr/`, `specs/`, or this file
