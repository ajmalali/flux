# 0009 — Companion skills are vendored, not depended on

Five skills flux composes were written elsewhere: `grilling`, `domain-modeling` and
`prototype` (invoked by /plan), `tdd` (invoked by /build), and `codebase-design` (which
tdd's own body reaches for). The spec said skills are composed by reference and never
restated inside another skill's body. It did not say where the referenced skill comes
from, and the honest answer until now was "the user happens to have `mattpocock-skills`
installed" — which nothing in this plugin makes true.

The manifest answer works: a `dependencies` entry naming
`mattpocock-skills@claude-plugins-official`, plus `allowCrossMarketplaceDependenciesOn` in
our marketplace so the resolver is allowed to reach outside it. Rejected, because the
failure is not scoped to the thing that failed. An unresolved dependency — the plugin not
installed, or its marketplace never added on this machine — marks flux itself
`dependency-unsatisfied` and takes the whole harness down with it: prime, heartbeat, the
statusline, `/flux:build`, every skill, including the ones that never touch grilling. A
missing interview discipline should cost the interview, not the session-start stamp.

Decided: flux ships its own copies. `skills/{grilling,domain-modeling,prototype,tdd,
codebase-design}/` are byte-for-byte copies of mattpocock-skills 1.2.3, sibling reference
files and `agents/openai.yaml` included; frontmatter `name` keeps its upstream value, so
they resolve as `flux:grilling` and friends and namespacing keeps them distinct from the
originals when both plugins are enabled. `skills/NOTICE.md` carries the MIT licence, the
copyright line, the version each copy came from, and the commands that fetch a newer one.
There is no `dependencies` entry in plugin.json. Installing flux installs everything flux
invokes.

The second reason to carry them rather than borrow them: `domain-modeling` writes into
`CONTEXT.md` and `docs/adr/`, and this harness already has opinions about both. Owning the
copy is what makes reconciling that vocabulary a thing we can do at all. That reconciling
is deliberately *not* done here — the copies start out diffable against upstream, and
diverge later, on purpose, in their own commits.

Accepted cost: upstream improvements no longer arrive. A fix Matt ships lands in flux only
when someone deliberately re-syncs, and nothing in this repo notices a new release or
nags — NOTICE.md documents the diff commands and that is the entire mechanism. We are also
now carrying five bodies we did not write and must read before changing. Both are cheaper
than a harness that refuses to start.
