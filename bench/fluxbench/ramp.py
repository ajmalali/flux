"""How much does a session spend before it does any work, and on what?

ADR 0001 makes `flux task` — a local execution index with a topological `next` —
answerable to one metric: the **cold-start ramp**, the tokens and tool calls before
a session's first Edit/Write. Its falsifier is stated there: *ramp does not shrink
=> the frontier was not where context went; delete it*. That metric had never been
measured, which is the same position the decay premise was in before
`.flux/analysis/2026-08-22-context-decay.md` measured it and it did not survive.

The number on its own decides nothing, so this module measures the part that does:

* **The ramp is split into what an execution index could remove and what it could
  not.** Re-reading `status.md`, a handoff, a task queue or `git log` to work out
  where the project is — that is the frontier being re-derived, and an index
  replaces it. Reading CLAUDE.md, an ADR or a spec is orientation an index does
  *not* replace, so it gets its own bucket rather than being counted for flux.
  Reading the source about to be changed is the work. A big ramp made of source
  reads falsifies `flux task` just as surely as a small ramp does.

* **Bench sessions are excluded by default.** A `claude -p` run is handed its task
  in the prompt and has no frontier to derive, so its ramp is structurally near
  zero. Mixing ~100 of those into the corpus would halve the median and flatter
  the metric. Only real interactive sessions count; `--all` overrides.

* **Sessions that never edit are reported, never imputed.** A session that answers
  a question and stops has no first Edit, so it has no ramp — counting it as zero
  or as its whole length would both be inventions.

* **`flux prime` is a natural experiment already in the corpus.** It has injected
  phase/position/next at SessionStart since 2026-08-20, which is the cheap version
  of what an index would do. Sessions either side of that date are reported
  separately: if the pack did not move the ramp, an index has to explain why it
  would.

Pure and stdlib-only: it reads JSONL and returns records. Nothing spawns a model.
"""

from __future__ import annotations

import glob
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .decay import Call, model_family, scan_transcript

EDIT_TOOLS = ("Edit", "Write", "NotebookEdit")
SEARCH_TOOLS = ("Read", "Grep", "Glob")

# --- what the ramp is made of ------------------------------------------------
#
# The distinction that decides ADR 0001: could an execution index have spared this
# call? Only *task state* -- what is done, what is next, what is blocked -- is
# replaceable by an index. Conventions, rationale and specs are not, and neither is
# reading the code. Sorting those into the frontier bucket would manufacture the
# result the ADR is being tested for, so they get a bucket of their own.
#
# Most reading on this account happens through Bash (`cat`, `sed -n`, `grep`), not
# through Read/Grep -- a global instruction tells the model to prefer the shell. A
# classifier that only looked at ``file_path`` therefore put ~3,000 orientation and
# code calls in "other". Bash is classified on its whole command line.

# Directories that exist only to carry project state across sessions.
STATE_DIRS = re.compile(
    r"[/\\]\.(?:flux|paul|agent-os|specify|kiro|openspec|taskmaster)[/\\]", re.I)
# Files that answer "what is done and what is next" -- what an index replaces.
FRONTIER_FILES = re.compile(
    r"(?:^|[/\\])(?:status|state|plans?|roadmap|todos?|backlog|handoffs?|"
    r"milestones?|progress|next|queue|tasks?|issues?)"
    r"(?:[-_.][\w-]+)*\.(?:md|toml|json|jsonl|ya?ml|txt)$", re.I)
# Orientation an index does NOT replace: conventions, rationale, what the thing is.
DOC_FILES = re.compile(
    r"(?:^|[/\\])(?:claude|agents?|readme|contributing|changelog|adrs?|"
    r"decisions?|specs?|design|architecture|notes?)"
    r"(?:[-_.][\w-]+)*\.(?:md|mdx|rst|txt)$", re.I)
DOC_DIRS = re.compile(r"[/\\](?:adrs?|docs?|decisions?|analysis)[/\\]", re.I)
# Shell that asks the repo where it is rather than doing anything to it.
FRONTIER_SHELL = re.compile(
    r"\bgit\s+(?:log|status|diff|branch|show|stash\s+list|reflog)\b"
    r"|\bgh\s+(?:pr|issue)\s+(?:list|view|status)\b"
    r"|\bflux\s+(?:prime|state|handoff)\b"
    r"|\bbd\s+(?:ready|list|show|blocked)\b",
    re.I,
)
# Shell verbs that read or search rather than execute.
READ_SHELL = re.compile(
    r"\b(?:cat|head|tail|sed|less|more|nl|bat|grep|rg|ag|find|ls|wc|awk|jq|tree|fd|diff)\b",
    re.I)
