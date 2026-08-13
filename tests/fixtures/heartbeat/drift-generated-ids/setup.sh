#!/usr/bin/env bash
# Both id shapes past the sync baseline. Beads names what it creates itself with
# a base36 hash — `bd init` promises FLX-<hash>, and FLX-63o is already on this
# repo's frontier — while every imported ticket still carries a hand-numbered
# FLX-09. A commit naming either one is linked work, and counting it as drift
# makes the statusline nag about a ticket that was tracked.
#
# Both hashes, on purpose: a numeric pattern matches FLX-63o by accident, since
# FLX-63 is a prefix of it. FLX-dfo is the one that tells the truth.
#
# The JSONL export is the fixture's only statement of the prefix, which is also
# what keeps ADR-0006 in the last commit from reading as an id.
set -eu
export GIT_AUTHOR_NAME=flux GIT_AUTHOR_EMAIL=flux@example.com
export GIT_COMMITTER_NAME=flux GIT_COMMITTER_EMAIL=flux@example.com
git init -q -b main .
git config commit.gpgsign false
printf '.flux/\n' > .gitignore
mkdir -p .beads
cat > .beads/issues.jsonl <<'JSONL'
{"_type":"issue","id":"FLX-63o","title":"A generated id that opens with digits","status":"open"}
{"_type":"issue","id":"FLX-dfo","title":"A generated id that opens with a letter","status":"open"}
{"_type":"issue","id":"FLX-09","title":"An id the markdown store numbered","status":"closed"}
JSONL
c() { echo "$1" >> log.txt; git add -A; git commit -q -m "$1"; }
c "chore: seed the repo"
base=$(git rev-parse HEAD)
c "FLX-63o: the id beads generated for itself"
c "FLX-dfo: and one whose hash opens with a letter"
c "FLX-09: the id the markdown store hand-numbered"
c "wip: an FLX- with no id after it, and ADR-0006 is not one either"
c "fix a typo"
mkdir -p .flux
printf '{"last_synced_commit":"%s"}\n' "$base" > .flux/session.json
