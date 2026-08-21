"""Turn one Claude Code session into the numbers plan.md's targets table names.

Two sources, deliberately kept separate:

* the ``--output-format json`` result envelope, which is authoritative for cost,
  wall time and turn count (it already folds in subagents); and
* the session transcript JSONL, which is the only place per-request detail lives
  -- context size at each request, which tools were called, which failed, what
  was read twice, how many characters of Bash output came back.

Everything here is pure: it reads files and returns records. Nothing spawns a
model, so the whole module is unit-testable against fixture transcripts.
"""

from __future__ import annotations

import glob
import json
import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

# Relative token prices, identical in shape across the Claude family: output is
# 5x input, a cache write 1.25x, a cache read 0.1x. Absolute dollars come from
# the result envelope; these weights exist only to answer "what share of the
# spend went to cache writes?" without hardcoding a per-model price table.
WEIGHT_INPUT = 1.0
WEIGHT_OUTPUT = 5.0
WEIGHT_CACHE_WRITE = 1.25
WEIGHT_CACHE_READ = 0.1

PROJECTS_DIR = Path(os.path.expanduser("~/.claude/projects"))


@dataclass
class Request:
    """One assistant turn -- one request billed against the context window."""

    ts: str = ""
    model: str = ""
    input_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    output_tokens: int = 0
    sidechain: bool = False

    @property
    def context_tokens(self) -> int:
        """What the model actually had in front of it for this request.

        Cache reads count: cached context is still context. This is the number
        the 'median context / request' target is about, and reading it as
        ``input_tokens`` alone would report ~2 tokens for a fully cached turn.
        """
        return self.input_tokens + self.cache_read_tokens + self.cache_creation_tokens


@dataclass
class SessionMetrics:
    """Everything one ``claude -p`` invocation cost and did."""

    arm: str = ""
    task: str = ""
    step: int = 0
    label: str = ""
    session_id: str = ""
    transcript: str = ""
    ok: bool = True
    error: str = ""
    prompt_chars: int = 0

    wall_ms: int = 0
    api_ms: int = 0
    num_turns: int = 0
    cost_usd: float = 0.0
    permission_denials: int = 0

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0

    requests: List[Request] = field(default_factory=list)
    tool_calls: Dict[str, int] = field(default_factory=dict)
    tool_errors: int = 0
    redundant_reads: int = 0
    bash_output_chars: int = 0
    tool_result_chars: int = 0
    subagent_requests: int = 0

    # ---- derived ----------------------------------------------------------

    @property
    def total_tool_calls(self) -> int:
        return sum(self.tool_calls.values())

    @property
    def tool_error_rate(self) -> float:
        return self.tool_errors / self.total_tool_calls if self.total_tool_calls else 0.0

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_tokens
            + self.cache_creation_tokens
        )

    @property
    def weighted_units(self) -> float:
        return (
            WEIGHT_INPUT * self.input_tokens
            + WEIGHT_OUTPUT * self.output_tokens
            + WEIGHT_CACHE_WRITE * self.cache_creation_tokens
            + WEIGHT_CACHE_READ * self.cache_read_tokens
        )

    @property
    def cache_write_share(self) -> float:
        """Share of spend burned re-establishing a prompt cache rather than working."""
        units = self.weighted_units
        return (WEIGHT_CACHE_WRITE * self.cache_creation_tokens / units) if units else 0.0

    def context_percentile(self, pct: float) -> int:
        return percentile([r.context_tokens for r in self.requests if not r.sidechain], pct)

    def to_json(self) -> Dict[str, Any]:
        payload = {
            k: v
            for k, v in self.__dict__.items()
            if k != "requests"
        }
        payload["requests"] = [r.__dict__ for r in self.requests]
        payload["median_context"] = self.context_percentile(50)
        payload["p90_context"] = self.context_percentile(90)
        payload["cache_write_share"] = round(self.cache_write_share, 4)
        payload["tool_error_rate"] = round(self.tool_error_rate, 4)
        return payload

    @classmethod
    def from_json(cls, payload: Dict[str, Any]) -> "SessionMetrics":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        kwargs = {k: v for k, v in payload.items() if k in known and k != "requests"}
        obj = cls(**kwargs)
        obj.requests = [Request(**r) for r in payload.get("requests", [])]
        return obj


def percentile(values: Sequence[int], pct: float) -> int:
    """Nearest-rank percentile. Zero for an empty sample rather than an exception --
    a session that died before its first request has no context to report, and the
    report should show that as 0, not crash the whole run."""
    ordered = sorted(values)
    if not ordered:
        return 0
    if len(ordered) == 1:
        return ordered[0]
    rank = max(1, min(len(ordered), math.ceil(pct / 100.0 * len(ordered))))
    return ordered[rank - 1]


def find_transcript(session_id: str, cwd: Optional[str] = None) -> Optional[Path]:
    """Locate the JSONL Claude Code wrote for ``session_id``.

    Globs on the session id rather than reconstructing the project-directory
    slug: the slugging rule is Claude Code's, not ours, and a wrong guess would
    silently zero every per-request metric.
    """
    matches = glob.glob(str(PROJECTS_DIR / "*" / (session_id + ".jsonl")))
    if not matches:
        return None
    if cwd:
        for m in matches:
            if Path(m).parent.name.endswith(Path(cwd).name):
                return Path(m)
    return Path(matches[0])


