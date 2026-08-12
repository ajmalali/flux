
<!-- flux -->
## flux

- Specs: `specs/<feature>/spec.md`
- Tickets: beads (`bd`), or `specs/<feature>/tickets/*.md` when beads is absent
- Decisions: `docs/adr/` — read before changing anything they cover
- Glossary: `CONTEXT.md` — use those terms exactly. A term defines a concept, not its
  address: no file paths, since a glossary outlives the layout it was written against
- Machine state: `.flux/` — gitignored, written by the hooks, never edited by hand

Durable knowledge lives only in `CONTEXT.md`, `docs/adr/`, `specs/`, or this file.

One ticket per fresh session, and ticket-writing gets a window of its own: `/flux:plan`
ends at an approved spec, `/flux:tickets` decomposes that spec in a session that has read
nothing else. `/flux:build` implements one ticket and closes it with a commit naming its
id; `/flux:show-work` reviews what a ticket actually changed.
<!-- /flux -->
