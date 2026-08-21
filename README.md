# flux

Deterministic session machinery for Claude Code, shipped as one repo that is both a
plugin and its own marketplace. flux does the parts of a working session that are
the same every time — priming, budgeted state, filtered verification, generated
handoffs — as scripts, so the model's context stays small and stable; judgment work
stays in a lean skill set.

## Install

Once per machine:

    /plugin marketplace add ajmalali/flux
    /plugin install flux@flux-market

Once per repo:

    flux init        # detects Nx / Turbo / npm / cargo / uv, writes .flux/flux.toml

## The CLI

`bin/flux` — single-file, stdlib-only Python (≥3.9), on the Bash PATH while the
plugin is enabled.

| Command | Does |
|---|---|
| `flux init` | Detect repo type, write `.flux/flux.toml` + state scaffold |
| `flux prime` | Session context pack (branch, phase, next, check cmd) — ≤2k tokens, SessionStart hook, silent no-op without `.flux/` |
| `flux state get\|set` | Tiny TOML state; writes over budget are refused |
| `flux init --scan` | Inventory prior project state (PAUL, agent-os, hand-kept STATE/ROADMAP, CLAUDE.md) — finds and sizes it, parses none of it, writes nothing |
| `flux check` | Run the repo's configured verification; print failures only; exit-code semantics |
| `flux handoff` | Deterministic, capped handoff from git status + state + commits |
| `flux run -- <cmd>` | Output filter for noisy commands: dedupe + truncate, then `--filter elide` (default, head+tail), `failures` (check's failure extractor), `tail:N`, or `raw`; default from `[run].filter` |

## Skills

Lifecycle (`/flux:plan` `audit` `apply` `wrap` `resume`) — judgment only; procedures
live in the CLI. One phase runs plan → (audit) → apply → wrap; `resume` opens the next
session from the primed pack. Iterate with `flux run --filter failures`, close with
`flux check` — nothing else counts as done. Vendored from
[mattpocock-skills](skills/VENDORED.md) (MIT):
`/flux:wayfinder` `to-spec` `to-tickets` `ask-matt` `grill` `review`.

`/flux:adopt` brings a repo in: migrates whatever knowledge it already carries into
`.flux/`, and — only if asked, only onto a clean tree — retires the old framework by
archiving it into `.flux/archive/`, never deleting. Run once per repo.

## Development

    python3 -m unittest discover -s tests

Project docs: `.flux/plans/flux-v2/` (plan, status). v1 — a full Python
orchestration harness — is archived at tag `v1-final` and `.flux/archive/v1/`.
