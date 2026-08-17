# 0006 — All gus artifacts under a single `.gus/` folder

Status: accepted

## Context
gus generates many artifact kinds in a target repo: research docs, plans, ADRs, per-ticket
context packs, transcripts, usage logs, caches, config. Scattering them across `docs/`,
repo root, and dot-directories pollutes the target repo's own namespace.

## Decision
Everything gus writes lives under `.gus/` at the target repo root, created by `gus init`:
committed artifacts (`gus.toml`, `research/`, `plans/`, `adr/`, `context/`) and gitignored
runtime state (`transcripts/`, `usage/`, `cache/`) with the split declared in `.gus/.gitignore`.
The gus repo itself dogfoods this layout.

## Consequences
- One namespace to find, back up, or exclude; target repos stay clean.
- Known exception: beads defaults to `.beads/` — tolerated until bd supports a custom path.
