"""The metrics record and its JSONL store (ADR 0008, design.md §3).

One line per ``(ticket, stage)`` attempt appended to ``.flux/usage/metrics.jsonl``.
Append-only and schema-versioned: every kill-switch and threshold in the plan reads
this file, so it has to survive format changes without losing history.

On a subscription the primary economics are tokens and usage-window consumption
(ADR 0010). ``total_cost_usd`` is recorded but is a client-side estimate that only
carries weight under API fallback.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from flux.executor.types import ExecResult
from flux.jsonio import as_json_mapping

SCHEMA_VERSION = 1
DEFAULT_METRICS_PATH = Path(".flux/usage/metrics.jsonl")


@dataclass(frozen=True, slots=True)
class GateOutcome:
    """One deterministic gate's verdict, as the runner observed it."""

    name: str
    passed: bool
    duration_ms: int = 0
    detail: str = ""

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "duration_ms": self.duration_ms,
            "detail": self.detail,
        }

    @classmethod
    def from_json(cls, payload: Mapping[str, Any]) -> GateOutcome:
        return cls(
            name=str(payload.get("name", "")),
            passed=bool(payload.get("passed")),
            duration_ms=_int(payload.get("duration_ms")),
            detail=str(payload.get("detail", "")),
        )


@dataclass(frozen=True, slots=True)
class MetricRecord:
    """One stage attempt. Field set is fixed by design.md §3."""

    ticket: str
    stage: str
    model: str
    effort: str
    billing_mode: str
    provider: str | None = None
    """Provider the CLI reported billing to, observed per run (ADR 0010)."""
    ok: bool = True
    ts: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    total_cost_usd: float | None = None
    wall_ms: int = 0
    api_ms: int = 0
    num_turns: int = 0
    retry_count: int = 0
    exploratory_calls: int = 0
    pack_chars: int = 0
    session_id: str = ""
    error: str | None = None
    """Why the attempt failed, when it did. Triage reads this before the transcript."""
    variant: str = "harness"
    """``harness`` or ``vanilla`` — the A/B baseline axis (ADR 0008)."""
    window_status: str | None = None
    window_utilization: float | None = None
    window_resets_at: int | None = None
    gates: tuple[GateOutcome, ...] = ()
    schema_version: int = SCHEMA_VERSION

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_tokens
            + self.cache_creation_tokens
        )

    @property
    def gates_passed(self) -> bool:
        return all(g.passed for g in self.gates)

    def to_json(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "ts": self.ts or _now_iso(),
            "ticket": self.ticket,
            "stage": self.stage,
            "variant": self.variant,
            "ok": self.ok,
            "model": self.model,
            "effort": self.effort,
            "billing_mode": self.billing_mode,
            "provider": self.provider,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_creation_tokens": self.cache_creation_tokens,
            "total_cost_usd": self.total_cost_usd,
            "wall_ms": self.wall_ms,
            "api_ms": self.api_ms,
            "num_turns": self.num_turns,
            "retry_count": self.retry_count,
            "exploratory_calls": self.exploratory_calls,
            "pack_chars": self.pack_chars,
            "session_id": self.session_id,
            "error": self.error,
            "window_status": self.window_status,
            "window_utilization": self.window_utilization,
            "window_resets_at": self.window_resets_at,
            "gates": [g.to_json() for g in self.gates],
        }

    @classmethod
    def from_json(cls, payload: Mapping[str, Any]) -> MetricRecord:
        raw_gates: object = payload.get("gates")
        gate_maps = (
            [m for m in (as_json_mapping(g) for g in cast(list[object], raw_gates)) if m]
            if isinstance(raw_gates, list)
            else []
        )
        gates = tuple(GateOutcome.from_json(m) for m in gate_maps)
        return cls(
            ticket=str(payload.get("ticket", "")),
            stage=str(payload.get("stage", "")),
            model=str(payload.get("model", "")),
            effort=str(payload.get("effort", "")),
            billing_mode=str(payload.get("billing_mode", "")),
            provider=_opt_str(payload.get("provider")),
            ok=bool(payload.get("ok", True)),
            ts=str(payload.get("ts", "")),
            input_tokens=_int(payload.get("input_tokens")),
            output_tokens=_int(payload.get("output_tokens")),
            cache_read_tokens=_int(payload.get("cache_read_tokens")),
            cache_creation_tokens=_int(payload.get("cache_creation_tokens")),
            total_cost_usd=_opt_float(payload.get("total_cost_usd")),
            wall_ms=_int(payload.get("wall_ms")),
            api_ms=_int(payload.get("api_ms")),
            num_turns=_int(payload.get("num_turns")),
            retry_count=_int(payload.get("retry_count")),
            exploratory_calls=_int(payload.get("exploratory_calls")),
            pack_chars=_int(payload.get("pack_chars")),
            session_id=str(payload.get("session_id", "")),
            error=_opt_str(payload.get("error")),
            variant=str(payload.get("variant", "harness")),
            window_status=_opt_str(payload.get("window_status")),
            window_utilization=_opt_float(payload.get("window_utilization")),
            window_resets_at=_opt_int(payload.get("window_resets_at")),
            gates=gates,
            schema_version=_int(payload.get("schema_version")) or SCHEMA_VERSION,
        )

    @classmethod
    def from_exec_result(
        cls,
        *,
        ticket: str,
        stage: str,
        result: ExecResult,
        gates: Sequence[GateOutcome] = (),
        retry_count: int = 0,
        wall_ms: int | None = None,
        variant: str = "harness",
        ts: str = "",
    ) -> MetricRecord:
        """Build the record for one stage attempt.

        ``wall_ms`` defaults to the session's own duration; the runner overrides it
        when it measured the whole attempt (including gates and retries).
        """
        window = result.window
        return cls(
            ticket=ticket,
            stage=stage,
            model=result.model,
            effort=result.effort,
            billing_mode=result.billing_mode,
            provider=result.provider,
            ok=result.ok and all(g.passed for g in gates),
            ts=ts or _now_iso(),
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            cache_read_tokens=result.usage.cache_read_tokens,
            cache_creation_tokens=result.usage.cache_creation_tokens,
            total_cost_usd=result.total_cost_usd,
            wall_ms=result.duration_ms if wall_ms is None else wall_ms,
            api_ms=result.duration_api_ms,
            num_turns=result.num_turns,
            retry_count=retry_count,
            exploratory_calls=result.exploratory_calls,
            pack_chars=result.pack_chars,
            session_id=result.session_id,
            error=result.error,
            variant=variant,
            window_status=window.status if window else None,
            window_utilization=window.utilization if window else None,
            window_resets_at=window.resets_at if window else None,
            gates=tuple(gates),
        )


