"""Does quality decay as context grows? Measure it, on this account's own transcripts.

ADR 0001 makes a task-size budget conditional on that premise, which had never been
checked. This module checks it, and exists so the check can be repeated every
reporting cycle rather than done once by hand.

Three things it does that a naive count gets wrong, each of which reverses the answer:

* **Most tool "errors" are permission friction, not model error.** "This command
  requires approval", "was blocked", "the user doesn't want to proceed" -- these
  measure the operator's allowlist warming up, and they cluster at the start of a
  session. Counted raw, the tool-error rate *falls* fivefold as context grows and
  looks like proof that context helps. They are classified out.

* **Naive churn is mechanically forced.** "Did this Edit touch a file already
  touched this session?" must rise with context, because the set of already-touched
  files only grows. So rework is measured against a *fixed-size window of the same
  activity*: is this file among the last K files edited (or read)? That window is the
  same size on tool call 5 and on tool call 500, so growth in it is not bookkeeping.

* **Between-session comparison confounds model and task.** Sessions that pass 200K
  are opus-family sessions doing long work; sonnet sessions never get there. So every
  headline is also reported *within session* -- each session compared against itself
  either side of a cut -- which removes model, project and difficulty in one step.

Pure and stdlib-only: it reads JSONL and returns records. Nothing spawns a model.
"""

from __future__ import annotations

import glob
import json
import math
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

# --- error classification ---------------------------------------------------
#
# Order matters: a permission refusal on an Edit also mentions the file, so the
# permission test has to run first or it lands in the memory bucket.

PERMISSION = re.compile(
    r"requires approval|was blocked|blocked by|requested permissions"
    r"|permission (?:for|to)|does(?:n't| not) want to proceed"
    r"|denied by the Claude Code|expansion obfuscation|simple_expansion|Contains brace",
    re.I,
)
# The model's picture of the tree or of a file's contents was wrong. This is the
# only class that is evidence about memory rather than about the sandbox.
MEMORY = re.compile(
    r"String to replace not found|has not been read yet|File does not exist"
    r"|EISDIR|Found \d+ matches of the string",
    re.I,
)
LIMIT = re.compile(r"exceeds maximum allowed|is not installed|InputValidationError", re.I)
EXIT = re.compile(r"^Exit code (\d+)")

EDIT_TOOLS = ("Edit", "Write", "NotebookEdit")
READ_TOOLS = ("Read",)


def classify_error(text: str, tool: str = "") -> str:
    """One of: permission, memory, limit, notfound, exit, other, unknown."""
    if not text:
        return "unknown"
    if PERMISSION.search(text):
        return "permission"
    if MEMORY.search(text):
        return "memory"
    if LIMIT.search(text):
        return "limit"
    m = EXIT.match(text.strip())
    if m:
        return "notfound" if m.group(1) in ("126", "127") else "exit"
    return "other"


def model_family(model: str) -> str:
    for fam in ("opus", "sonnet", "haiku", "fable"):
        if fam in model:
            return fam
    return model or "?"


@dataclass
class Call:
    """One tool call, with the context the model held when it issued it."""

    session: str = ""
    model: str = ""
    sidechain: bool = False
    index: int = 0          # position among main-chain tool calls in this session
    context: int = 0        # input + cache read + cache write, i.e. what it had in front of it
    tool: str = ""
    path: str = ""
    is_error: bool = False
    error_class: str = ""

    @property
    def family(self) -> str:
        return model_family(self.model)


# --- transcript scanning ----------------------------------------------------


def _blocks(entry: Dict) -> List[Dict]:
    content = (entry.get("message") or {}).get("content")
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def _result_text(block: Dict) -> str:
    content = block.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(p.get("text", "") for p in content if isinstance(p, dict))
    return ""


def scan_transcript(path: Path) -> List[Call]:
    """Every tool call in one session transcript, in order."""
    session = path.name[:-6] if path.name.endswith(".jsonl") else path.name
    calls: List[Call] = []
    pending: Dict[str, Call] = {}
    index = 0
    try:
        fh = path.open("r", encoding="utf-8", errors="replace")
    except OSError:
        return calls
    with fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            etype = entry.get("type")
            sidechain = bool(entry.get("isSidechain"))
            if etype == "assistant":
                message = entry.get("message") or {}
                usage = message.get("usage") or {}
                context = (int(usage.get("input_tokens") or 0)
                           + int(usage.get("cache_read_input_tokens") or 0)
                           + int(usage.get("cache_creation_input_tokens") or 0))
                model = str(message.get("model", ""))
                for block in _blocks(entry):
                    if block.get("type") != "tool_use":
                        continue
                    if not sidechain:
                        index += 1
                    inp = block.get("input") or {}
                    call = Call(
                        session=session, model=model, sidechain=sidechain,
                        index=index, context=context, tool=str(block.get("name", "?")),
                        path=str(inp.get("file_path") or inp.get("notebook_path") or ""),
                    )
                    calls.append(call)
                    pending[str(block.get("id", ""))] = call
            elif etype == "user":
                for block in _blocks(entry):
                    if block.get("type") != "tool_result":
                        continue
                    call = pending.get(str(block.get("tool_use_id", "")))
                    if call is None or not block.get("is_error"):
                        continue
                    call.is_error = True
                    call.error_class = classify_error(_result_text(block), call.tool)
    return calls


