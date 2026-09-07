#!/usr/bin/env bash
# Re-sync the vendored mattpocock-skills subset. Run DELIBERATELY, never from CI.
# After bumping PIN_* to a newer install, rerun and review the diff by hand.
#
# As of loop phase 07 (2026-09-07) grill is the ONLY vendored skill left — the seven
# other vendored skills were deleted on the zero-use bar (see git history and
# .flux/plans/loop/07-deletions.md). This script now wires grill and nothing else; it
# recreates none of the deleted directories.
set -euo pipefail

# Provenance pin — the installed plugin build the vendored copies come from.
PIN_VERSION="1.2.3"
PIN_SHA="2ab958093e83e0ec752e6c1c5932da465bf23e0c"   # claude-plugins-official marketplace commit
SRC="${1:-$HOME/.claude/plugins/cache/claude-plugins-official/mattpocock-skills/$PIN_VERSION}"

REPO="$(cd "$(dirname "$0")/.." && pwd)"
DST="$REPO/skills"
[ -d "$SRC/skills" ] || { echo "source not found: $SRC" >&2; exit 1; }

# grill = the grill-with-docs wrapper + its two dependencies as local references
rm -rf "$DST/grill"; mkdir -p "$DST/grill/references"
cat > "$DST/grill/SKILL.md" <<'GRILL'
---
name: grill
description: A relentless interview to sharpen a plan or design, which also creates docs (ADR's and glossary) as we go.
disable-model-invocation: true
---

Run a grilling session as specified in [references/grilling.md](references/grilling.md),
using the domain-modeling method in [references/domain-modeling.md](references/domain-modeling.md)
(its ADR and CONTEXT formats are in the same directory).
GRILL
cp "$SRC/skills/productivity/grilling/SKILL.md"       "$DST/grill/references/grilling.md"
cp "$SRC/skills/engineering/domain-modeling/SKILL.md" "$DST/grill/references/domain-modeling.md"
cp "$SRC/skills/engineering/domain-modeling/ADR-FORMAT.md"     "$DST/grill/references/"
cp "$SRC/skills/engineering/domain-modeling/CONTEXT-FORMAT.md" "$DST/grill/references/"

# Namespace rewrites: grill's grill-with-docs entrypoint and its local references.
rewrite() { perl -pi -e "$1" "$2"; }
for f in $(find "$DST/grill" -type f -name '*.md'); do
  rewrite 's{/mattpocock-skills:}{/flux:}g' "$f"
  rewrite 's{(?<![\w:/-])/grill-with-docs(?![\w-])}{/flux:grill}g' "$f"
  rewrite 's{(?<![\w:/-])/implement(?![\w-])}{/flux:apply}g' "$f"
  rewrite 's{(?<![\w:/-])/handoff(?![\w-])}{`flux handoff`}g' "$f"
done

# Inside grill's own reference files, keep the pair pointing at each other locally.
for f in "$DST"/grill/references/grilling.md "$DST"/grill/references/domain-modeling.md; do
  rewrite 's{(?<![\w:/-])/grilling(?![\w-])}{grilling.md (this file set)}g' "$f"
  rewrite 's{(?<![\w:/-])/domain-modeling(?![\w-])}{domain-modeling.md (this file set)}g' "$f"
done

cat > "$DST/VENDORED.md" <<NOTE
# Vendored skills

grill (upstream: grill-with-docs + grilling + domain-modeling as references/) is
vendored from Matt Pocock's mattpocock-skills, version $PIN_VERSION
(claude-plugins-official commit $PIN_SHA), MIT licensed — see LICENSE-mattpocock
in this directory. Local changes are limited to the namespace rewrites in
scripts/sync-vendored.sh. Re-sync only by rerunning that script deliberately.

It is the sole survivor: loop phase 07 (2026-09-07) deleted the seven other vendored
skills on the zero-use bar — none had been invoked in the fleet corpus, and the
upstream plugin they came from was already retired (2026-08-23, utilisation bar — see
.flux/analysis/2026-08-23-mattpocock-utilisation-bar.md). Their names, bodies, and the
earlier visibility narrative remain recoverable in git history, that analysis file,
and .flux/plans/loop/07-deletions.md.

**The upstream plugin is retired.** The marketplace cache at \`\$SRC\` survived the
uninstall, so a re-sync still works today — but it is now orphaned: nothing refreshes
it, and \`claude plugin prune\` may remove it. Pass a checkout of
claude-plugins-official as \$1 rather than relying on it.

Upstream skills referenced by grill but NOT vendored as their own directories:
/grill-me, and — outside the grill skill — /grilling and /domain-modeling (inside
grill they are local references/). His implement and handoff are superseded by
/flux:apply and \`flux handoff\` and are rewritten accordingly.
NOTE
cp "$SRC/LICENSE" "$DST/LICENSE-mattpocock"
echo "synced from $SRC"
