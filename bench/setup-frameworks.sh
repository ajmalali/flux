#!/usr/bin/env bash
# Stage the third-party frameworks the benchmark compares flux against.
#
# Their payloads deliberately do NOT live in this repo: flux ships as a plugin by
# copying its whole directory, so vendoring a few hundred KB of someone else's
# framework would ride along in every install, and their licences are theirs.
# Everything lands in $FLUXBENCH_FRAMEWORKS (default ~/.flux-bench/frameworks),
# and arm specs reference it as ${FRAMEWORKS}.
#
# Run once per machine. Re-running refreshes in place.
set -uo pipefail

FRAMEWORKS="${FLUXBENCH_FRAMEWORKS:-$HOME/.flux-bench/frameworks}"
mkdir -p "$FRAMEWORKS"
echo "staging into $FRAMEWORKS"

# --- PAUL -------------------------------------------------------------------
# Copied from a repo that already has it installed; only the framework itself,
# never a project's .paul/ state (that is project content, not framework).
PAUL_SRC="${PAUL_SRC:-$HOME/Dev/zaps/kiosk}"
if [ -d "$PAUL_SRC/.claude/paul-framework" ]; then
  rm -rf "$FRAMEWORKS/paul"
  mkdir -p "$FRAMEWORKS/paul/.claude"
  cp -R "$PAUL_SRC/.claude/paul-framework" "$FRAMEWORKS/paul/.claude/paul-framework"
  cp -R "$PAUL_SRC/.claude/commands" "$FRAMEWORKS/paul/.claude/commands"
  echo "  paul       ok ($(du -sh "$FRAMEWORKS/paul" | cut -f1), from $PAUL_SRC)"
else
  echo "  paul       SKIPPED - no .claude/paul-framework under $PAUL_SRC (set PAUL_SRC=)" >&2
fi

# --- GitHub Spec Kit --------------------------------------------------------
# Installed per-repo by its own CLI at bootstrap time rather than staged here,
# because `specify init` writes into the target repo. This checks the tool exists.
if command -v uvx >/dev/null 2>&1; then
  echo "  spec-kit   uvx present (arm installs per-run via 'specify init')"
else
  echo "  spec-kit   SKIPPED - needs uv/uvx on PATH (https://docs.astral.sh/uv/)" >&2
fi

# --- Agent OS ---------------------------------------------------------------
if [ -d "$HOME/.agent-os" ]; then
  echo "  agent-os   base install present at ~/.agent-os"
else
  echo "  agent-os   SKIPPED - base install missing; see bench/README.md" >&2
fi

echo "done."
