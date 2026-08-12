# Spec: The Flux harness

Full research and design rationale: https://claude.ai/code/artifact/45b7cd63-1002-4d75-82be-5554e755ba13
Vocabulary: CONTEXT.md. Decisions: docs/adr/. Tickets: specs/harness/tickets/.

## Problem statement

AI-assisted coding sessions lose state between terminals and worktrees, burn tokens re-exploring the codebase, degrade in quality when planning conversations run long, and produce work that is hard to review. Existing systems solve fragments: PAUL has good formats but prompt-only enforcement and no routing/worktrees; mattpocock-skills has good disciplines but no deterministic state, no orchestration, and nothing advances ticket status.

## Solution

A Claude Code plugin ("flux") providing: a beads-backed ticket store wrapped behind our own verbs; three deterministic components (SessionStart prime, Stop heartbeat, statusline); eight skills (/plan, /tickets, /build, /run, /show-work, /pause, /sync, /flux:init); three routed subagents (chore/build/deep); and a plain-language output style. The repo is its own plugin and marketplace.

## User stories

1. Opening a terminal in any worktree, I see the claimed ticket, frontier, pending handoffs, and drift — without typing anything.
2. After /clear or compaction, the session re-orients automatically.
3. I plan a feature through a grilling interview that maintains the glossary, the ADRs, and a spec draft kept current at every round, so I can stop whenever I choose and lose nothing.
4. Tickets are generated in a fresh session from the spec alone, each self-contained and routed to a model tier.
5. I implement a ticket manually with /build: atomic claim, minimal context load, TDD at pre-agreed seams, Execute→Qualify per task, close with a linked commit.
6. I run the frontier automatically with /run: worktree-isolated subagents, capped concurrency, hard stops at human-verify checkpoints.
7. I review any completed ticket as a diff-scoped behavior diagram plus a plain-English summary and AC checklist.
8. I pause a long discussion and continue it in a fresh session without losing anything settled.
9. Work done without the harness is detected at the next session start and reconciled with one command.
10. On any new machine or repo, two commands install the harness and one idempotent command bootstraps the project.

## Implementation decisions

- **Layout**: `.claude-plugin/{plugin.json,marketplace.json}`, `skills/<name>/SKILL.md`, `agents/{chore,build,deep}.md`, `hooks/hooks.json`, `bin/{flux-prime,flux-heartbeat,flux-statusline}`, `output-styles/flux.md`.
- **Hook scripts**: bash + jq. Must complete <500ms and always exit 0 (ADR-0001, fail-open). Paths in hooks.json use `${CLAUDE_PLUGIN_ROOT}`. Verify current hook/statusline JSON schemas against https://code.claude.com/docs/en/hooks and /statusline docs at implementation time — do not trust remembered field names.
- **Ticket store**: beads behind create/ready/claim/close verbs (ADR-0002). Pre-beads fallback (used for these very tickets): markdown files with YAML frontmatter in `specs/<feature>/tickets/`, `status:` field advanced in place.
- **Ticket format**: frontmatter `id/title/status/agent/effort/blockers/checkpoint`; body sections Context, Tasks (each task = Files / Action / Verify / Done), Test plan, Boundaries. Routing by complexity score: ≤3 → chore, 4–7 → build, ≥8 → deep.
- **Skills**: `skills/<name>/SKILL.md`, authored per the `writing-for-agents` conventions (an authoring habit, read before writing one — not a runtime dependency). User-invoked skills set `disable-model-invocation: true`. Skills are composed by reference and never restated inside another skill's body; the composed skills — grilling, domain-modeling, prototype, tdd, codebase-design — ship in this plugin and are invoked as `flux:<name>` (ADR-0009, `skills/NOTICE.md`).
- **Session split**: ADR-0003 — /tickets refuses a polluted window.
- **State files**: `.flux/session.json` (heartbeat every turn, prime at session start — ADR-0005; both through `session_stamp`, which merges), `.flux/handoffs/*.md` (residue only). `.flux/` is gitignored. Durable knowledge only in CONTEXT.md, docs/adr/, specs/, CLAUDE.md.

## Testing decisions

- Hook scripts: fixture JSON piped to stdin, exact-output assertions, plus a malformed-input case proving exit 0. Runner: `tests/run.sh` (plain bash, no framework). All scripts pass `shellcheck`.
- Skills: verified by dogfooding — each skill ticket's verify step is a live run on this repo or a sandbox repo.
- Plugin: validates by installing from the local marketplace path.

## Acceptance criteria

- AC-1: New session shows primed state (ticket, frontier, handoffs, drift) with no user action.
- AC-2: Prime re-fires after /clear and after compaction.
- AC-3: Heartbeat writes .flux/session.json every turn, <500ms, never blocks.
- AC-4: Statusline renders `<ticket>-<state> · <branch> · ctx N% · <tokens>` — the claimed ticket, else the last completed one (ADR-0006), else `no tickets`; plus a `⚠ N drift` segment when, and only when, there is drift, and a trailing verb (`/pause`, `/sync`) when a condition warrants one — at most one, never in the steady state (ADR-0007 — the primed block is invisible to the human, so anything needing human action goes here, and prime asks the model to relay the rest).
- AC-5: All hook scripts exit 0 on malformed input, missing bd, missing .flux.
- AC-6: /plan writes each settled section into specs/<slug>/spec-draft.md in the round it settles, and gives one notice at 200k and one at 350k without stopping the run on its own; the run ends with an approved spec.md, or — when the user calls a pause or context pressure forces one — a draft plus handoff.
- AC-7: /tickets refuses a polluted window; every ticket carries routing, F/A/V/D tasks, test plan, boundaries, blockers.
- AC-8: /build claims atomically, closes with a commit referencing the ticket id; 3 failed qualify cycles escalate classified (intent/spec/code).
- AC-9: /show-work artifact: one diagram ≤12 nodes scoped to the diff, ≤5-sentence summary, AC checklist with verify commands.
- AC-10: /pause deposits settled knowledge into durable homes before writing residue; prime surfaces the handoff next session.
- AC-11: /sync creates retroactive closed tickets for unattributed commits and flags ADR/architecture/glossary contradictions.
- AC-12: /run caps concurrency at 3, blocks at checkpoints, tags failures without retrying.
- AC-13: Fresh repo: marketplace add + install + /flux:init yields all of the above; second /flux:init run is a no-op.
- AC-14: plugin.json and marketplace.json validate; bin scripts pass shellcheck.

## Out of scope

- Support for other harnesses (Codex, opencode) — PAUL's portability trap; revisit only if needed.
- Our own MCP server, BASE, Task Master, kanban UIs.
- Team/multi-user features, Jira/Linear backends.
- Automated retry of failed tickets in /run.

## Further notes

- Once FLX-05 (foundation checkpoint) passes, optionally import remaining open tickets into beads and continue via /build itself.
- The gitnexus license question (PolyForm Noncommercial vs commercial zaps work) must be resolved before /flux:init advertises gitnexus indexing as a default step; until then it is offered as optional.