def scan_dirs(dirs: Sequence[str]) -> List[Call]:
    files: List[str] = []
    for d in dirs:
        files.extend(glob.glob(os.path.join(os.path.expanduser(d), "**", "*.jsonl"),
                               recursive=True))
    out: List[Call] = []
    for f in sorted(set(files)):
        out.extend(scan_transcript(Path(f)))
    return out


# --- rework, normalised for activity ----------------------------------------


def rework_flags(calls: Sequence[Call], tools: Sequence[str], k: int = 5) -> List[Tuple[Call, bool]]:
    """For each call on a file, was that file among the last ``k`` files this session
    touched *with the same kind of tool*?

    The window is over calls of that kind, not over wall-clock tool calls, so a
    session whose recent history is all Greps does not get an artificially low
    rework score just because no Edit could have matched.
    """
    by_session: Dict[str, List[Call]] = {}
    for c in calls:
        if c.sidechain or c.tool not in tools or not c.path:
            continue
        by_session.setdefault(c.session, []).append(c)
    out: List[Tuple[Call, bool]] = []
    for seq in by_session.values():
        history: List[str] = []
        for c in seq:
            if len(history) >= k:
                out.append((c, c.path in history[-k:]))
            history.append(c.path)
    return out


# --- statistics -------------------------------------------------------------


def wilson(k: int, n: int, z: float = 1.959964) -> Tuple[float, float]:
    """Wilson score interval. Correct at the small counts this data actually has,
    where the normal approximation would put a lower bound below zero."""
    if n <= 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def sign_test(deltas: Sequence[float]) -> Tuple[int, int, int, float]:
    """(worse, better, tied, two-sided p). Ties are dropped, as the test requires."""
    worse = sum(1 for d in deltas if d > 0)
    better = sum(1 for d in deltas if d < 0)
    tied = len(deltas) - worse - better
    n = worse + better
    if n == 0:
        return (worse, better, tied, 1.0)
    tail = sum(_comb(n, i) for i in range(max(worse, better), n + 1))
    return (worse, better, tied, min(1.0, 2.0 * tail / (2 ** n)))


def _comb(n: int, k: int) -> int:
    return math.factorial(n) // (math.factorial(k) * math.factorial(n - k))


def fisher_exact(a: int, b: int, c: int, d: int) -> float:
    """Two-sided Fisher exact p for [[a, b], [c, d]]."""
    def hyper(w: int, x: int, y: int, z: int) -> float:
        n = w + x + y + z
        lg = math.lgamma
        return math.exp(lg(w + x + 1) + lg(y + z + 1) + lg(w + y + 1) + lg(x + z + 1)
                        - lg(n + 1) - lg(w + 1) - lg(x + 1) - lg(y + 1) - lg(z + 1))
    observed = hyper(a, b, c, d)
    total = 0.0
    for w in range(0, min(a + b, a + c) + 1):
        x, y = a + b - w, a + c - w
        z = d - (a - w)
        if x < 0 or y < 0 or z < 0:
            continue
        p = hyper(w, x, y, z)
        if p <= observed * (1 + 1e-9):
            total += p
    return min(1.0, total)


def samples_needed(p1: float, p2: float, power: float = 0.8) -> int:
    """Two-proportion sample size per arm. Reported so an inconclusive result is
    stated as 'underpowered by Nx' rather than as 'no effect'."""
    if p1 == p2:
        return 0
    z_alpha, z_beta = 1.959964, {0.8: 0.8416, 0.9: 1.2816}.get(power, 0.8416)
    pbar = (p1 + p2) / 2
    num = (z_alpha * math.sqrt(2 * pbar * (1 - pbar))
           + z_beta * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2)))
    return int(math.ceil((num / (p2 - p1)) ** 2))


# --- binning and paired comparison ------------------------------------------

DEFAULT_BINS = (0, 50, 75, 100, 150, 200, 300)  # thousands of tokens


def bin_label(bins: Sequence[int], i: int) -> str:
    lo = bins[i]
    return "%d-%dk" % (lo, bins[i + 1]) if i + 1 < len(bins) else "%dk+" % lo


def bin_index(context: int, bins: Sequence[int] = DEFAULT_BINS) -> int:
    k = context / 1000.0
    for i in range(len(bins) - 1, -1, -1):
        if k >= bins[i]:
            return i
    return 0


@dataclass
class Paired:
    """One session compared against itself either side of a context cut."""

    session: str
    n_low: int
    k_low: int
    n_high: int
    k_high: int

    @property
    def delta(self) -> float:
        return self.k_high / self.n_high - self.k_low / self.n_low


