---
id: FLX-19
title: Statusline is a turn behind a claim made outside a session
status: open
agent: build
effort: low
blockers: [FLX-02, FLX-04]
checkpoint: none
---
Spec: specs/harness/spec.md (AC-3, AC-4).

## Context
Found by the human running the claim check during the FLX-05 checkpoint: claim a
ticket, open a new terminal, and prime says `Claimed: FLX-06` while the
statusline still says `FLX-05-unclaimed`. Both are reading honestly — they read
different things:

- prime scans the ticket store on every session start, so it is never stale
- the statusline reads `.flux/session.json`, which only the heartbeat writes
  (spec AC-3), and the heartbeat had not run since the claim

So the first render of every session reflects the *previous* session's last
turn. It self-corrects at the end of the first turn, which is what makes it
nasty: by the time you go looking, it is right. The window is small but it lands
exactly where trust is set — the first thing you see in a new terminal.

This is not the statusline reading the wrong file. Scanning the store on a hook
that fires on every keystroke is the thing FLX-04 deliberately refused (README:
"the frontier head is resolved by the heartbeat, not here"), and that refusal
still stands.

The cheap fix is at the other end: prime already scans the store at SessionStart
and already knows the claim. Have it stamp `claimed_ticket` and `next_ticket`
into `.flux/session.json` before it prints, and the statusline's first render is
correct with no extra work per keystroke. Note this makes prime a second writer
of a file the spec attributes to the heartbeat — deliberate, and worth recording
if it is taken.

Alternative if that is rejected: the statusline treats session.json as stale on
first render and falls back to `no tickets` rather than to a wrong ticket id. A
blank segment is a worse first frame than a correct one, so prefer the stamp.

## Tasks
1. Files: bin/flux-prime (and bin/flux-common if the write belongs there)
   Action: stamp the claim it already resolved into `.flux/session.json`,
   preserving every field it does not own — `last_synced_commit` in particular,
   which only /sync advances.
   Verify: claim a ticket with no session running, run flux-prime, then
   flux-statusline; the statusline names the claimed ticket
   Done: first render after an out-of-session claim is correct (AC-4)
2. Files: bin/flux-prime, hooks + fail-open contract
   Action: keep the write non-fatal — a read-only `.flux/`, absent jq, or
   missing session.json must still leave prime printing its block and exiting 0.
   Verify: bash tests/run.sh prime
   Done: prime exits 0 and prints normally with .flux/ unwritable (ADR-0001)
3. Files: tests/fixtures/prime/ (new case), tests/fixtures/statusline/
   Action: fixture for the claim-outside-a-session sequence, and one pinning
   fail-open when the stamp cannot be written.
   Verify: bash tests/run.sh
   Done: both cases fail against today's prime and pass after the fix

## Test plan
The regression is a sequence, not a single invocation: claim → prime → statusline
with no heartbeat in between. The prime suite drives the first two; the assertion
is on what the statusline renders from the session.json prime left behind.

## Boundaries
Do not make the statusline read the ticket store — that is the cost decision
FLX-04 made on purpose. Do not touch `last_synced_commit`; it belongs to /sync
(FLX-14). If prime becomes a writer of session.json, add the ADR rather than
leaving the spec's "session.json (heartbeat)" line silently wrong.
