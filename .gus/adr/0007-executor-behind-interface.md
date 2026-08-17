# 0007 — Executor behind an interface; no stage imports the SDK

Status: accepted

## Context
Claude Code absorbs harness features quarterly (native workflows, built-in worktree isolation,
subagent patterns). Parts of the Stage runner may be obsoleted; the durable value is the beads
graph, knowledge artifacts, ticket-sizing discipline, and gate suite.

## Decision
All model invocation goes through a single `Executor` protocol:
`run(pack: PromptPack, cfg: ExecConfig) -> ExecResult`. `ClaudeAgentSDKExecutor` is the first
implementation and the only module that imports `claude_agent_sdk`. Stage code depends on the
protocol only.

## Consequences
- Swapping the executor (native workflows, Gas City, another CLI agent) touches one module.
- Per-call model/effort/permission/tool config is normalized in `ExecConfig`, so routing policy
  lives in gus config, not scattered across stages.
