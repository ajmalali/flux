"""``flux`` command line entry point.

Subcommands mirror the pipeline in plan.md §4. Only ``metrics`` and ``doctor`` do
real work at T2; the rest are declared stubs so the surface is fixed early and each
milestone fills one in rather than reshaping the CLI.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from flux import __version__
from flux.errors import ParkSignal
from flux.executor.billing import detect_billing_redirects, preflight, sanitize_process_env
from flux.metrics.record import DEFAULT_METRICS_PATH, MetricsStore
from flux.metrics.report import build_report, render

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_PARKED = 2
EXIT_NOT_IMPLEMENTED = 3

# Subcommands whose milestone has not landed yet: (name, help, milestone).
_PLANNED: tuple[tuple[str, str, str], ...] = (
    ("init", "scaffold .flux/ in the target repo", "M0/T4"),
    ("index", "regenerate the repo map", "M0/T4"),
    ("research", "run the research phase for a slug", "M3"),
    ("plan", "run the planning phase for a slug", "M3"),
    ("tickets", "turn a plan into a bd ticket graph", "M4"),
    ("run", "run a ticket through the pipeline", "M0/T3"),
    ("status", "show ticket + checkpoint state", "M0/T3"),
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="flux", description=__doc__)
    parser.add_argument("--version", action="version", version=f"flux {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    for name, help_text, milestone in _PLANNED:
        planned = sub.add_parser(name, help=f"{help_text} (not implemented — {milestone})")
        planned.add_argument("args", nargs="*", help=argparse.SUPPRESS)
        planned.set_defaults(func=_make_stub(name, milestone))

    metrics = sub.add_parser("metrics", help="report per-stage cost, tokens, and time")
    metrics.add_argument(
        "--path",
        type=Path,
        default=DEFAULT_METRICS_PATH,
        help=f"metrics JSONL to read (default: {DEFAULT_METRICS_PATH})",
    )
    metrics.add_argument("--ticket", default=None, help="restrict to one ticket id")
    metrics.add_argument("--stage", default=None, help="restrict to one stage name")
    metrics.set_defaults(func=cmd_metrics)

    doctor = sub.add_parser("doctor", help="verify subscription auth and a clean billing env")
    doctor.set_defaults(func=cmd_doctor)

    return parser


def _make_stub(name: str, milestone: str) -> Callable[[argparse.Namespace], int]:
    def stub(_args: argparse.Namespace) -> int:
        print(f"flux {name}: not implemented yet (lands in {milestone})", file=sys.stderr)
        return EXIT_NOT_IMPLEMENTED

    return stub


def cmd_metrics(args: argparse.Namespace) -> int:
    """Print the KPI report (ADR 0008)."""
    path: Path = args.path
    store = MetricsStore(path)
    records = store.read()
    if args.ticket:
        records = [r for r in records if r.ticket == args.ticket]
    if args.stage:
        records = [r for r in records if r.stage == args.stage]
    report = build_report(records, malformed_lines=store.count_malformed())
    print(render(report))
    return EXIT_OK


def cmd_doctor(_args: argparse.Namespace) -> int:
    """Run the ADR 0010 preflight and report what it found."""
    removed = sanitize_process_env()
    status = preflight()
    print(f"auth:          {status.email or '(unknown)'} via {status.auth_method}")
    print(f"provider:      {status.api_provider}")
    print(f"subscription:  {status.subscription_type or '(none reported)'}")
    print(f"stripped from environment: {', '.join(sorted(removed)) if removed else 'nothing'}")
    print(f"billing redirects: {', '.join(detect_billing_redirects()) or 'none'}")
    return EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "func", None) is None:
        parser.print_help()
        return EXIT_OK
    try:
        return int(args.func(args))
    except ParkSignal as parked:
        print(f"parked ({parked.reason}): {parked.note}", file=sys.stderr)
        return EXIT_PARKED


if __name__ == "__main__":
    raise SystemExit(main())
