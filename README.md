# flux

**F**ast **L**oop **U**nified e**X**ecution.

A deterministic orchestration harness around Claude Code. flux owns the full lifecycle of a
software change — persistent knowledge layer, research, planning, ticket decomposition, and a
hardened per-ticket TDD pipeline — with deterministic gates enforced by the environment, not
the model.

Status: **M0 in progress**. The executor seam and metrics store are implemented; the runner
spine, gates, and stages are not.

```sh
uv sync --all-groups
uv run flux doctor     # verify subscription auth and a clean billing environment
uv run flux metrics    # per-stage tokens, time, and gate results
```

Gates on this repo: `uv run ruff check .`, `uv run pyright`, `uv run pytest`. The live
subscription round-trip is opt-in: `FLUX_LIVE_TESTS=1 uv run pytest -m live`.

- Implementation plan (v2.1): [`.flux/plans/flux-harness/plan.md`](.flux/plans/flux-harness/plan.md)
- Mechanism design (state machine, executor, artifact handoff): [`.flux/plans/flux-harness/design.md`](.flux/plans/flux-harness/design.md)
- Architecture decisions: [`.flux/adr/`](.flux/adr/)
- Source research: [`.flux/research/`](.flux/research/)

Everything flux generates — in this repo and in target repos — lives under a single `.flux/`
folder (see ADR 0006).
