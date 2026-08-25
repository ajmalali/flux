"""Aggregate a run into the table that decides whether flux is worth keeping.

The columns are not chosen for tidiness -- they are the targets table in
`.flux/plans/flux-v2/plan.md`, plus the two axes that table takes for granted:
did the arm actually deliver the task, and how long did a human have to wait.

One rule governs the whole report: **an arm's efficiency numbers are only
reported next to its delivery rate.** Winning on tokens by not doing the work is
the failure mode this benchmark exists to make impossible to hide, so 'cheapest'
is never printed as a verdict on its own.

A second rule was added after ``meridian-002``: **void tasks are not zeros.**
When a task could not be attempted -- a rate limit, an upstream outage -- it is
excluded from every denominator here and counted in its own column, and an arm
with no scored tasks is rendered as ``void`` rather than as an arm that tried
and delivered nothing. The distinction is the whole difference between "this
framework does not work" and "the API was down".
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
    ("model_error_rate", "model err", "%", True, 0.015),
    ("friction_rate", "friction", "%", True, None),
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
    tool_error_buckets: Dict[str, int] = field(default_factory=dict)
    redundant_reads: int = 0
    bash_output_chars: int = 0
    files_changed: int = 0
    lines_added: int = 0
    void_tasks: int = 0
    void_reason: str = ""
    no_diff_tasks: int = 0
    scored_tasks: List[str] = field(default_factory=list)
    delivered_tasks: List[str] = field(default_factory=list)
    contexts: List[int] = field(default_factory=list)

    # -- derived ------------------------------------------------------------
    @property
    def scored(self) -> bool:
        """Did this arm get to attempt anything? Nothing below means much if not."""
        return self.tasks > 0

    @property
    def delivered(self) -> str:
        if not self.scored:
            return "void"
        suffix = " (+%d void)" % self.void_tasks if self.void_tasks else ""
        return "%d/%d%s" % (self.delivered_count, self.tasks, suffix)

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
        """Raw failed-tool-result rate. Not published: most of it is friction."""
        return self.tool_errors / self.tool_calls if self.tool_calls else 0.0

    @property
    def model_errors(self) -> int:
        return self.tool_error_buckets.get("model", 0)

    @property
    def friction_errors(self) -> int:
        return self.tool_error_buckets.get("friction", 0)

    @property
    def unclassified_errors(self) -> int:
        """Errors recorded before the split existed, so neither column can see them.

        Runs written by an older ``fluxbench`` carry a total and no buckets. Their
        model and friction columns would read as zero, which is a stronger claim
        than the data supports -- so the count is surfaced and the table says so.
        """
        return max(0, self.tool_errors - sum(self.tool_error_buckets.values()))

    @property
    def model_error_rate(self) -> float:
        return self.model_errors / self.tool_calls if self.tool_calls else 0.0

    @property
    def friction_rate(self) -> float:
        return self.friction_errors / self.tool_calls if self.tool_calls else 0.0

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


API_ERROR_STATUSES = {"400", "401", "403", "404", "408", "429",
                      "500", "502", "503", "504", "529"}

# A transport failure that named no status at all. Records written by
# meridian-005 carry `error: "api_error"` with an empty `api_error_status`;
# reading only the code re-published the untried-arm-as-failed-arm mistake the
# void machinery exists to stop, so the reason counts as evidence too.
API_ERROR_REASONS = {"api_error"}


def _api_status(row: Dict[str, Any]) -> str:
    status = str(row.get("api_error_status") or "")
    if status:
        return status
    error = str(row.get("error") or "").strip()
    if error in API_ERROR_STATUSES:
        return error
    return error if error in API_ERROR_REASONS else ""


def _is_api_failure(row: Dict[str, Any]) -> bool:
    return not row.get("ok", True) and bool(_api_status(row))


def summarize(manifest: Dict[str, Any], rows: List[Dict[str, Any]]) -> List[ArmSummary]:
    titles = {a["name"]: a.get("title", a["name"]) for a in manifest.get("arms", [])}
    order = [a["name"] for a in manifest.get("arms", [])]
    summaries: Dict[str, ArmSummary] = {}

    def get(name: str) -> ArmSummary:
        if name not in summaries:
            summaries[name] = ArmSummary(arm=name, title=titles.get(name, name))
        return summaries[name]

    # First pass: which (arm, task) pairs never got the chance to run? Their
    # sessions have to be excluded from the metrics as well as from the grades --
    # a rate-limited session that returned in 0.3s would otherwise pull an arm's
    # median context and cost per task toward zero.
    void_pairs = {(r.get("arm"), r.get("task")) for r in rows
                  if r.get("type") == "task" and r.get("void")}
    # A task whose session ended on an API error status is void whether or not
    # the runner said so -- runs recorded before that rule existed still hold the
    # evidence in the session rows, and reading them any other way republishes
    # the mistake.
    void_pairs |= {(r.get("arm"), r.get("task")) for r in rows
                   if r.get("type") == "session" and r.get("task") != "bootstrap"
                   and _is_api_failure(r)}
    void_reasons = {(r.get("arm"), r.get("task")): str(r.get("void") or "")
                    for r in rows if r.get("type") == "task" and r.get("void")}

    for row in rows:
        arm = row.get("arm")
        if not arm:
            continue
        s = get(arm)
        pair = (arm, row.get("task"))
        if pair in void_pairs:
            if row.get("type") == "task":
                s.void_tasks += 1
                s.void_reason = s.void_reason or void_reasons.get(pair, "")
            elif row.get("type") == "session" and _is_api_failure(row):
                s.void_reason = s.void_reason or ("could not reach the model (%s)"
                                                  % _api_status(row))
            continue
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
            for bucket, n in (row.get("tool_error_buckets") or {}).items():
                s.tool_error_buckets[bucket] = s.tool_error_buckets.get(bucket, 0) + int(n)
            s.redundant_reads += int(row.get("redundant_reads") or 0)
            s.bash_output_chars += int(row.get("bash_output_chars") or 0)
            s.contexts.extend(
                r["input_tokens"] + r["cache_read_tokens"] + r["cache_creation_tokens"]
                for r in row.get("requests", []) if not r.get("sidechain")
            )
        elif row.get("type") == "task":
            s.tasks += 1
            g = row.get("grade") or {}
            s.scored_tasks.append(str(row.get("task") or ""))
            if row.get("delivered"):
                s.delivered_tasks.append(str(row.get("task") or ""))
            s.delivered_count += 1 if row.get("delivered") else 0
            s.accept_total += int(g.get("accept_total") or 0)
            s.accept_passed += int(g.get("accept_passed") or 0)
            s.gate_failures += 0 if g.get("gate_ok", True) else 1
            s.files_changed += int(g.get("files_changed") or 0)
            s.lines_added += int(g.get("lines_added") or 0)
            if not row.get("delivered") and int(g.get("files_changed") or 0) == 0:
                s.no_diff_tasks += 1

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
            if not s.scored:
                cells.append("void" if key == "delivered" else "—")
                continue
            text = _fmt(key, s.value(key), unit)
            if winners.get(key) == s.arm and s.delivered_count > 0:
                text = "**%s**" % text
            cells.append(text)
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("Bold = best among arms that delivered at least one task. "
                 "Efficiency without delivery is not a win.")
    lines.append("")
    lines.append("`model err` counts only the failures that are evidence the model's "
                 "picture of the code was wrong (a stale edit string, an unread file); "
                 "`friction` counts approval prompts and blocks, which measure the "
                 "operator's allowlist, not the arm. Failing commands — a test that "
                 "exits 1 — are in neither.")
    stale = [s for s in summaries if s.unclassified_errors]
    if stale:
        lines.append("")
        lines.append("**Recorded before the split.** These arms carry tool errors with "
                     "no classification, so both columns above understate them: "
                     + ", ".join("%s (%d)" % (s.arm, s.unclassified_errors) for s in stale)
                     + ". Re-run to classify.")
    voided = [s for s in summaries if s.void_tasks]
    if voided:
        lines.append("")
        lines.append("**This run is incomplete.** Tasks that could not be attempted are "
                     "void — excluded from every column above, not scored as zero:")
        lines.append("")
        lines.append("| arm | tasks scored | void | why |")
        lines.append("|---|---|---|---|")
        for s in voided:
            lines.append("| %s | %d | %d | %s |" % (s.arm, s.tasks, s.void_tasks,
                                                    s.void_reason or "not attempted"))
    lines.append("")

    stalled = [s for s in summaries if s.no_diff_tasks]
    if stalled:
        # A task where every session succeeded and the tree did not move is the
        # signature of an arm that stalled -- typically on a question it could not
        # ask, because the driver denies AskUserQuestion. It may also be a
        # framework that genuinely does nothing, and the harness cannot tell the
        # two apart, so it says so rather than guessing. meridian-003 scored PAUL
        # 1/4 this way: its arm ended each phase with `/paul:verify` instead of
        # `/paul:unify`, so the loop never closed and later plan sessions refused
        # to start.
        lines.append("**Check before publishing.** These arms produced tasks where "
                     "every session succeeded and the tree did not change — usually a "
                     "misconfigured arm stalling on a question it cannot ask, not a "
                     "framework that failed:")
        lines.append("")
        lines.append("| arm | undelivered tasks with an empty diff |")
        lines.append("|---|---|")
        for s in stalled:
            lines.append("| %s | %d of %d |" % (s.arm, s.no_diff_tasks, s.tasks))
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
            if not s.scored:
                # An arm that never ran hits every target by doing nothing. A tick
                # here would be the most misleading character in the report.
                row.append("—")
                continue
            value = s.value(key)
            if key == "model_error_rate" and s.unclassified_errors:
                # A tick here would be earned by missing data: the run predates the
                # friction split, so every one of its errors is invisible to this
                # column. Same failure as ticking an arm that never ran.
                row.append("%s ?" % _fmt(key, value, unit))
                continue
            mark = "✓" if value <= target else "✗"
            row.append("%s %s" % (_fmt(key, value, unit), mark))
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    lines.append("## delivery detail")
    lines.append("")
    lines.append("| arm | tasks | delivered | acceptance tests | gate failures | failed sessions | total $ | $/delivered |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for s in summaries:
        if not s.scored:
            lines.append("| %s | 0 | void | — | — | %d | $%.2f | — |"
                         % (s.arm, s.failed_sessions, s.cost_usd))
            continue
        lines.append("| %s | %d | %s | %d/%d | %d | %d | $%.2f | %s |"
                     % (s.arm, s.tasks, s.delivered, s.accept_passed, s.accept_total,
                        s.gate_failures, s.failed_sessions, s.cost_usd,
                        "n/a" if s.delivered_count == 0 else "$%.2f" % s.cost_per_delivered))
    lines.append("")
    return "\n".join(lines)


FOCUS_ARM = "flux"


def render_verdict(summaries: List[ArmSummary], focus: str = FOCUS_ARM) -> str:
    """Answer the question the benchmark was built to answer, in words.

    "Is flux beating everything?" is not readable off a twelve-column table at a
    glance, and the whole point of the exercise is that an unfavourable answer
    triggers work rather than being quietly absorbed. So the verdict names every
    metric flux loses, who beat it, and by how much.
    """
    lines: List[str] = ["## verdict", ""]
    target = next((s for s in summaries if s.arm == focus), None)
    if target is None:
        return "\n".join(lines + ["No `%s` arm in this run." % focus, ""])

    incomplete = [s for s in summaries if s.void_tasks]
    if incomplete:
        lines.append("**Read this run as incomplete.** %s did not get to attempt every "
                     "task (%s), so no column below is a like-for-like comparison unless "
                     "the arms scored the same tasks. Void tasks are excluded, never "
                     "counted as failures to deliver."
                     % (", ".join("`%s` (%d void)" % (s.arm, s.void_tasks) for s in incomplete),
                        incomplete[0].void_reason or "not attempted"))
        lines.append("")

    if not target.scored:
        lines.append("`%s` was **voided** — %s. There is nothing to judge."
                     % (focus, target.void_reason or "it never ran"))
        lines.append("")
        return "\n".join(lines)

    others = [s for s in summaries if s.arm != focus and s.delivered_count > 0]
    lines.append("`%s` delivered **%s** at **$%.2f/task**%s."
                 % (focus, target.delivered, target.cost_per_task,
                    "" if target.delivered_count == 0
                    else " ($%.2f per delivered task)" % target.cost_per_delivered))
    lines.append("")

    if target.delivered_count == 0:
        lines.append("**It delivered nothing.** No efficiency number below counts for "
                     "anything until that changes.")
        lines.append("")
        return "\n".join(lines)

    # Only arms that ran the same number of tasks can out-deliver this one. An
    # arm that got four tasks to focus's two has a bigger numerator by default.
    peers = [s for s in summaries if s.arm != focus and s.tasks == target.tasks]
    best_delivery = max((s.delivered_count for s in peers), default=0)
    if target.delivered_count < best_delivery:
        beaten_by = [s.arm for s in peers if s.delivered_count == best_delivery]
        lines.append("**Out-delivered.** %s delivered %d of %d; `%s` delivered %d. "
                     "Cost comparisons are secondary to this."
                     % (", ".join("`%s`" % a for a in beaten_by), best_delivery,
                        target.tasks, focus, target.delivered_count))
        lines.append("")
    elif any(s.tasks != target.tasks for s in summaries if s.arm != focus and s.scored):
        # Different arms scored different task sets, so the delivery column is
        # not a comparison. The tasks they *both* attempted still are -- and
        # throwing that away would waste the only real evidence the run produced.
        lines.append("**The arms scored different tasks**, so the delivery column above "
                     "is not a comparison. On the tasks each pair both attempted:")
        lines.append("")
        lines.append("| vs | shared tasks | `%s` | them |" % focus)
        lines.append("|---|---|---|---|")
        mine = set(target.scored_tasks)
        for other in (s for s in summaries if s.arm != focus and s.scored):
            shared = sorted(mine & set(other.scored_tasks))
            if not shared:
                lines.append("| `%s` | none | — | — |" % other.arm)
                continue
            lines.append("| `%s` | %s | %d/%d | %d/%d |"
                         % (other.arm, ", ".join(shared),
                            len(set(target.delivered_tasks) & set(shared)), len(shared),
                            len(set(other.delivered_tasks) & set(shared)), len(shared)))
        lines.append("")

    losses = []
    for key, header, unit, lower_is_better, _t in COLUMNS:
        if key == "delivered":
            continue
        mine = target.value(key)
        for other in others:
            theirs = other.value(key)
            better = theirs < mine if lower_is_better else theirs > mine
            if better:
                losses.append((header, unit, mine, other.arm, theirs, lower_is_better))
                break
        else:
            continue

    if not losses:
        lines.append("**`%s` wins every measured column** against every arm that "
                     "delivered. Nothing here says to change it." % focus)
        lines.append("")
        return "\n".join(lines)

    lines.append("Where `%s` is beaten — each row is a thing to fix or a claim to "
                 "retire:" % focus)
    lines.append("")
    lines.append("| metric | %s | best | beaten by | gap |" % focus)
    lines.append("|---|---|---|---|---|")
    for header, unit, mine, arm, theirs, lower_is_better in losses:
        best = min((o.value(_key_for(header)) for o in others),
                   key=lambda v: v) if lower_is_better else max(
                       (o.value(_key_for(header)) for o in others))
        winner = min(others, key=lambda o: o.value(_key_for(header))) if lower_is_better \
            else max(others, key=lambda o: o.value(_key_for(header)))
        lines.append("| %s | %s | %s | `%s` | %s |"
                     % (header, _fmt(_key_for(header), mine, unit),
                        _fmt(_key_for(header), best, unit), winner.arm,
                        _gap(mine, best, lower_is_better)))
    lines.append("")
    return "\n".join(lines)


def _key_for(header: str) -> str:
    for key, head, _u, _l, _t in COLUMNS:
        if head == header:
            return key
    raise KeyError(header)


def _gap(mine: float, best: float, lower_is_better: bool) -> str:
    try:
        mine, best = float(mine), float(best)
    except (TypeError, ValueError):
        return "-"
    if best == 0 or mine == 0:
        return "-"
    ratio = (mine / best) if lower_is_better else (best / mine)
    return "%.2gx" % ratio if ratio >= 1.05 else "~equal"


def report(records_path: Path, focus: str = FOCUS_ARM) -> str:
    manifest, rows = load(records_path)
    summaries = summarize(manifest, rows)
    return render_markdown(manifest, summaries) + "\n" + render_verdict(summaries, focus)
