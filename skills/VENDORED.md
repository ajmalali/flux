# Vendored skills

grill (upstream: grill-with-docs + grilling + domain-modeling as references/) is
vendored from Matt Pocock's mattpocock-skills, version 1.2.3
(claude-plugins-official commit 2ab958093e83e0ec752e6c1c5932da465bf23e0c), MIT licensed — see LICENSE-mattpocock
in this directory. Local changes are limited to the namespace rewrites in
scripts/sync-vendored.sh. Re-sync only by rerunning that script deliberately.

It is the sole survivor: loop phase 07 (2026-09-07) deleted the seven other vendored
skills on the zero-use bar — none had been invoked in the fleet corpus, and the
upstream plugin they came from was already retired (2026-08-23, utilisation bar — see
.flux/analysis/2026-08-23-mattpocock-utilisation-bar.md). Their names, bodies, and the
earlier visibility narrative remain recoverable in git history, that analysis file,
and .flux/plans/loop/07-deletions.md.

**The upstream plugin is retired.** The marketplace cache at `$SRC` survived the
uninstall, so a re-sync still works today — but it is now orphaned: nothing refreshes
it, and `claude plugin prune` may remove it. Pass a checkout of
claude-plugins-official as $1 rather than relying on it.

Upstream skills referenced by grill but NOT vendored as their own directories:
/grill-me, and — outside the grill skill — /grilling and /domain-modeling (inside
grill they are local references/). His implement and handoff are superseded by
/flux:apply and `flux handoff` and are rewritten accordingly.
