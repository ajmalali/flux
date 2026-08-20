# 0006 — All flux artifacts under a single `.flux/` folder

Status: accepted

## Context
flux generates many artifact kinds in a target repo: research docs, plans, ADRs, per-ticket
context packs, transcripts, usage logs, caches, config. Scattering them across `docs/`,
repo root, and dot-directories pollutes the target repo's own namespace.

## Decision
Everything flux writes lives under `.flux/` at the target repo root, created by `flux init`:
committed artifacts (`flux.toml`, `research/`, `plans/`, `adr/`, `context/`) and gitignored
runtime state (`transcripts/`, `usage/`, `cache/`) with the split declared in `.flux/.gitignore`.
The flux repo itself dogfoods this layout.

## Consequences
- One namespace to find, back up, or exclude; target repos stay clean.
- Known exception: beads defaults to `.beads/` — tolerated until bd supports a custom path.
