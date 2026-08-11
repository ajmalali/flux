# 0001 — Determinism lives in hooks and CLIs, never in prompts

Anything that must always happen (state injection, heartbeat stamps, ticket claims) is implemented as a hook or CLI call the model cannot skip; skills carry only judgment work. Rejected: PAUL-style prompt-level enforcement — its own issue tracker (#16) documents the model ignoring "mandatory" markdown rules. Consequence: a hook script failing must fail open (exit 0, empty output) so the harness degrades to plain Claude Code, never blocks it.
