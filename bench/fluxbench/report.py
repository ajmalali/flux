"""Aggregate a run into the table that decides whether flux is worth keeping.

The columns are not chosen for tidiness -- they are the targets table in
`.flux/plans/flux-v2/plan.md`, plus the two axes that table takes for granted:
did the arm actually deliver the task, and how long did a human have to wait.

One rule governs the whole report: **an arm's efficiency numbers are only
reported next to its delivery rate.** Winning on tokens by not doing the work is
the failure mode this benchmark exists to make impossible to hide, so 'cheapest'
is never printed as a verdict on its own.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import metrics as M

# (key, header, unit, lower_is_better, plan.md target)
COLUMNS = [
    ("delivered", "delivered", "n/n", False, None),
    ("accept_rate", "accept", "%", False, None),
    ("cost_per_task", "$/task", "$", True, 25.0),
    ("median_context", "ctx p50", "tok", True, 80000),
    ("p90_context", "ctx p90", "tok", True, None),
    ("cache_write_share", "cache-write", "%", True, 0.15),
    ("tool_error_rate", "tool err", "%", True, 0.015),
    ("redundant_reads_per_task", "re-reads", "n", True, 1.0),
    ("bash_chars_per_task", "bash out", "chars", True, 25000),
    ("wall_per_task", "wall/task", "s", True, None),
    ("sessions_per_task", "sessions", "n", True, None),
    ("total_tokens", "tokens", "tok", True, None),
]


@dataclass
class ArmSummary:
    arm: str
    title: str = ""
    tasks: int = 0
    delivered_count: int = 0
    accept_total: int = 0
    accept_passed: int = 0
    gate_failures: int = 0
    sessions: int = 0
    failed_sessions: int = 0
    cost_usd: float = 0.0
    wall_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    tool_calls: int = 0
    tool_errors: int = 0
    redundant_reads: int = 0
    bash_output_chars: int = 0
    files_changed: int = 0
    lines_added: int = 0
    contexts: List[int] = field(default_factory=list)

    # -- derived ------------------------------------------------------------
    @property
    def delivered(self) -> str:
        return "%d/%d" % (self.delivered_count, self.tasks)

    @property
    def accept_rate(self) -> float:
        return self.accept_passed / self.accept_total if self.accept_total else 0.0

    @property
    def cost_per_task(self) -> float:
        return self.cost_usd / self.tasks if self.tasks else 0.0

    @property
    def cost_per_delivered(self) -> float:
        return self.cost_usd / self.delivered_count if self.delivered_count else float("inf")

    @property
    def median_context(self) -> int:
        return M.percentile(self.contexts, 50)

    @property
    def p90_context(self) -> int:
        return M.percentile(self.contexts, 90)

    @property
    def cache_write_share(self) -> float:
        units = (M.WEIGHT_INPUT * self.input_tokens + M.WEIGHT_OUTPUT * self.output_tokens
                 + M.WEIGHT_CACHE_WRITE * self.cache_creation_tokens
                 + M.WEIGHT_CACHE_READ * self.cache_read_tokens)
        return (M.WEIGHT_CACHE_WRITE * self.cache_creation_tokens / units) if units else 0.0

    @property
    def tool_error_rate(self) -> float:
        return self.tool_errors / self.tool_calls if self.tool_calls else 0.0

    @property
    def redundant_reads_per_task(self) -> float:
        return self.redundant_reads / self.tasks if self.tasks else 0.0

    @property
    def bash_chars_per_task(self) -> float:
        return self.bash_output_chars / self.tasks if self.tasks else 0.0

    @property
    def wall_per_task(self) -> float:
        return (self.wall_ms / 1000.0) / self.tasks if self.tasks else 0.0

    @property
    def sessions_per_task(self) -> float:
        return self.sessions / self.tasks if self.tasks else 0.0

    @property
    def total_tokens(self) -> int:
        return (self.input_tokens + self.output_tokens
                + self.cache_read_tokens + self.cache_creation_tokens)

    def value(self, key: str) -> Any:
        return getattr(self, key)


def load(records_path: Path) -> "tuple[Dict[str, Any], List[Dict[str, Any]]]":
    manifest: Dict[str, Any] = {}
    rows: List[Dict[str, Any]] = []
    with Path(records_path).open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if entry.get("type") == "manifest":
                manifest = entry
            else:
                rows.append(entry)
    return manifest, rows


def summarize(manifest: Dict[str, Any], rows: List[Dict[str, Any]]) -> List[ArmSummary]:
    titles = {a["name"]: a.get("title", a["name"]) for a in manifest.get("arms", [])}
    order = [a["name"] for a in manifest.get("arms", [])]
    summaries: Dict[str, ArmSummary] = {}

    def get(name: str) -> ArmSummary:
        if name not in summaries:
            summaries[name] = ArmSummary(arm=name, title=titles.get(name, name))
        return summaries[name]

    for row in rows:
        arm = row.get("arm")
        if not arm:
            continue
        s = get(arm)
        if row.get("type") == "session":
            if row.get("task") == "bootstrap":
                # Bootstrap is a one-off setup cost, counted in dollars and wall
                # time (an arm that needs a 10-minute install should pay for it)
                # but excluded from per-request context statistics, which are
                # about steady-state work.
                s.cost_usd += float(row.get("cost_usd") or 0.0)
                s.wall_ms += int(row.get("wall_ms") or 0)
                continue
            s.sessions += 1
            if not row.get("ok", True):
                s.failed_sessions += 1
            s.cost_usd += float(row.get("cost_usd") or 0.0)
            s.wall_ms += int(row.get("wall_ms") or 0)
            s.input_tokens += int(row.get("input_tokens") or 0)
            s.output_tokens += int(row.get("output_tokens") or 0)
            s.cache_read_tokens += int(row.get("cache_read_tokens") or 0)
            s.cache_creation_tokens += int(row.get("cache_creation_tokens") or 0)
            s.tool_calls += sum((row.get("tool_calls") or {}).values())
            s.tool_errors += int(row.get("tool_errors") or 0)
            s.redundant_reads += int(row.get("redundant_reads") or 0)
            s.bash_output_chars += int(row.get("bash_output_chars") or 0)
            s.contexts.extend(
                r["input_tokens"] + r["cache_read_tokens"] + r["cache_creation_tokens"]
                for r in row.get("requests", []) if not r.get("sidechain")
            )
        elif row.get("type") == "task":
            s.tasks += 1
            g = row.get("grade") or {}
            s.delivered_count += 1 if row.get("delivered") else 0
            s.accept_total += int(g.get("accept_total") or 0)
            s.accept_passed += int(g.get("accept_passed") or 0)
            s.gate_failures += 0 if g.get("gate_ok", True) else 1
            s.files_changed += int(g.get("files_changed") or 0)
            s.lines_added += int(g.get("lines_added") or 0)

    ordered = [summaries[n] for n in order if n in summaries]
    ordered += [s for n, s in sorted(summaries.items()) if n not in order]
    return ordered


def _fmt(key: str, value: Any, unit: str) -> str:
    if unit == "%":
        return "%.1f%%" % (value * 100)
    if unit == "$":
        return "$%.2f" % value
    if unit == "n/n":
        return str(value)
    if unit == "s":
        return "%.0f" % value
    if unit == "tok" or unit == "chars":
        return "{:,}".format(int(value))
    return "%.1f" % value if isinstance(value, float) else str(value)


def _winners(summaries: List[ArmSummary]) -> Dict[str, str]:
    """Best arm per metric -- but only among arms that delivered something.

    An arm with a 0/6 delivery rate has the best token numbers by construction;
    letting it 'win' a column would make the table actively misleading."""
    eligible = [s for s in summaries if s.delivered_count > 0] or summaries
    winners: Dict[str, str] = {}
    for key, _h, _u, lower_is_better, _t in COLUMNS:
        if key in ("delivered",):
            best = max(eligible, key=lambda s: s.delivered_count)
        elif lower_is_better:
            best = min(eligible, key=lambda s: s.value(key))
        else:
            best = max(eligible, key=lambda s: s.value(key))
        winners[key] = best.arm
    return winners


def render_markdown(manifest: Dict[str, Any], summaries: List[ArmSummary]) -> str:
    cfg = manifest.get("config", {})
    lines: List[str] = []
    lines.append("# fluxbench — run %s" % manifest.get("run_id", "?"))
    lines.append("")
    lines.append("project **%s** · model `%s`%s · %d tasks · budget $%.0f"
                 % (manifest.get("project", {}).get("title", "?"),
                    cfg.get("model", "?"),
                    (" · effort `%s`" % cfg["effort"]) if cfg.get("effort") else "",
                    len(manifest.get("project", {}).get("tasks", [])),
                    float(cfg.get("max_usd", 0))))
    lines.append("")

    headers = ["arm"] + [h for _k, h, _u, _l, _t in COLUMNS]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    winners = _winners(summaries)
    for s in summaries:
        cells = [s.arm]
        for key, _h, unit, _l, _t in COLUMNS:
            text = _fmt(key, s.value(key), unit)
            if winners.get(key) == s.arm and s.delivered_count > 0:
                text = "**%s**" % text
            cells.append(text)
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("Bold = best among arms that delivered at least one task. "
                 "Efficiency without delivery is not a win.")
    lines.append("")

    lines.append("## against plan.md targets")
    lines.append("")
    lines.append("| metric | target | " + " | ".join(s.arm for s in summaries) + " |")
    lines.append("|" + "|".join(["---"] * (2 + len(summaries))) + "|")
    for key, header, unit, _lower, target in COLUMNS:
        if target is None:
            continue
        row = [header, _fmt(key, target, unit)]
        for s in summaries:
            value = s.value(key)
            mark = "✓" if value <= target else "✗"
            row.append("%s %s" % (_fmt(key, value, unit), mark))
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    lines.append("## delivery detail")
    lines.append("")
    lines.append("| arm | tasks | delivered | acceptance tests | gate failures | failed sessions | total $ | $/delivered |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for s in summaries:
        lines.append("| %s | %d | %s | %d/%d | %d | %d | $%.2f | %s |"
                     % (s.arm, s.tasks, s.delivered, s.accept_passed, s.accept_total,
                        s.gate_failures, s.failed_sessions, s.cost_usd,
                        "n/a" if s.delivered_count == 0 else "$%.2f" % s.cost_per_delivered))
    lines.append("")
    return "\n".join(lines)


def report(records_path: Path) -> str:
    manifest, rows = load(records_path)
    return render_markdown(manifest, summarize(manifest, rows))
