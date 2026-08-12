# flux

A stateful Claude Code harness: a ticket store behind flux verbs, deterministic
session prime / heartbeat / statusline, planning and build skills, and routed
subagents. The repo is both the plugin and its own marketplace.

Install:

    /plugin marketplace add ~/Dev/flux
    /plugin install flux@flux

Status line — plugins cannot install one, so add this to `~/.claude/settings.json`
yourself (`/flux:init` will automate it), pointing `command` at this repo:

    {
      "statusLine": {
        "type": "command",
        "command": "~/Dev/flux/bin/flux-statusline"
      }
    }

It renders `FLX-04-claimed · main · ctx 41% · 83.6k` — ticket and its state,
branch, context used, tokens in the window. The first segment states a fact and
never a guess: the claimed ticket when there is one, otherwise the last ticket
finished, and `no tickets` only when the store has neither. What comes *next* is
prime's business, not this line's — ADR-0006.

    FLX-04-claimed    · main · ctx 41% · 83.6k
    FLX-11-qualifying · main · ctx 41% · 83.6k
    FLX-19-done       · main · ctx 41% · 83.6k
    no tickets        · main · ctx 41% · 83.6k
    FLX-19-done       · main · ⚠ 2 drift · ctx 41% · 83.6k · /sync
    FLX-04-claimed    · main · ctx 78% · 156k · /pause

The drift segment appears only when commits since the last `/sync` name no
ticket — work the harness has no record of. It lives here rather than in the
primed block because SessionStart output goes to the model and is never printed
in the terminal (ADR-0007), so a nudge that only prime knows about is a nudge
nobody acts on. The count is walked by the hooks, never by this script. Prime
closes its block by asking the model to relay the same state in one line at the
top of its first reply — that reply is the earliest a session can say anything,
since no turn exists until you type.

The line ends in a verb when there is one worth naming: `/pause` once the session
has spent 350k tokens or filled 75% of the window — whichever comes first, since
a share alone reads wrong on a 1M window and a count alone reads wrong on a 200k
one — and `/sync` when there is drift. At most one, ordered by what doing
nothing costs — a full window loses the session, drift only loses attribution —
and nothing at all in the steady state, because a hint that is always there
stops being read.

The state suffix is `claimed` unless a verb wrote its own `status` into
`.flux/session.json`, so a skill can show `qualifying` or `reviewing` without a
change to the script.

The ticket is resolved by the hooks, not here: the statusline runs on every event
with a 100ms budget, so it reads `claimed_ticket` and `last_done_ticket` out of
`.flux/session.json` and never touches the ticket store. The heartbeat stamps
both at the end of every turn and prime stamps them again at session start
(ADR-0005) — otherwise a ticket claimed between sessions would show up in the
primed block but not down here until the first turn ended. The branch is read out
of `.git/HEAD` rather than by running `git`, for the same reason; a detached HEAD
shows a short sha, and outside a checkout the segment falls back to the worktree
or directory name. The token count appears only once there is one — before the
first API response the segment is dropped rather than printing a zero. `jq`
supplies the percentage and token count; without it the rest of the line still
renders, `ctx` reads 0%, and the token segment is absent.

Spec: `specs/harness/spec.md`. Decisions: `docs/adr/`. Vocabulary: `CONTEXT.md`.
Design rationale: https://claude.ai/code/artifact/45b7cd63-1002-4d75-82be-5554e755ba13
