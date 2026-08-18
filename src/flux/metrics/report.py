"""``flux metrics`` — aggregation and rendering over the JSONL store (ADR 0008).

Two audiences, one report. Per-stage rows answer "where does the time and token
budget go"; the harness-vs-vanilla block answers the standing kill-criterion: did
the harness beat plain Claude Code on the last samples.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from flux.metrics.record import MetricRecord

Keyer = Callable[[MetricRecord], str]


@dataclass(frozen=True, slots=True)
class Aggregate:
    """Rolled-up numbers for one group of records."""

    key: str
    runs: int = 0
    ok_runs: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    cost_usd: float = 0.0
    wall_ms: int = 0
    retries: int = 0
    exploratory_calls: int = 0
    gates_run: int = 0
    gates_passed: int = 0

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_tokens
            + self.cache_creation_tokens
        )

    @property
    def billable_input_tokens(self) -> int:
        """Uncached input — the figure that actually consumes the usage window."""
        return self.input_tokens + self.cache_creation_tokens

    @property
    def ok_rate(self) -> float:
        return self.ok_runs / self.runs if self.runs else 0.0

    @property
    def gate_pass_rate(self) -> float:
        return self.gates_passed / self.gates_run if self.gates_run else 0.0

    @property
    def mean_wall_ms(self) -> float:
        return self.wall_ms / self.runs if self.runs else 0.0

    @property
    def mean_tokens(self) -> float:
        return self.total_tokens / self.runs if self.runs else 0.0


def aggregate(records: Iterable[MetricRecord], *, key: str = "") -> Aggregate:
    """Fold ``records`` into one :class:`Aggregate`."""
    acc = _Accumulator(key)
    for record in records:
        acc.add(record)
    return acc.build()


def group_by_stage(records: Sequence[MetricRecord]) -> list[Aggregate]:
    """One aggregate per stage, in first-seen order (which is pipeline order)."""
    return _group(records, lambda r: r.stage)


def group_by_ticket(records: Sequence[MetricRecord]) -> list[Aggregate]:
    return _group(records, lambda r: r.ticket)


def group_by_variant(records: Sequence[MetricRecord]) -> list[Aggregate]:
    """Harness vs vanilla — the A/B comparison axis."""
    return _group(records, lambda r: r.variant)


@dataclass
class _Accumulator:
    key: str
    runs: int = 0
    ok_runs: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    cost_usd: float = 0.0
    wall_ms: int = 0
    retries: int = 0
    exploratory_calls: int = 0
    gates_run: int = 0
    gates_passed: int = 0

    def add(self, record: MetricRecord) -> None:
        self.runs += 1
        self.ok_runs += int(record.ok)
        self.input_tokens += record.input_tokens
        self.output_tokens += record.output_tokens
        self.cache_read_tokens += record.cache_read_tokens
        self.cache_creation_tokens += record.cache_creation_tokens
        self.cost_usd += record.total_cost_usd or 0.0
        self.wall_ms += record.wall_ms
        self.retries += record.retry_count
        self.exploratory_calls += record.exploratory_calls
        self.gates_run += len(record.gates)
        self.gates_passed += sum(1 for g in record.gates if g.passed)

    def build(self) -> Aggregate:
        return Aggregate(
            key=self.key,
            runs=self.runs,
            ok_runs=self.ok_runs,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            cache_read_tokens=self.cache_read_tokens,
            cache_creation_tokens=self.cache_creation_tokens,
            cost_usd=self.cost_usd,
            wall_ms=self.wall_ms,
            retries=self.retries,
            exploratory_calls=self.exploratory_calls,
            gates_run=self.gates_run,
            gates_passed=self.gates_passed,
        )


def _group(
    records: Sequence[MetricRecord],
    key_of: Keyer,
) -> list[Aggregate]:
    buckets: dict[str, _Accumulator] = {}
    for record in records:
        key = key_of(record) or "(unset)"
        buckets.setdefault(key, _Accumulator(key)).add(record)
    return [acc.build() for acc in buckets.values()]


@dataclass(frozen=True, slots=True)
class WindowSnapshot:
    """Latest observed subscription usage-window pressure (ADR 0010)."""

    status: str
    utilization: float | None = None
    resets_at: int | None = None


def latest_window(records: Sequence[MetricRecord]) -> WindowSnapshot | None:
    """The most recent record that carried window state, if any."""
    for record in reversed(records):
        if record.window_status:
            return WindowSnapshot(
                status=record.window_status,
                utilization=record.window_utilization,
                resets_at=record.window_resets_at,
            )
    return None


@dataclass(frozen=True, slots=True)
class Report:
    """Everything ``flux metrics`` prints, assembled but not yet formatted."""

    total: Aggregate
    by_stage: Sequence[Aggregate] = ()
    by_ticket: Sequence[Aggregate] = ()
    by_variant: Sequence[Aggregate] = ()
    window: WindowSnapshot | None = None
    malformed_lines: int = 0


def build_report(records: Sequence[MetricRecord], *, malformed_lines: int = 0) -> Report:
    return Report(
        total=aggregate(records, key="all"),
        by_stage=group_by_stage(records),
        by_ticket=group_by_ticket(records),
        by_variant=group_by_variant(records),
        window=latest_window(records),
        malformed_lines=malformed_lines,
    )


def render(report: Report) -> str:
    """Format the report as plain text for a terminal."""
    if report.total.runs == 0:
        return "No metrics recorded yet."

    lines: list[str] = []
    lines.append(_table("Per stage", report.by_stage, "stage"))
    lines.append("")
    lines.append(_table("Per ticket", report.by_ticket, "ticket"))

    if len(report.by_variant) > 1:
        lines.append("")
        lines.append(
            _table("Harness vs vanilla (ADR 0008 kill-criterion)", report.by_variant, "variant")
        )

    total = report.total
    lines.append("")
    lines.append(
        f"Totals: {total.runs} runs · {total.total_tokens:,} tokens "
        f"({total.billable_input_tokens:,} uncached in / {total.output_tokens:,} out) · "
        f"{total.wall_ms / 1000:.1f}s wall · {total.retries} retries · "
        f"{total.exploratory_calls} exploratory calls"
    )
    lines.append(f"Estimated cost (secondary on subscription): ${total.cost_usd:.4f}")

    if report.window:
        util = (
            f"{report.window.utilization * 100:.0f}%"
            if report.window.utilization is not None
            else "unknown"
        )
        lines.append(f"Usage window: {report.window.status} · {util} consumed")
    if report.malformed_lines:
        lines.append(f"Warning: skipped {report.malformed_lines} malformed metrics line(s)")
    return "\n".join(lines)


_COLUMNS = ("runs", "ok", "tokens", "in(uncached)", "out", "wall s", "retries", "explore")


def _table(title: str, rows: Sequence[Aggregate], label: str) -> str:
    if not rows:
        return f"{title}: (none)"
    width = max(len(label), *(len(r.key) for r in rows))
    header = f"{label:<{width}}  " + "  ".join(f"{c:>12}" for c in _COLUMNS)
    out = [title, header, "-" * len(header)]
    for row in rows:
        cells = (
            f"{row.runs}",
            f"{row.ok_runs}/{row.runs}",
            f"{row.total_tokens:,}",
            f"{row.billable_input_tokens:,}",
            f"{row.output_tokens:,}",
            f"{row.wall_ms / 1000:.1f}",
            f"{row.retries}",
            f"{row.exploratory_calls}",
        )
        out.append(f"{row.key:<{width}}  " + "  ".join(f"{c:>12}" for c in cells))
    return "\n".join(out)