# Leading tokens that mean "run something", so a stray `grep` deeper in the line
# (inside a heredoc, say) does not turn a test run into a file read.
RUNNER = re.compile(
    r"^(?:python3?|node|npx?|pnpm|yarn|bun|pytest|uv|poetry|cargo|go|make|just|"
    r"gradle|mvn|dotnet|swift|deno|docker|brew|pip3?|ruby|bundle|rake|tsc|"
    r"eslint|prettier|jest|vitest|mkdir|rm|cp|mv|touch|chmod|open|say|curl)$", re.I)
# `cd /x && cat y` and `FOO=bar cat y` both hide the real verb behind a prefix.
_PREFIX = re.compile(r"^\s*(?:cd\s+[^&;|]+(?:&&|;)\s*|\w+=[^\s]*\s+)+")


def _lead(command: str) -> str:
    """The first token that actually does something, past `cd ... &&` and env vars."""
    stripped = _PREFIX.sub("", command.strip(), count=1).strip()
    head = stripped.split(None, 1)
    return head[0] if head else ""


def _by_target(target: str, default: str) -> str:
    if STATE_DIRS.search(target) or FRONTIER_FILES.search(target):
        return "frontier"
    if DOC_FILES.search(target) or DOC_DIRS.search(target):
        return "docs"
    return default


def classify_ramp_call(call: Call) -> str:
    """``frontier``, ``docs``, ``code`` or ``other`` for one pre-first-edit call.

    ``frontier`` is the only bucket an execution index competes with.
    """
    if call.tool == "Bash":
        command = call.arg or ""
        if FRONTIER_SHELL.search(command):
            return "frontier"
        if RUNNER.match(_lead(command)):
            return "other"
        if READ_SHELL.search(command):
            return _by_target(command, "code")
        return "other"
    if call.tool in SEARCH_TOOLS:
        return _by_target(call.path or call.arg, "code")
    return "other"


@dataclass
class Session:
    """One session's approach to its first edit."""

    session: str = ""
    project: str = ""
    date: str = ""
    model: str = ""
    total_calls: int = 0
    edited: bool = False
    ramp_calls: int = 0
    ramp_kinds: Dict[str, int] = field(default_factory=dict)
    ramp_chars: Dict[str, int] = field(default_factory=dict)
    start_context: int = 0
    edit_context: int = 0

    @property
    def family(self) -> str:
        return model_family(self.model)

    @property
    def ramp_growth(self) -> int:
        """Context pulled in between the session's first call and its first edit.

        The floor (``start_context``: system prompt, tools, CLAUDE.md, any
        SessionStart pack) is not ramp -- nothing about task ordering can remove
        it. What orientation actually cost is the growth on top of it.
        """
        return max(0, self.edit_context - self.start_context)

    @property
    def frontier_calls(self) -> int:
        return self.ramp_kinds.get("frontier", 0)

    @property
    def code_calls(self) -> int:
        return self.ramp_kinds.get("code", 0)

    @property
    def frontier_share(self) -> float:
        return self.frontier_calls / self.ramp_calls if self.ramp_calls else 0.0

    @property
    def ramp_result_chars(self) -> int:
        return sum(self.ramp_chars.values())

    @property
    def frontier_char_share(self) -> float:
        """The share that decides the ADR: not how many calls, but how much context."""
        total = self.ramp_result_chars
        return self.ramp_chars.get("frontier", 0) / total if total else 0.0


def sessions_from_calls(calls: Sequence[Call], session: str = "", project: str = "",
                        date: str = "") -> Optional[Session]:
    """Fold one transcript's calls into a :class:`Session`, or None if it had none."""
    main = [c for c in calls if not c.sidechain]
    if not main:
        return None
    out = Session(session=session or main[0].session, project=project, date=date,
                  model=main[0].model, total_calls=len(main),
                  start_context=main[0].context)
    for c in main:
        if c.tool in EDIT_TOOLS:
            out.edited = True
            out.edit_context = c.context
            break
        out.ramp_calls += 1
        kind = classify_ramp_call(c)
        out.ramp_kinds[kind] = out.ramp_kinds.get(kind, 0) + 1
        out.ramp_chars[kind] = out.ramp_chars.get(kind, 0) + c.result_chars
    if not out.edited:
        # No first edit means no ramp. Reset rather than report the whole session
        # as approach; a question-and-answer session was never approaching anything.
        out.ramp_calls = 0
        out.ramp_kinds = {}
        out.ramp_chars = {}
    return out