def parse_result_envelope(payload: Dict[str, Any], into: SessionMetrics) -> SessionMetrics:
    """Fold the ``--output-format json`` envelope into ``into``.

    The envelope's ``modelUsage`` block is preferred over its top-level ``usage``
    because ``usage`` reports only the final turn, while ``modelUsage`` sums every
    model the session touched, subagents included.
    """
    into.session_id = str(payload.get("session_id", "") or "")
    into.wall_ms = int(payload.get("duration_ms") or 0)
    into.api_ms = int(payload.get("duration_api_ms") or 0)
    into.num_turns = int(payload.get("num_turns") or 0)
    into.cost_usd = float(payload.get("total_cost_usd") or 0.0)
    into.permission_denials = len(payload.get("permission_denials") or [])
    into.ok = not payload.get("is_error") and payload.get("subtype") == "success"
    if not into.ok:
        into.error = str(payload.get("api_error_status") or payload.get("terminal_reason") or "error")
    elif into.num_turns == 0 and into.cost_usd == 0.0:
        # An unresolved slash command exits with is_error=false, subtype=success,
        # zero turns and zero cost -- the CLI's "success" for a prompt that did
        # nothing at all. Trusting it would score a misconfigured arm as an
        # efficient one, which is the single most dangerous way this benchmark
        # could lie. It cost the agentos arm two silent no-op steps before this
        # check existed.
        into.ok = False
        into.error = ("no turns and no cost -- the prompt produced nothing "
                      "(usually an unresolved slash command)")

    usage = payload.get("modelUsage") or {}
    if usage:
        for stats in usage.values():
            into.input_tokens += int(stats.get("inputTokens") or 0)
            into.output_tokens += int(stats.get("outputTokens") or 0)
            into.cache_read_tokens += int(stats.get("cacheReadInputTokens") or 0)
            into.cache_creation_tokens += int(stats.get("cacheCreationInputTokens") or 0)
    else:  # pragma: no cover - only when the CLI changes shape
        u = payload.get("usage") or {}
        into.input_tokens = int(u.get("input_tokens") or 0)
        into.output_tokens = int(u.get("output_tokens") or 0)
        into.cache_read_tokens = int(u.get("cache_read_input_tokens") or 0)
        into.cache_creation_tokens = int(u.get("cache_creation_input_tokens") or 0)
    return into


def _blocks(entry: Dict[str, Any]) -> List[Dict[str, Any]]:
    content = (entry.get("message") or {}).get("content")
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def _result_text(block: Dict[str, Any]) -> str:
    content = block.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return ""


def parse_transcript(path: Path, into: SessionMetrics) -> SessionMetrics:
    """Fold per-request and per-tool detail from a transcript into ``into``.

    Redundant re-reads count only *exact repeats* of a Read on the same path in
    the same session. A second Read with a different offset is legitimate paging
    through a big file, not waste, so it is not counted.
    """
    read_paths: Dict[str, int] = {}
    tool_names: Dict[str, str] = {}

    with path.open("r", encoding="utf-8", errors="replace") as fh:
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
                usage = (entry.get("message") or {}).get("usage") or {}
                req = Request(
                    ts=str(entry.get("timestamp", "")),
                    model=str((entry.get("message") or {}).get("model", "")),
                    input_tokens=int(usage.get("input_tokens") or 0),
                    cache_read_tokens=int(usage.get("cache_read_input_tokens") or 0),
                    cache_creation_tokens=int(usage.get("cache_creation_input_tokens") or 0),
                    output_tokens=int(usage.get("output_tokens") or 0),
                    sidechain=sidechain,
                )
                into.requests.append(req)
                if sidechain:
                    into.subagent_requests += 1
                for block in _blocks(entry):
                    if block.get("type") != "tool_use":
                        continue
                    name = str(block.get("name", "?"))
                    into.tool_calls[name] = into.tool_calls.get(name, 0) + 1
                    tool_names[str(block.get("id", ""))] = name
                    if name == "Read":
                        key = json.dumps(block.get("input") or {}, sort_keys=True)
                        read_paths[key] = read_paths.get(key, 0) + 1

            elif etype == "user":
                for block in _blocks(entry):
                    if block.get("type") != "tool_result":
                        continue
                    if block.get("is_error"):
                        into.tool_errors += 1
                    text = _result_text(block)
                    into.tool_result_chars += len(text)
                    if tool_names.get(str(block.get("tool_use_id", ""))) == "Bash":
                        into.bash_output_chars += len(text)

    into.redundant_reads = sum(n - 1 for n in read_paths.values() if n > 1)
    return into


def collect(payload: Dict[str, Any], cwd: Optional[str] = None, **ident: Any) -> SessionMetrics:
    """Full metrics for one session: envelope first, transcript second."""
    m = SessionMetrics(**ident)
    parse_result_envelope(payload, m)
    if m.session_id:
        transcript = find_transcript(m.session_id, cwd)
        if transcript is not None:
            m.transcript = str(transcript)
            parse_transcript(transcript, m)
    return m
