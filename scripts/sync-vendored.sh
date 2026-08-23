#!/usr/bin/env bash
# Re-sync the vendored mattpocock-skills subset. Run DELIBERATELY, never from CI.
# After bumping PIN_* to a newer install, rerun and review the diff by hand.
set -euo pipefail

# Provenance pin — the installed plugin build the vendored copies come from.
PIN_VERSION="1.2.3"
PIN_SHA="2ab958093e83e0ec752e6c1c5932da465bf23e0c"   # claude-plugins-official marketplace commit
SRC="${1:-$HOME/.claude/plugins/cache/claude-plugins-official/mattpocock-skills/$PIN_VERSION}"

REPO="$(cd "$(dirname "$0")/.." && pwd)"
DST="$REPO/skills"
[ -d "$SRC/skills" ] || { echo "source not found: $SRC" >&2; exit 1; }

copy_skill() { # upstream-dir vendored-name
  local from="$SRC/skills/$1" to="$DST/$2"
  rm -rf "$to"; mkdir -p "$to"
  # SKILL.md + any support .md files; drop agents/ (OpenAI packaging, not ours)
  find "$from" -maxdepth 1 -type f -name '*.md' -exec cp {} "$to/" \;
}

copy_skill engineering/wayfinder      wayfinder
copy_skill engineering/to-spec        to-spec
copy_skill engineering/to-tickets     to-tickets
copy_skill engineering/ask-matt       ask-matt
copy_skill engineering/code-review    review
copy_skill engineering/research       research
copy_skill productivity/writing-for-agents writing-for-agents

# Kept OUT of the model-visible skill listing. The 2026-08-23 utilisation bar that
# retired the upstream plugin applies to flux's own copies too, and none of them
# clears it: research/writing-for-agents at their measured utilisation, and review
# at zero -- it had never been invoked once in 520 transcripts while costing 109
# tok/session as flux's only listed skill (see
# .flux/analysis/2026-08-23-flux-listing-utilisation.md). review's visibility was
# never chosen: it was inherited from upstream's frontmatter, which is why hiding it
# has to happen HERE and not only in the file, or the next re-sync re-lists it.
# All three stay reachable as /flux:review, /flux:research, /flux:writing-for-agents.
hide_skill() { # vendored-name — add disable-model-invocation to the frontmatter
  local f="$DST/$1/SKILL.md"
  grep -q '^disable-model-invocation:' "$f" ||
    perl -0pi -e 's{\A(---\n.*?)(\n---\n)}{$1\ndisable-model-invocation: true$2}s' "$f"
}
hide_skill review
hide_skill research
hide_skill writing-for-agents

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

# Namespace rewrites: vendored set points at itself; superseded skills point at
# their flux replacements; grill's dependencies become local reference files.
rewrite() { perl -pi -e "$1" "$2"; }
ALL_FILES=$(find "$DST/wayfinder" "$DST/to-spec" "$DST/to-tickets" "$DST/ask-matt" "$DST/review" \
                 "$DST/research" "$DST/writing-for-agents" "$DST/grill" -type f -name '*.md')
for f in $ALL_FILES; do
  rewrite 's{/mattpocock-skills:}{/flux:}g' "$f"
  rewrite 's{(?<![\w:/-])/to-spec(?![\w-])}{/flux:to-spec}g' "$f"
  rewrite 's{(?<![\w:/-])/to-tickets(?![\w-])}{/flux:to-tickets}g' "$f"
  rewrite 's{(?<![\w:/-])/wayfinder(?![\w-])}{/flux:wayfinder}g' "$f"
  rewrite 's{(?<![\w:/-])/ask-matt(?![\w-])}{/flux:ask-matt}g' "$f"
  rewrite 's{(?<![\w:/-])/code-review(?![\w-])}{/flux:review}g' "$f"
  rewrite 's{(?<![\w:/-])/grill-with-docs(?![\w-])}{/flux:grill}g' "$f"
  rewrite 's{(?<![\w:/-])/research(?![\w-])}{/flux:research}g' "$f"
  rewrite 's{(?<![\w:/-])/writing-for-agents(?![\w-])}{/flux:writing-for-agents}g' "$f"
  rewrite 's{(?<![\w:/-])/implement(?![\w-])}{/flux:apply}g' "$f"
  rewrite 's{(?<![\w:/-])/handoff(?![\w-])}{`flux handoff`}g' "$f"
done

# Inside grill's own reference files, keep the pair pointing at each other locally.
for f in "$DST"/grill/references/grilling.md "$DST"/grill/references/domain-modeling.md; do
  rewrite 's{(?<![\w:/-])/grilling(?![\w-])}{grilling.md (this file set)}g' "$f"
  rewrite 's{(?<![\w:/-])/domain-modeling(?![\w-])}{domain-modeling.md (this file set)}g' "$f"
done

# Frontmatter names must match the vendored directory names.
perl -pi -e 's{^name: code-review$}{name: review}' "$DST/review/SKILL.md"

cat > "$DST/VENDORED.md" <<NOTE
# Vendored skills

wayfinder, to-spec, to-tickets, ask-matt, review (upstream: code-review),
research, writing-for-agents, and grill (upstream: grill-with-docs + grilling +
domain-modeling as references/) are vendored from Matt Pocock's mattpocock-skills, version $PIN_VERSION
(claude-plugins-official commit $PIN_SHA), MIT licensed — see LICENSE-mattpocock
in this directory. Local changes are limited to the namespace rewrites in
scripts/sync-vendored.sh, plus the disable-model-invocation key that script adds
to research and writing-for-agents. Re-sync only by rerunning that script
deliberately.

**The upstream plugin is retired** (2026-08-23, utilisation bar — see
.flux/analysis/2026-08-23-mattpocock-utilisation-bar.md). The marketplace cache at
\`\$SRC\` survived the uninstall, so a re-sync still works today — but it is now
orphaned: nothing refreshes it, and \`claude plugin prune\` may remove it. Pass a
checkout of claude-plugins-official as \$1 rather than relying on it.

research and writing-for-agents are vendored *because* of that retirement: they
were the only upstream skills with recorded use that flux did not already carry.
They ship \`disable-model-invocation: true\` — reachable as /flux:research and
/flux:writing-for-agents, costing nothing in a session that does not call them.

Upstream skills referenced but NOT vendored — with the plugin retired these are
now dead references, kept only where rewriting them would distort Matt's text:
/tdd, /triage, /prototype, /codebase-design, /improve-codebase-architecture,
/grill-me, and — outside the grill skill — /grilling and /domain-modeling
(inside grill they are local references/). His implement and handoff are
superseded by /flux:apply and \`flux handoff\` and are rewritten accordingly.
NOTE
cp "$SRC/LICENSE" "$DST/LICENSE-mattpocock"
echo "synced from $SRC"