@dataclass
class MetricsStore:
    """Append-only JSONL store.

    Each record is serialised, then written as one ``write()`` of a single line to a
    file opened in append mode. Under POSIX that keeps concurrent stage processes
    from interleaving partial lines — parallel tickets (M5) share this file.
    """

    path: Path = DEFAULT_METRICS_PATH

    def record(self, entry: MetricRecord) -> MetricRecord:
        """Append ``entry``, stamping ``ts`` if it is unset. Returns what was written."""
        stamped = entry if entry.ts else _with_ts(entry)
        line = json.dumps(stamped.to_json(), separators=(",", ":"), sort_keys=True) + "\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
        return stamped

    def read(self) -> list[MetricRecord]:
        """All well-formed records, oldest first. Malformed lines are skipped."""
        return list(self.iter_records())

    def iter_records(self) -> Iterator[MetricRecord]:
        """Stream records, tolerating truncated or corrupt lines.

        A half-written final line (killed mid-append) must not make the whole
        history unreadable — the store is diagnostic data, not a ledger.
        """
        if not self.path.exists():
            return
        with self.path.open(encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    payload: Any = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                mapping = as_json_mapping(payload)
                if mapping is not None:
                    yield MetricRecord.from_json(mapping)

    def count_malformed(self) -> int:
        """Number of non-empty lines that failed to parse. Reported by ``flux metrics``."""
        if not self.path.exists():
            return 0
        bad = 0
        with self.path.open(encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    payload: Any = json.loads(stripped)
                except json.JSONDecodeError:
                    bad += 1
                    continue
                if as_json_mapping(payload) is None:
                    bad += 1
        return bad


def _with_ts(entry: MetricRecord) -> MetricRecord:
    return replace(entry, ts=_now_iso())


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _opt_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _opt_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    return float(value) if isinstance(value, int | float) else None


def _opt_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
