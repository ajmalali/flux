#!/usr/bin/env bash
# The citation is only worth pinning as a pair, so this case pins both halves.
# The runner's exact stdout diff is the first half — listed handoff, citation
# printed, once. This is the second: consume the handoff and the citation goes
# with it, because an obligation printed with nothing to attach it to is noise
# in every session that has no handoff at all.
# shellcheck source=/dev/null
. "$TESTS_ROOT/lib.sh"

rm -f .flux/handoffs/2026-08-14-payments.md
out=$(rerun)

case "$out" in
  *"skills/pause/SKILL.md"*) fail "citation printed with no handoff listed" ;;
esac
# Prime still has something to say — the line above is the citation leaving with
# the handoff, not prime falling silent and passing by default.
case "$out" in
  *"Claimed: FLX-20"*) ;;
  *) fail "block missing after the handoff was consumed" ;;
esac

finish
