#!/usr/bin/env bash
# A repo that has never been primed: no .flux/ at all. The .git marker keeps
# root discovery from walking past the fixture into whatever contains $TMPDIR.
set -eu
mkdir -p .git
