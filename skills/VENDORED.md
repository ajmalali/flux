# Vendored skills

wayfinder, to-spec, to-tickets, ask-matt, review (upstream: code-review),
research, writing-for-agents, and grill (upstream: grill-with-docs + grilling +
domain-modeling as references/) are vendored from Matt Pocock's mattpocock-skills, version 1.2.3
(claude-plugins-official commit 2ab958093e83e0ec752e6c1c5932da465bf23e0c), MIT licensed — see LICENSE-mattpocock
in this directory. Local changes are limited to the namespace rewrites in
scripts/sync-vendored.sh, plus the disable-model-invocation key that script adds
to review, research and writing-for-agents. Re-sync only by rerunning that script
deliberately.

**The upstream plugin is retired** (2026-08-23, utilisation bar — see
.flux/analysis/2026-08-23-mattpocock-utilisation-bar.md). The marketplace cache at
`$SRC` survived the uninstall, so a re-sync still works today — but it is now
orphaned: nothing refreshes it, and `claude plugin prune` may remove it. Pass a
checkout of claude-plugins-official as $1 rather than relying on it.

research and writing-for-agents are vendored *because* of that retirement: they
were the only upstream skills with recorded use that flux did not already carry.
They ship `disable-model-invocation: true` — reachable as /flux:research and
/flux:writing-for-agents, costing nothing in a session that does not call them.

**review carries the same key since 2026-08-23**, and it is the reason no flux skill
is model-visible any more. It was flux's only listed skill, costing 109 tok in every
session, and it had never been invoked — 0 times in 520 transcripts, by the model or
the user — so the same bar that retired the upstream plugin retired the listing slot
(.flux/analysis/2026-08-23-flux-listing-utilisation.md). Note the key is *added by the
script*, not inherited: upstream code-review is model-visible, so hand-editing the file
alone would be undone by the next re-sync.

Upstream skills referenced but NOT vendored — with the plugin retired these are
now dead references, kept only where rewriting them would distort Matt's text:
/tdd, /triage, /prototype, /codebase-design, /improve-codebase-architecture,
/grill-me, and — outside the grill skill — /grilling and /domain-modeling
(inside grill they are local references/). His implement and handoff are
superseded by /flux:apply and `flux handoff` and are rewritten accordingly.
