# flux

A stateful Claude Code harness: a ticket store behind flux verbs, deterministic
session prime / heartbeat / statusline, planning and build skills, and routed
subagents. The repo is both the plugin and its own marketplace.

Install:

    /plugin marketplace add ~/Dev/flux
    /plugin install flux@flux

Status line — plugins cannot install one, so add this to `~/.claude/settings.json`
yourself (`/flux-init` will automate it), pointing `command` at this repo:

    {
      "statusLine": {
        "type": "command",
        "command": "~/Dev/flux/bin/flux-statusline"
      }
    }

It renders `FLX-04 · flux · claimed · ctx 41%` — claimed ticket, worktree or repo,
ticket status, context used — and `— · flux · idle · ctx 41%` when nothing is
claimed. `jq` supplies the context percentage; without it the rest of the line
still renders and `ctx` reads 0%.

Spec: `specs/harness/spec.md`. Decisions: `docs/adr/`. Vocabulary: `CONTEXT.md`.
Design rationale: https://claude.ai/code/artifact/45b7cd63-1002-4d75-82be-5554e755ba13
