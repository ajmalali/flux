#!/usr/bin/env bash
# A repo whose prefix is not FLX — `bd init -p` makes that per-repo, so nothing
# in the hooks may hardcode ours. Here the prefix is declared in the beads
# config rather than inferred from an export, which is the other place a repo
# can say it.
#
# The third commit is why the prefix is read rather than guessed: a blanket
# FOO-bar match would read its ADR and AC references as ids and let genuinely
# unlinked work go uncounted.
set -eu
export GIT_AUTHOR_NAME=flux GIT_AUTHOR_EMAIL=flux@example.com
export GIT_COMMITTER_NAME=flux GIT_COMMITTER_EMAIL=flux@example.com
git init -q -b main .
git config commit.gpgsign false
printf '.flux/\n' > .gitignore
mkdir -p .beads
cat > .beads/config.yaml <<'YAML'
# Issue prefix for this repository (used by bd init)
# Example: issue-prefix: "myproject" creates issues like "myproject-1"
issue-prefix: "ZAP"
YAML
c() { echo "$1" >> log.txt; git add -A; git commit -q -m "$1"; }
c "chore: seed the repo"
base=$(git rev-parse HEAD)
c "ZAP-m3h: work under another repo's prefix"
c "ZAP-04: and under its hand-numbered ids too"
c "chore: rework the layout (ADR-0006, AC-11)"
mkdir -p .flux
printf '{"last_synced_commit":"%s"}\n' "$base" > .flux/session.json
