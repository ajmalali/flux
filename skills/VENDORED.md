# Vendored skills

wayfinder, to-spec, to-tickets, ask-matt, review (upstream: code-review) and
grill (upstream: grill-with-docs + grilling + domain-modeling as references/)
are vendored from Matt Pocock's mattpocock-skills, version 1.2.3
(claude-plugins-official commit 2ab958093e83e0ec752e6c1c5932da465bf23e0c), MIT licensed — see LICENSE-mattpocock
in this directory. Local changes are limited to the namespace rewrites in
scripts/sync-vendored.sh. Re-sync only by rerunning that script deliberately.

Upstream skills referenced but NOT vendored (they resolve while the
mattpocock-skills plugin is installed, and degrade to no-ops after it retires):
/tdd, /research, /triage, /prototype, /codebase-design,
/improve-codebase-architecture, /grill-me, and — outside the grill skill —
/grilling and /domain-modeling (inside grill they are local references/). His implement and handoff are
superseded by /flux:apply and `flux handoff` and are rewritten accordingly.