def paired_sessions(rows: Sequence[Tuple[Call, bool]], cut: int, minimum: int = 5) -> List[Paired]:
    """Sessions with at least ``minimum`` observations on both sides of ``cut``."""
    by_session: Dict[str, List[Tuple[int, bool]]] = {}
    for call, flag in rows:
        by_session.setdefault(call.session, []).append((call.context, flag))
    out: List[Paired] = []
    for session, obs in sorted(by_session.items()):
        low = [f for c, f in obs if c < cut]
        high = [f for c, f in obs if c >= cut]
        if len(low) >= minimum and len(high) >= minimum:
            out.append(Paired(session, len(low), sum(low), len(high), sum(high)))
    return out


# --- rendering --------------------------------------------------------------


def _rate_table(rows: Sequence[Tuple[Call, bool]], bins: Sequence[int], minimum: int = 30) -> List[str]:
    out = ["| context | n | k | rate | 95% CI |", "|---|---:|---:|---:|---|"]
    for i in range(len(bins)):
        bucket = [(c, f) for c, f in rows if bin_index(c.context, bins) == i]
        if len(bucket) < minimum:
            continue
        k = sum(1 for _, f in bucket if f)
        lo, hi = wilson(k, len(bucket))
        out.append("| %s | %d | %d | %.2f%% | %.1f–%.1f |"
                   % (bin_label(bins, i), len(bucket), k, k / len(bucket) * 100, lo * 100, hi * 100))
    return out


def _paired_block(rows: Sequence[Tuple[Call, bool]], cut: int, minimum: int) -> List[str]:
    pairs = paired_sessions(rows, cut, minimum)
    if not pairs:
        return ["_no session has %d observations on both sides of %dk._" % (minimum, cut // 1000)]
    deltas = [p.delta for p in pairs]
    worse, better, tied, p = sign_test(deltas)
    n_low = sum(x.n_low for x in pairs)
    k_low = sum(x.k_low for x in pairs)
    n_high = sum(x.n_high for x in pairs)
    k_high = sum(x.k_high for x in pairs)
    return [
        "%d sessions span %dk. worse above: %d · better: %d · tied: %d · "
        "mean delta %+.2fpp · sign-test p=%.3f"
        % (len(pairs), cut // 1000, worse, better, tied,
           sum(deltas) / len(deltas) * 100, p),
        "",
        "pooled within those sessions: %.1f%% (%d) below → %.1f%% (%d) above · "
        "Fisher p=%.4f _(ignores session clustering, so read it as an upper bound on confidence)_"
        % (k_low / n_low * 100, n_low, k_high / n_high * 100, n_high,
           fisher_exact(k_low, n_low - k_low, k_high, n_high - k_high)),
    ]


def report(calls: Sequence[Call], family: str = "opus",
           bins: Sequence[int] = DEFAULT_BINS, cuts: Sequence[int] = (100_000, 200_000)) -> str:
    """Markdown answering: does anything get worse as context grows, and where?"""
    main = [c for c in calls if not c.sidechain]
    sessions = len(set(c.session for c in main))
    lines = ["# context vs rework — %d tool calls, %d sessions" % (len(main), sessions), ""]

    counts: Dict[str, int] = {}
    for c in main:
        if c.is_error:
            counts[c.error_class] = counts.get(c.error_class, 0) + 1
    total = sum(counts.values())
    lines += ["## what the raw error count is made of", ""]
    lines += ["| class | n | share |", "|---|---:|---:|"]
    for cls, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        lines.append("| %s | %d | %.0f%% |" % (cls, n, n / total * 100 if total else 0))
    lines += ["", "Permission and limit classes are sandbox friction, not model error, "
                  "and are excluded from every figure below.", ""]

    for title, tools, kind in (
        ("memory errors per Edit/Write call (stale string, unread file)", EDIT_TOOLS, "err"),
        ("rework: file among the last 5 files edited", EDIT_TOOLS, "rework"),
        ("re-orientation: file among the last 5 files read", READ_TOOLS, "rework"),
    ):
        if kind == "err":
            rows = [(c, c.is_error and c.error_class == "memory")
                    for c in main if c.tool in tools]
        else:
            rows = rework_flags(main, tools)
        fam_rows = [(c, f) for c, f in rows if c.family == family]
        lines += ["## %s" % title, "", "**all models**", ""]
        lines += _rate_table(rows, bins)
        lines += ["", "**%s family only** (removes the model/task confound: only "
                      "opus-family sessions exceed 200k)" % family, ""]
        lines += _rate_table(fam_rows, bins)
        for cut in cuts:
            lines += ["", "_within-session, cut at %dk:_ " % (cut // 1000)]
            lines += _paired_block(rows, cut, 5 if kind == "rework" else 15)
        lines.append("")
    return "\n".join(lines)
