# 0011 — The agent supplies prose; a script performs the act

Three tickets state the same split in their own words and none of them name it. FLX-amg
denies the agent `git commit` because "the commit is machinery, and the agent's only
contribution is the message text". FLX-a4g builds that machinery and invents `.flux/commit-msg`
to carry the text across. FLX-0jn is the identical sentence one level up — the agent fills a
PR body, a script runs `gh pr create --body-file`. Written three times, named zero times, which
is how the fourth instance invents a fourth convention.

ADR-0001 already says determinism lives in hooks and CLIs, never in prompts, but it is about
*state*: injection, heartbeat stamps, claims — things the model should not have to discover.
This is the same principle pointed at the model's *output*, and it needs saying separately
because the enforcement is different. Nobody has to be stopped from re-deriving state; they
have to be stopped from running `git commit`.

**Decided: where an act has a checkable shape, the agent writes prose into a named slot and a
script performs the act.** The shape is one shape, deliberately: the agent writes a text
artifact to a known path under `.flux/`; a hook fires on a trigger command; a script validates
the artifact's *form* — subject length, required sections, trailers — performs the act, prints
what it did and what it declined to do, and deletes the slot. Every path exits 0, per ADR-0001.
`.flux/commit-msg` consumed on a successful `bd close` is the first instance; the PR body is
the second. Slot read, form validation and reporting belong in `bin/flux-common` once, so the
second instance is a caller rather than a copy.

**Rejected: beads' own workflow machinery.** `bd formula` / `bd cook` / `bd mol` (bd 1.2.1,
checked 2026-08-14) look like the answer and are not. They are a ticket-graph templating
system: a formula's `Step` "defines a work item to create when the formula is instantiated",
and `pour`/`wisp` turn steps into real or ephemeral beads. Nothing in the eighteen declared
structs executes a command. `bd gate`, the closest candidate, is a *wait* condition in five
flavours — `human` waits for a manual close, `timer` for a timeout, `gh:run` and `gh:pr` for
GitHub, `bead` for another bead. None of it can stage a commit or open a PR, so adopting it
buys no determinism, and it would cost the ADR-0002 fence: four verbs, chosen because beads is
young and has already broken once, exchanged for a dependency on its newest surface. The narrow
place formulas would genuinely fit is `/flux:tickets` emitting a repeated ticket skeleton — but
a flux ticket body is almost entirely judgment prose, and formulas template structure. That is
a separate question and does not need answering here.

**The boundary is the load-bearing half: scriptify the act, never the decision.** FLX-a4g found
the wall while being written. Deriving a staging set from a ticket's `Files:` lines is not
mechanical — real lines say `(investigation, no edit)` and `docs/adr/ or CLAUDE.md` — so the
script intersects path-shaped tokens with what git reports as changed, and leaves anything
ambiguous dirty and printed. That intersection is a *compensation* for a script that cannot
judge, not an example of the pattern working. A script that begins inferring intent is a prompt
with worse ergonomics and no transcript. When the act has no checkable shape, it stays with the
agent.

Enforcement is FLX-amg and is not optional to the decision: without a fail-closed deny the
agent runs `git commit` by hand and the slot rots unread. That guard is why this pattern is a
constraint rather than a preference, and why it ships opt-in per repo rather than plugin-wide.

Accepted cost, stated plainly because the obvious defence of this ADR is the wrong one: **it
does not save tokens.** The commit dance it removes is a few thousand input tokens at the very
end of a session, which is the cheapest position in the window; FLX-amg's other rule, `--json`
on every beads read, costs *more* than the clipped rendering it replaces; and each guard denial
burns a turn until the skills learn to write the slot first. Net, roughly flat. The real return
is variance — FLX-10's session swept an unrelated `CLAUDE.md` edit into its commit, and the
sessions this prevents are the ones spent undoing that. Anyone reaching for this pattern to
reduce token spend should reach for subagent dispatch or `/pause` instead.