# --- corpus -----------------------------------------------------------------

# A `claude -p` bench session is handed its task and has no frontier to derive.
BENCH_MARKERS = ("flux-bench", "private-tmp", "scratchpad")


def is_bench(project: str) -> bool:
    return any(m in project for m in BENCH_MARKERS)


def _first_timestamp(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                ts = str(entry.get("timestamp") or "")
                if ts:
                    return ts[:10]
    except OSError:
        pass
    return ""


def scan_sessions(dirs: Sequence[str], include_bench: bool = False) -> List[Session]:
    files: List[str] = []
    for d in dirs:
        files.extend(glob.glob(os.path.join(os.path.expanduser(d), "**", "*.jsonl"),
                               recursive=True))
    out: List[Session] = []
    for f in sorted(set(files)):
        path = Path(f)
        project = path.parent.name
        if not include_bench and is_bench(project):
            continue
        s = sessions_from_calls(scan_transcript(path), project=project,
                                date=_first_timestamp(path))
        if s is not None:
            out.append(s)
    return out


# --- statistics -------------------------------------------------------------


def percentile(values: Sequence[float], pct: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return float(ordered[0])
    rank = max(0, min(len(ordered) - 1, int(round(pct / 100.0 * (len(ordered) - 1)))))
    return float(ordered[rank])


def _stats(values: Sequence[float]) -> Tuple[float, float, float]:
    return (percentile(values, 50), percentile(values, 90),
            sum(values) / len(values) if values else 0.0)


PRIME_DATE = "2026-08-20"   # flux prime started firing at SessionStart


def report(sessions: Sequence[Session], prime_date: str = PRIME_DATE) -> str:
    """Markdown answering: how big is the ramp, and how much of it is the frontier?"""
    editing = [s for s in sessions if s.edited]
    lines = ["# cold-start ramp — %d sessions, %d of which reach an edit"
             % (len(sessions), len(editing)), ""]
    if not editing:
        lines.append("No session in this corpus reached an Edit/Write. Nothing to report.")
        return "\n".join(lines)

    non_editing = len(sessions) - len(editing)
    lines += ["%d sessions never edited and are excluded from every figure below "
              "(they had no first edit to approach, so they have no ramp)."
              % non_editing, ""]

    calls = [s.ramp_calls for s in editing]
    growth = [s.ramp_growth for s in editing]
    med, p90, mean = _stats(calls)
    gmed, gp90, gmean = _stats(growth)
    lines += ["## the ramp", "",
              "| | median | p90 | mean |", "|---|---:|---:|---:|",
              "| tool calls before the first edit | %.0f | %.0f | %.1f |" % (med, p90, mean),
              "| context growth before it (tok) | %.0f | %.0f | %.0f |" % (gmed, gp90, gmean),
              "| context at the first call (tok) | %.0f | %.0f | %.0f |"
              % _stats([s.start_context for s in editing]),
              ""]
    zero = sum(1 for s in editing if s.ramp_calls == 0)
    lines += ["%d of %d editing sessions (%.0f%%) edit on their very first tool call — "
              "no ramp at all." % (zero, len(editing), zero / len(editing) * 100), ""]

    lines += ["## what the ramp is made of", "",
              "The split that decides ADR 0001.", "",
              "Counted twice, because they can disagree: a handful of calls that read "
              "a 40 KB status file costs more context than twenty greps. Tokens are "
              "estimated from tool-result bytes (tokens ~= chars/4), which is what "
              "actually lands in the window.", "",
              "| bucket | calls | % of calls | result tokens | % of tokens | can an index remove it? |",
              "|---|---:|---:|---:|---:|---|"]
    totals: Dict[str, int] = {}
    chars: Dict[str, int] = {}
    for s in editing:
        for k, n in s.ramp_kinds.items():
            totals[k] = totals.get(k, 0) + n
        for k, n in s.ramp_chars.items():
            chars[k] = chars.get(k, 0) + n
    total = sum(totals.values())
    total_chars = sum(chars.values())
    legend = {
        "frontier": "**yes** — status, plans, queues, handoffs, `git log`",
        "docs": "no — CLAUDE.md, ADRs, specs: conventions and rationale",
        "code": "no — reading the source about to be changed",
        "other": "no — builds, test runs, shell plumbing",
    }
    for kind in ("frontier", "docs", "code", "other"):
        n = totals.get(kind, 0)
        cc = chars.get(kind, 0)
        lines.append("| %s | %d | %.0f%% | %s | %.0f%% | %s |"
                     % (kind, n, n / total * 100 if total else 0,
                        "{:,}".format(cc // 4),
                        cc / total_chars * 100 if total_chars else 0, legend[kind]))
    ramping = [s for s in editing if s.ramp_calls]
    lines += ["", "Per session, the frontier share of the ramp is a median of "
                  "%.0f%% of calls and %.0f%% of result tokens."
              % (percentile([s.frontier_share for s in ramping], 50) * 100,
                 percentile([s.frontier_char_share for s in ramping], 50) * 100), ""]
    fmed, fp90, fmean = _stats([s.frontier_calls for s in editing])
    tmed, tp90, tmean = _stats([s.ramp_chars.get("frontier", 0) / 4 for s in editing])
    lines += ["**The ceiling on what `flux task` can save**, per session — an index "
              "that worked perfectly removes these and nothing else:", "",
              "| | median | p90 | mean |", "|---|---:|---:|---:|",
              "| frontier calls | %.0f | %.0f | %.1f |" % (fmed, fp90, fmean),
              "| frontier result tokens | %.0f | %.0f | %.0f |" % (tmed, tp90, tmean),
              ""]

    lines += ["## before and after `flux prime` (%s)" % prime_date, "",
              "`flux prime` already injects phase/position/next at SessionStart — the "
              "cheap version of an execution index. If it did not move the ramp, an "
              "index has to explain why it would.", "",
              "| corpus | sessions | median ramp calls | median frontier calls | median growth (tok) |",
              "|---|---:|---:|---:|---:|"]
    for label, subset in (
        ("before", [s for s in editing if s.date and s.date < prime_date]),
        ("on/after", [s for s in editing if s.date and s.date >= prime_date]),
    ):
        if not subset:
            lines.append("| %s | 0 | — | — | — |" % label)
            continue
        lines.append("| %s | %d | %.0f | %.0f | %.0f |"
                     % (label, len(subset),
                        percentile([s.ramp_calls for s in subset], 50),
                        percentile([s.frontier_calls for s in subset], 50),
                        percentile([s.ramp_growth for s in subset], 50)))
    lines.append("")

    flux_only = [s for s in editing if s.project.endswith("Dev-flux")]
    if flux_only:
        lines += ["Restricted to this repo, where prime is known to have fired "
                  "(%d sessions):" % len(flux_only), "",
                  "| corpus | sessions | median ramp calls | median frontier calls |",
                  "|---|---:|---:|---:|"]
        for label, subset in (
            ("before", [s for s in flux_only if s.date and s.date < prime_date]),
            ("on/after", [s for s in flux_only if s.date and s.date >= prime_date]),
        ):
            if not subset:
                lines.append("| %s | 0 | — | — |" % label)
                continue
            lines.append("| %s | %d | %.0f | %.0f |"
                         % (label, len(subset),
                            percentile([s.ramp_calls for s in subset], 50),
                            percentile([s.frontier_calls for s in subset], 50)))
        lines.append("")

    lines += ["## by project", "",
              "| project | sessions | median ramp | median frontier | frontier share |",
              "|---|---:|---:|---:|---:|"]
    by_project: Dict[str, List[Session]] = {}
    for s in editing:
        by_project.setdefault(s.project, []).append(s)
    for project, subset in sorted(by_project.items(), key=lambda kv: -len(kv[1]))[:12]:
        ramp_total = sum(x.ramp_calls for x in subset)
        front_total = sum(x.frontier_calls for x in subset)
        lines.append("| %s | %d | %.0f | %.0f | %.0f%% |"
                     % (project, len(subset),
                        percentile([x.ramp_calls for x in subset], 50),
                        percentile([x.frontier_calls for x in subset], 50),
                        front_total / ramp_total * 100 if ramp_total else 0))
    lines.append("")
    return "\n".join(lines)
