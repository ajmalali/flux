# gus

A deterministic orchestration harness around Claude Code. gus owns the full lifecycle of a
software change — persistent knowledge layer, research, planning, ticket decomposition, and a
hardened per-ticket TDD pipeline — with deterministic gates enforced by the environment, not
the model.

Status: **planning**. Nothing is implemented yet.

- Implementation plan (v2.1): [`.gus/plans/gus-harness/plan.md`](.gus/plans/gus-harness/plan.md)
- Mechanism design (state machine, executor, artifact handoff): [`.gus/plans/gus-harness/design.md`](.gus/plans/gus-harness/design.md)
- Architecture decisions: [`.gus/adr/`](.gus/adr/)
- Source research: [`.gus/research/`](.gus/research/)

Everything gus generates — in this repo and in target repos — lives under a single `.gus/`
folder (see ADR 0006).
