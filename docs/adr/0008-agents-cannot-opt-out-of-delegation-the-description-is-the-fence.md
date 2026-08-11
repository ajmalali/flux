# 0008 — Subagents cannot opt out of model invocation; the description is the only fence

FLX-06 specified `disable-model-invocation: true` on all three routing agents, carrying
over the rule the spec sets for user-invoked skills. No such field exists for subagents.
The documented frontmatter (https://code.claude.com/docs/en/sub-agents, re-read
2026-08-11) is `name`, `description`, `tools`, `disallowedTools`, `model`,
`permissionMode`, `maxTurns`, `skills`, `mcpServers`, `hooks`, `memory`, `background`,
`effort`, `isolation`, `color`, `initialPrompt` — and `permissionMode` and `hooks` are
ignored for plugin subagents anyway. `disable-model-invocation` is a skills-and-commands
boolean; on an agent it is an unknown key, not a switch. The only real off-switches are
blunt and live in settings, not in the plugin: `permissions.deny` on `Agent(chore)` for
one agent, or on `Agent` for all of them.

Decided: ship the three agents with `name`/`description`/`model`/`effort` only, and let
the description do the fencing — each one opens by naming the ticket tier it implements
and closes with "not a general-purpose worker", and none of them says "use proactively".
Rejected: a `permissions.deny` entry, because /run (FLX-15) dispatches these agents by
the ticket's `agent:` field and a deny rule would break the thing they exist for. The
residual risk is accepted and small: a stray delegation gets an agent that immediately
asks which ticket it is implementing.

Consequence for verification: `claude plugin validate . --strict` at the repo root
validates the *marketplace* manifest and never looks at `agents/`. Only
`claude plugin validate .claude-plugin/plugin.json` walks the components. It earns its
place — it caught what a human reviewer would not have: an unquoted `description`
containing `` `agent: chore` `` is invalid YAML, and the reported consequence is that
"at runtime this agent loads with empty metadata (all frontmatter fields silently
dropped)". A routing agent that loses its `model:` still runs; it just stops routing.
Quote any frontmatter value containing a colon, and validate the plugin manifest — not
only the marketplace — after touching any component.
