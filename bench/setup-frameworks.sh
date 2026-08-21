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
# Generated once into a scratch repo and staged, rather than run per benchmark
# run: `specify init` reaches the network, and a benchmark should not depend on
# that mid-flight. The generated tree carries no absolute paths (checked).
if command -v uvx >/dev/null 2>&1; then
  SCRATCH="$(mktemp -d)"
  ( cd "$SCRATCH" && git init -q . \
    && uvx --from specify-cli specify init --here --integration claude \
         --ignore-agent-tools --force >/dev/null 2>&1 )
  if [ -d "$SCRATCH/.claude/skills" ]; then
    rm -rf "$FRAMEWORKS/speckit"
    mkdir -p "$FRAMEWORKS/speckit"
    cp -R "$SCRATCH/.claude" "$FRAMEWORKS/speckit/.claude"
    cp -R "$SCRATCH/.specify" "$FRAMEWORKS/speckit/.specify"
    echo "  spec-kit   ok ($(du -sh "$FRAMEWORKS/speckit" | cut -f1))"
  else
    echo "  spec-kit   SKIPPED - 'specify init' produced nothing" >&2
  fi
  rm -rf "$SCRATCH"
else
  echo "  spec-kit   SKIPPED - needs uv/uvx on PATH (https://docs.astral.sh/uv/)" >&2
fi

# --- Agent OS ---------------------------------------------------------------
# Clone + project-install.sh, which is the documented path and avoids piping a
# remote script into a shell.
if git clone -q --depth 1 https://github.com/buildermethods/agent-os.git \
     "$FRAMEWORKS/agent-os-base.new" 2>/dev/null; then
  rm -rf "$FRAMEWORKS/agent-os-base"
  mv "$FRAMEWORKS/agent-os-base.new" "$FRAMEWORKS/agent-os-base"
  echo "  agent-os   ok (v$(grep '^version:' "$FRAMEWORKS/agent-os-base/config.yml" | cut -d' ' -f2))"
elif [ -d "$FRAMEWORKS/agent-os-base" ]; then
  echo "  agent-os   kept existing clone (refresh failed)" >&2
else
  echo "  agent-os   SKIPPED - clone failed" >&2
fi
rm -rf "$FRAMEWORKS/agent-os-base.new"

echo "done."
