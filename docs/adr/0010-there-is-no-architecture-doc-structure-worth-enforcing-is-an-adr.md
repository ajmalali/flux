# 0010 — There is no architecture.md; structure worth enforcing is an ADR

Two unbuilt tickets tell an agent to reconcile a finished diff against `docs/architecture.md`
— FLX-11(f), "check the diff against docs/architecture.md and ADRs — update or flag", and
FLX-14(d), "update architecture.md for structural changes". The file does not exist, nothing
in any ticket creates it, and nothing says what it would contain. An agent told to reconcile
against a missing file notes nothing and continues, so the instruction reads as a safeguard
while having no mechanism behind it. The whole surface is three references, all of them in
beads bodies: FLX-11, FLX-14, and the ticket that raised this.

**Maintaining the document was the obvious answer and loses on currency.** It buys a real
structural check — a written statement of intended structure is the only thing a diff can
contradict — and it costs a fourth durable home against a house rule that names three plus
CLAUDE.md. That cost is payable. The one that is not: `architecture.md` describes the
present, and a description of the present is exactly the document shape that rots. A stale
one does not fail silently; it asserts things that are false, to a reader who has no cheaper
way to check. Its only consumer would be a machine reading it once per ticket close —
FLX-11's minimal-context rule deliberately excludes it from what /build loads — which is a
thin readership to keep a document honest. It would also need a ticket ahead of both
consumers just to create and seed it, since neither skill can update a file that is not
there.

**Computing it from gitnexus loses on the evidence.** The appeal is that structure is derived
rather than maintained, so nothing goes stale. Measured, it does: the flux index sits at
`1b9bfc0`, ten commits behind HEAD, and reports 0 communities and 0 processes across 45
files, because gitnexus reads code graphs and this repo is markdown and bash. Against a real
code repo it has plenty to say — kiosk indexes 175 communities and 169 processes — so the
option is not worthless, it is unevenly available, and it goes quiet in exactly the way a
missing file does. That relocates staleness into an index that fails silently rather than
removing it. It also contradicts the spec: gitnexus indexing stays optional until the
PolyForm licence question is resolved, and putting it in /build's close path makes it
mandatory for every close.

**Decided: the file does not exist, and `docs/adr/` is where enforceable structure lives.**
The close-time check in /build and /sync runs against `docs/adr/` and `CONTEXT.md` — decisions
and vocabulary. This is not a downgrade dressed as a decision: the ADRs already *are* the
structural constraints of this harness, and they say so in their filenames — determinism via
hooks not prompts, beads behind our own verbs, prime speaks to the model the statusline speaks
to the human, companion skills are vendored. A diff that violates the shape of this repo
violates one of those. What makes them the right home is that an ADR is a dated decision, not
a description: it is never stale, only superseded, and superseding it is a visible act with a
number. The rule that follows is the whole mechanism — structure worth enforcing gets written
as an ADR, and structure nobody wrote down is not yet a constraint.

Consequence: FLX-11 and FLX-14 drop the reference, and AC-11's "ADR/architecture/glossary"
becomes "ADR/glossary", since under this decision the architecture case is the ADR case.

Accepted cost: drift against structure that was never decided goes undetected, and there is
no automated moment that notices layout wandering. The intended tell is a human finding the
wandering worth objecting to, which is the same event that produces the ADR. That is slower
than a document diff and it will miss things a maintained `architecture.md` would have caught
— which is the trade, taken deliberately, in exchange for never being lied to by a stale one.
