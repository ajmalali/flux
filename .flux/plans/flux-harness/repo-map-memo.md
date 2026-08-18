# Repo-map bake-off — `repowiki map` vs Aider RepoMapper

Date: 2026-08-18 · Task: T4b (M0, ADR 0009 C2) · Decision: **adopt `repowiki map`**

ADR 0009 left the repo-map tool as "whichever ranks better on the target repo". This is that
comparison. Both tools were installed and run against two repos: **flux** itself (85 files, a real
Python import graph) and **tinylib** (the 3-file scratch target used for the M0 benchmark).

## Decision

Adopt **`repowiki map`**, invoked as a configured command (`[repo_map] command` in `flux.toml`,
default `uvx --from repowiki repowiki map`) rather than as a flux dependency.

RepoMapper is **not adoptable in its current state**. This is not a close call on output quality;
it is a question of whether the tool runs at all.

## The comparison

| | `repowiki map` 0.3.2 | RepoMapper (Cryect, HEAD 96f1e66) |
|---|---|---|
| Runs out of the box | **yes** | **no** — four separate blocking defects, below |
| LLM calls | none | none |
| Time (flux, 85 files) | **0.2 s** | 0.23 s (library API, after patching) |
| Output | ranked file list: path, PageRank score, language, line count | ranked file list **plus symbol signatures with line numbers** |
| Machine-readable | **`--format json`, prompt-ready** | prints a Python tuple `repr` to stdout |
| Ranking on flux | `errors.py` → `jsonio.py` → `executor/types.py` → `proc.py` — the four most-imported modules, correctly | every file scores exactly `1.0` |
| Maintenance | active (0.3.2, Aug 2026) | last commit 2025-09-24, and it is the commit that broke the tool |

### What is wrong with RepoMapper

Found in order while trying to get a fair reading out of it:

1. **Broken on every tree-sitter version.** Its last commit raised the floor to `tree-sitter>=0.25`
   for `QueryCursor`, but left `language.query(...)` — an API *removed* in 0.25. Below 0.25 there
   is no `QueryCursor`; at or above it there is no `Language.query`. Patched locally to
   `Query(language, text)`.
2. **The CLI prints a tuple.** `get_repo_map()` returns `(map, FileReport)` and `main` treats the
   return as a string: it prints `(None, FileReport(...))`, and `if map_content:` is true for a
   tuple whose map is `None`.
3. **`token_count(None)`** raises inside the verbose path, and the handler swallows it as
   "Error generating repository map".
4. **PageRank does not run.** The decisive one:

   ```python
   if personalization:                       # only set by --chat-files
       ranks = nx.pagerank(G, personalization=personalization, alpha=0.85)
   else:
       ranks = {node: 1.0 for node in G.nodes()}
   ```

   With no `--chat-files` — flux's case, since a ticket's map is built before any file is chosen —
   the graph is constructed and then thrown away, and every file ranks 1.0. The ordering that
   comes out is dict iteration order. The tool's entire premise is unimplemented for the default
   invocation.

   A fifth, softer problem: the tags cache memoises *failures* with no invalidation, and
   `--force-refresh` does not clear it. The first runs after each patch kept returning zero tags
   until the cache directory was deleted by hand.

Once patched around (1)–(3), the underlying extraction is good — 664 definitions and 2493
references across flux in 0.23 s, and Aider's symbol-level output is genuinely richer than a
ranked file list. That richness is worth remembering, but the honest read is that this fork is an
LLM-generated reimplementation whose author says Python is not their language, unmaintained for
eleven months, in a state where its headline feature never executes. Adopting it would mean
maintaining it.

### What is wrong with `repowiki map`

Nothing blocking, but two things flux compensates for:

- **It maps every file, not just source.** On flux it ranked `.flux/**` artifacts and `.gitkeep`
  files alongside code. flux filters `.flux/` out and over-fetches (`OVERFETCH = 3`) so the
  exclusions do not silently shrink the kept map.
- **It ranks files, not symbols.** Good enough for the context pack's job — "which files matter
  for this ticket" — but it will not answer "which functions". If flux later needs symbol-level
  maps, the thing to take is **Aider's own `repomap.py`**, not this fork.
- On a repo with no real import graph (tinylib, 3 files) everything ties at 0.541 and the ordering
  is arbitrary. Correct behaviour — there is no signal to find — but it means a map is worth
  generating only once a repo has structure.

The dependency is heavy for what it does (litellm, openai, numpy, networkx — 57 packages) because
the `map` subcommand ships inside a full wiki generator. That is why the default is `uvx`: flux
gets the ranker without taking the dependency, and the command stays configurable, so pointing at
a different ranker is a one-line config change rather than a code change.

## What was built on top

`src/flux/knowledge/repomap.py` owns the parts a bought tool cannot:

- **Cache** at `.flux/cache/repo-map.json` (gitignored), written atomically.
- **Provenance and staleness** — the git HEAD at generation time is stored, and
  `ImplementStage.hydrate` labels a map generated at a different commit as possibly out of date
  rather than presenting it as current. Stale context is the dominant residual risk (plan.md §7),
  so a map that quietly describes an older tree is worse than no map.
- **Slicing** — the cache keeps `top` (60) entries; a prompt pack carries `pack_entries` (25).
- **Failure is loud** — a ranker that cannot run raises, rather than caching an empty map that
  would later read as "this repo has no important files".
- `flux index --install-hook` writes an opt-in `post-merge` hook that regenerates the map and can
  never fail a merge.

## Revisit when

- flux needs symbol-level context (extract from Aider directly, not from RepoMapper).
- `repowiki` stops being maintained, or its `map` subcommand changes shape — the JSON parse is
  defensive but the field names are its own.
- The M2 wiki spike (OpenWiki vs deepwiki-by-cc) lands: if the chosen wiki tool also emits a
  usable ranked map, one tool may replace two.
