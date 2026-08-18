"""Metrics store and report (ADR 0008, design.md §3)."""

from flux.metrics.record import (
    DEFAULT_METRICS_PATH,
    SCHEMA_VERSION,
    GateOutcome,
    MetricRecord,
    MetricsStore,
)
from flux.metrics.report import (
    Aggregate,
    Report,
    WindowSnapshot,
    aggregate,
    build_report,
    group_by_stage,
    group_by_ticket,
    group_by_variant,
    latest_window,
    render,
)

__all__ = [
    "DEFAULT_METRICS_PATH",
    "SCHEMA_VERSION",
    "Aggregate",
    "GateOutcome",
    "MetricRecord",
    "MetricsStore",
    "Report",
    "WindowSnapshot",
    "aggregate",
    "build_report",
    "group_by_stage",
    "group_by_ticket",
    "group_by_variant",
    "latest_window",
    "render",
]
