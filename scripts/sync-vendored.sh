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
ALL_FILES=$(find "$DST/wayfinder" "$DST/to-spec" "$DST/to-tickets" "$DST/ask-matt" "$DST/review" "$DST/grill" -type f -name '*.md')
for f in $ALL_FILES; do
  rewrite 's{/mattpocock-skills:}{/flux:}g' "$f"
  rewrite 's{(?<![\w:/-])/to-spec(?![\w-])}{/flux:to-spec}g' "$f"
  rewrite 's{(?<![\w:/-])/to-tickets(?![\w-])}{/flux:to-tickets}g' "$f"
  rewrite 's{(?<![\w:/-])/wayfinder(?![\w-])}{/flux:wayfinder}g' "$f"
  rewrite 's{(?<![\w:/-])/ask-matt(?![\w-])}{/flux:ask-matt}g' "$f"
  rewrite 's{(?<![\w:/-])/code-review(?![\w-])}{/flux:review}g' "$f"
  rewrite 's{(?<![\w:/-])/grill-with-docs(?![\w-])}{/flux:grill}g' "$f"
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

wayfinder, to-spec, to-tickets, ask-matt, review (upstream: code-review) and
grill (upstream: grill-with-docs + grilling + domain-modeling as references/)
are vendored from Matt Pocock's mattpocock-skills, version $PIN_VERSION
(claude-plugins-official commit $PIN_SHA), MIT licensed — see LICENSE-mattpocock
in this directory. Local changes are limited to the namespace rewrites in
scripts/sync-vendored.sh. Re-sync only by rerunning that script deliberately.

Upstream skills referenced but NOT vendored (they resolve while the
mattpocock-skills plugin is installed, and degrade to no-ops after it retires):
/tdd, /research, /triage, /prototype, /codebase-design,
/improve-codebase-architecture, /grill-me, and — outside the grill skill —
/grilling and /domain-modeling (inside grill they are local references/). His implement and handoff are
superseded by /flux:apply and \`flux handoff\` and are rewritten accordingly.
NOTE
cp "$SRC/LICENSE" "$DST/LICENSE-mattpocock"
echo "synced from $SRC"
