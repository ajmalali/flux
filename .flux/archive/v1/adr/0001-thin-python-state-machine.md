# 0001 — Thin Python state machine, not an orchestration framework

Status: accepted

## Context
The harness needs deterministic, resumable control flow over ~5 pipeline stages per ticket.
Candidates: plain Python, LangGraph, Temporal/Prefect/Dagster/Airflow, CrewAI/AutoGen.

## Decision
A plain Python package: a `Stage` abstraction, each stage idempotent and keyed on
`(ticket_id, stage)`, state externalized to beads + git + `.flux/` artifacts. No framework.

## Consequences
- Full control, trivially resumable, no infra, no learning curve.
- We own retry/resume logic ourselves (small, and it stays inspectable).

## Alternatives
- LangGraph: checkpointing between nodes duplicates what beads/git already provide.
- Temporal-class: server + weeks-long learning curve, justified only at multi-day mission-critical scale.
- CrewAI/AutoGen: these frameworks populate the MAST multi-agent failure dataset; simple pipelines
  (Agentless, arXiv:2407.01489) beat complex agent graphs on SWE-bench at lower cost.
