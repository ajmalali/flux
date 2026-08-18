"""``flux`` command line entry point.

Subcommands mirror the pipeline in plan.md §4. ``metrics``, ``doctor`` and ``status``
do real work; the rest are declared stubs so the surface is fixed early and each
milestone fills one in rather than reshaping the CLI.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from flux import __version__
from flux.errors import ConfigError, ParkSignal
from flux.executor.billing import detect_billing_redirects, preflight, sanitize_process_env
from flux.metrics.record import DEFAULT_METRICS_PATH, MetricsStore
from flux.metrics.report import build_report, render
from flux.runner.checkpoint import CheckpointStore
from flux.runner.context import TicketContext

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
    ("run", "run a ticket through the pipeline", "M0/T4"),
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

    status = sub.add_parser("status", help="show a ticket's checkpoint state")
    status.add_argument("ticket", help="ticket id")
    status.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="repo the ticket belongs to (default: the current directory)",
    )
    status.set_defaults(func=cmd_status)

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


def cmd_status(args: argparse.Namespace) -> int:
    """Print a ticket's position in the pipeline.

    A read of the checkpoint files and nothing else (design.md §1) — no model, no
    subprocess. The *next* stage is not shown yet: that needs the concrete pipeline,
    which lands with the stages in T4.
    """
    ticket = TicketContext(ticket_id=args.ticket, root=Path(args.root).resolve())
    store = CheckpointStore(ticket.state_dir)
    state = store.load_state(ticket.ticket_id)
    # Chronological, not alphabetical: the order stages actually ran is the story.
    checkpoints = sorted(store.iter_checkpoints(), key=lambda cp: cp.ts)

    print(f"ticket:  {ticket.ticket_id}")
    print(f"state:   {ticket.state_dir}")
    if not checkpoints:
        print("stages:  (none run yet)")
    for index, cp in enumerate(checkpoints):
        label = "stages: " if index == 0 else "        "
        mark = "done" if cp.ok else "failed"
        note = f" — {cp.note}" if cp.note else ""
        print(f"{label} {cp.stage:<12} {mark:<7} {cp.attempts} attempt(s)  {cp.ts}{note}")
    if state.review_iterations or state.open_findings:
        findings = "findings open" if state.open_findings else "no open findings"
        print(f"review:  {state.review_iterations} pass(es), {findings}")
    if state.parked is not None:
        print(f"status:  PARKED at {state.parked.stage} ({state.parked.reason})")
        print(f"         {state.parked.note}")
    else:
        print(f"status:  active ({state.stage_runs} stage run(s) so far)")
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
    except ConfigError as bad:
        print(f"flux: {bad}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
