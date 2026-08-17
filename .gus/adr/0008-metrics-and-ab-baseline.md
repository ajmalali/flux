# 0008 — Metrics store + vanilla-Claude A/B baseline as P0 deliverables

Status: accepted

## Context
Every kill-switch and threshold in the plan depends on data, and the harness is a second product
for a team of one. Measuring the harness only against itself cannot detect the day it becomes
net overhead relative to vanilla Claude Code.

## Decision
- The Stage runner writes a metrics line per (ticket, stage): tokens in/out, cache read/write,
  `total_cost_usd` (estimate), wall time, gate results, retry count, exploratory-call count,
  model/effort. `gus metrics` prints the KPI report.
- Every ~10th ticket also runs through **vanilla Claude Code** (`claude -p`, no harness) with
  identical metrics recorded, maintained in a running comparison table.
- Standing kill-criterion, written in `gus.toml` and answered at every phase gate: if vanilla
  wins on cost AND quality for 3 consecutive samples, freeze harness feature work and
  investigate. Each phase gate also names which planned feature the data says to cut.

## Consequences
- No milestone advances without its metric; the harness must continuously justify itself.
- Small runner overhead (one JSONL append per stage) — negligible.
