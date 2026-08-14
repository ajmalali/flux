# 0012 — Guard hooks fail closed, and therefore ship opt-in per repo

ADR-0001 says a hook script that fails must fail open — exit 0, empty output — so the
harness degrades to plain Claude Code and never blocks it. `bin/flux-guard` denies Bash
calls. A guard that fails open is not a guard, so this is a real departure and needs
saying out loud rather than being read as a violation.

**Decided: flux ships two kinds of hook, and they are scoped differently.**

*State hooks* — prime, the heartbeat — are plugin-scoped in `hooks/hooks.json` and active
for anyone who installs flux. That is safe because the whole of what they do is stamp a
gitignored JSON file. They fail open in the full sense of ADR-0001: every failure mode
degrades to a session that is merely unprimed.

*Guard hooks* — flux-guard, and anything that denies after it — are project-scoped,
opt-in, and fail closed. They ship in `bin/` with the plugin but are registered by
`/flux:init` into the target repository's own `.claude/settings.json`, after asking, the
way `gitnexus-reindex` is already wired in this repo. A fail-closed deny cannot arrive
plugin-scoped: someone who installed flux for the status line would find `git commit`
blocked by a plugin update they did not read, in a repo that never agreed to the rule.
Opt-in per repo, declinable at init, visible in the init report, and removable by deleting
one key from a file the repo owns. `tests/run.sh` asserts flux-guard's *absence* from
`hooks/hooks.json`, so a later session that reads that absence as an oversight gets a
failing test instead of a comment.

**Failing closed is a promise about the denials, not about the script.** Every path in
flux-guard still exits 0, and silence is still an allow: no jq, an unreadable event, a
tool that is not Bash, a command that matches nothing — all allow. What "fail closed"
buys is that a *positive match* is refused rather than warned about. The script can only
ever deny work it recognised; it can never deny work because it broke.

**Accepted cost: a guard that is wrong blocks legitimate work,** and that cost is paid in
a currency the user notices immediately. Three things hold it down. The match is positive
only — nothing is denied by falling through. The denied set is closed and small: beads
reads without `--json`, and `git commit` / `git push` / `git reset --hard`. And the scan
is quote-aware and heredoc-aware rather than a grep, because `echo "git commit"` and a
heredoc that writes those words into a file both have to run. Widening the git list is the
failure mode to fear here — a guard that also blocks `git add` or `git status` makes the
harness unusable, and would be uninstalled rather than corrected.

**Not defended against: evasion.** `bash -c 'git commit …'`, `xargs`, an alias, a script
that commits internally — the scan sees the first word of each command segment and stops
there. This guard is aimed at habit, which is what actually breaks these two rules, not at
an adversary. A wrapper wide enough to catch a determined bypass would start denying
`bash tests/run.sh`, which is the same unusability by another road.

This is the enforcement leg of ADR-0011: without a fail-closed deny the agent runs
`git commit` by hand and `.flux/commit-msg` rots unread. It is also why that pattern is a
constraint rather than a preference — and why the constraint is one each repo accepts for
itself.
