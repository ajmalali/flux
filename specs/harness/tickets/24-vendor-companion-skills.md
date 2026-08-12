---
id: FLX-24
title: flux ships its own copies of the skills it composes
status: done
agent: build
effort: medium
blockers: [FLX-01]
checkpoint: none
---
Spec: specs/harness/spec.md (implementation decisions, Skills bullet — this ticket amends it).

## Context
Flux skills compose five skills that today live in the `mattpocock-skills` plugin: grilling
and domain-modeling and prototype (invoked by /plan), tdd (invoked by /build), and
codebase-design (referenced from tdd's own body). Nothing makes a user have them. The
manifest answer — a `dependencies` entry naming `mattpocock-skills@claude-plugins-official`
plus `allowCrossMarketplaceDependenciesOn` in our marketplace — works, but it disables the
entire harness with `dependency-unsatisfied` whenever the dependency is missing or its
marketplace was never added. Carrying our own copies removes the failure mode and lets flux
own the conventions domain-modeling writes into, which are the same CONTEXT.md and
docs/adr/ this harness already has opinions about. Upstream is MIT, © 2026 Matt Pocock.

Verbatim copies in this ticket. Reconciling their vocabulary with CONTEXT.md is later work,
and it stays legible only if the copies start out diffable against upstream.

## Tasks
1. Files: docs/adr/0009-companion-skills-are-vendored.md
   Action: record the reversal — flux ships copies rather than depending on the plugin.
   State the rejected alternative (cross-marketplace `dependencies`) with the reason it
   loses: an unresolved dependency disables prime, heartbeat, statusline and every skill,
   not just the one that needed it. State the accepted cost: upstream improvements arrive
   only through a deliberate re-sync, and nothing reminds us.
   Verify: `ls docs/adr/0009-*`
   Done: ADR carries decision, rejected alternative, and accepted cost.
2. Files: specs/harness/spec.md
   Action: rewrite the Skills bullet under implementation decisions. Skills are composed by
   reference and never restated inside another skill's body — that rule stands. What changes
   is where the composed skills come from: this plugin, per ADR-0009.
   Verify: `grep -rn 'installed mattpocock-skills' specs/` returns nothing
   Done: no line in specs/ tells a skill to invoke something flux does not ship.
3. Files: skills/grilling/, skills/domain-modeling/, skills/prototype/, skills/tdd/,
   skills/codebase-design/, skills/NOTICE.md
   Action: copy each directory byte-for-byte from mattpocock-skills 1.2.3, sibling
   reference files and `agents/openai.yaml` included, so a future re-sync is a diff rather
   than a reconstruction. Frontmatter `name` keeps its upstream value; the skills resolve
   as `flux:<name>`. NOTICE.md carries the MIT licence text, the copyright line, the
   upstream version each copy came from, and the command that fetches a newer one.
   Verify: `claude plugin validate .claude-plugin/plugin.json`, then `/reload-plugins`
   Done: five skills load under the flux namespace; NOTICE.md names version 1.2.3.
4. Files: skills/plan/SKILL.md
   Action: repoint the three invocations from `mattpocock-skills:<name>` to `flux:<name>`.
   Verify: `grep -rn 'mattpocock-skills' skills/` matches only NOTICE.md
   Done: /plan invokes only skills this plugin ships.

## Test plan
Task 3's verify, then the real proof: `claude plugin disable
mattpocock-skills@claude-plugins-official`, open a fresh session, run /flux:plan far enough
to reach the first grilling round. It reaches it. Re-enable afterwards. Edge: both plugins
enabled at once — two `grilling` skills exist, namespaces keep them apart, and /plan reaches
the flux one.

## Boundaries
No edits to the vendored bodies. They still say `/codebase-design` and `/prototype` in
their own voice and still describe CONTEXT.md in their own format; reconciling that with
this repo's glossary is a separate ticket and a separate commit. Do not add a
`dependencies` entry to plugin.json. Do not vendor the other twenty skills in that plugin —
only what a flux skill actually invokes.
