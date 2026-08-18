# gus

A deterministic orchestration harness around Claude Code. gus owns the full lifecycle of a
software change — persistent knowledge layer, research, planning, ticket decomposition, and a
hardened per-ticket TDD pipeline — with deterministic gates enforced by the environment, not
the model.

Status: **M0 in progress**. The executor seam and metrics store are implemented; the runner
spine, gates, and stages are not.

```sh
uv sync --all-groups
uv run gus doctor     # verify subscription auth and a clean billing environment
uv run gus metrics    # per-stage tokens, time, and gate results
```

Gates on this repo: `uv run ruff check .`, `uv run pyright`, `uv run pytest`. The live
subscription round-trip is opt-in: `GUS_LIVE_TESTS=1 uv run pytest -m live`.

- Implementation plan (v2.1): [`.gus/plans/gus-harness/plan.md`](.gus/plans/gus-harness/plan.md)
- Mechanism design (state machine, executor, artifact handoff): [`.gus/plans/gus-harness/design.md`](.gus/plans/gus-harness/design.md)
- Architecture decisions: [`.gus/adr/`](.gus/adr/)
- Source research: [`.gus/research/`](.gus/research/)

Everything gus generates — in this repo and in target repos — lives under a single `.gus/`
folder (see ADR 0006).
