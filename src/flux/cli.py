"""``flux`` command line entry point.

Subcommands mirror the pipeline in plan.md §4. ``metrics``, ``doctor`` and ``status``
do real work; the rest are declared stubs so the surface is fixed early and each
milestone fills one in rather than reshaping the CLI.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path

from flux import __version__, knowledge
from flux.config import FluxConfig
from flux.errors import ConfigError, FluxError, ParkSignal
from flux.executor.billing import detect_billing_redirects, preflight, sanitize_process_env
from flux.executor.sdk import ClaudeAgentSDKExecutor
from flux.git import head_sha
from flux.metrics.record import DEFAULT_METRICS_PATH, MetricsStore
from flux.metrics.report import build_report, render
from flux.runner.checkpoint import CheckpointStore
from flux.runner.context import CONTEXT_DIRNAME, FLUX_DIRNAME, TicketContext
from flux.runner.loop import run_ticket
from flux.runner.transition import Pipeline, next_stage
from flux.scaffold import init_repo, install_post_merge_hook
from flux.stages import build_pipeline
from flux.tickets import TICKET_FILENAME, load_ticket

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_PARKED = 2
EXIT_NOT_IMPLEMENTED = 3

# Subcommands whose milestone has not landed yet: (name, help, milestone).
_PLANNED: tuple[tuple[str, str, str], ...] = (
    ("research", "run the research phase for a slug", "M3"),
    ("plan", "run the planning phase for a slug", "M3"),
    ("tickets", "turn a plan into a bd ticket graph", "M4"),
)

_ROOT_HELP = "repo to operate on (default: the current directory)"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="flux", description=__doc__)
    parser.add_argument("--version", action="version", version=f"flux {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    for name, help_text, milestone in _PLANNED:
        planned = sub.add_parser(name, help=f"{help_text} (not implemented — {milestone})")
        planned.add_argument("args", nargs="*", help=argparse.SUPPRESS)
        planned.set_defaults(func=_make_stub(name, milestone))

    index = sub.add_parser("index", help="regenerate the ranked repo map")
    index.add_argument("--root", type=Path, default=Path.cwd(), help=_ROOT_HELP)
    index.add_argument("--top", type=int, default=None, help="entries to keep in the cache")
    index.add_argument(
        "--install-hook",
        action="store_true",
        help="also install a git post-merge hook that regenerates the map",
    )
    index.add_argument(
        "--force", action="store_true", help="with --install-hook, replace an existing hook"
    )
    index.set_defaults(func=cmd_index)

    init = sub.add_parser("init", help="scaffold .flux/ in the target repo")
    init.add_argument("--root", type=Path, default=Path.cwd(), help=_ROOT_HELP)
    init.add_argument(
        "--force",
        action="store_true",
        help="rewrite an existing flux.toml (its gate suite is otherwise left alone)",
    )
    init.set_defaults(func=cmd_init)

    run = sub.add_parser("run", help="run a ticket through the pipeline")
    run.add_argument("ticket", help="ticket id")
    run.add_argument("--root", type=Path, default=Path.cwd(), help=_ROOT_HELP)
    run.add_argument(
        "--worktree",
        type=Path,
        default=None,
        help="checkout the stages edit and the gates run in (default: --root)",
    )
    run.add_argument(
        "--dry-run",
        action="store_true",
        help="print the next stage and the prompt it would receive; spend nothing",
    )
    run.set_defaults(func=cmd_run)

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

    unpark = sub.add_parser("unpark", help="clear a ticket's park so it can run again")
    unpark.add_argument("ticket", help="ticket id")
    unpark.add_argument("--root", type=Path, default=Path.cwd(), help=_ROOT_HELP)
    unpark.set_defaults(func=cmd_unpark)

    doctor = sub.add_parser("doctor", help="verify subscription auth and a clean billing env")
    doctor.set_defaults(func=cmd_doctor)

    return parser


def _make_stub(name: str, milestone: str) -> Callable[[argparse.Namespace], int]:
    def stub(_args: argparse.Namespace) -> int:
        print(f"flux {name}: not implemented yet (lands in {milestone})", file=sys.stderr)
        return EXIT_NOT_IMPLEMENTED

    return stub


def cmd_init(args: argparse.Namespace) -> int:
    """Lay down ``.flux/`` (ADR 0006)."""
    report = init_repo(Path(args.root), force=args.force)
    print(f"target:  {report.target}")
    for path in report.created:
        print(f"created  {path}")
    for path in report.skipped:
        print(f"kept     {path}")
    for warning in report.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    example = report.root / FLUX_DIRNAME / CONTEXT_DIRNAME / "<ticket-id>" / TICKET_FILENAME
    print(f"\nNext: write a ticket brief to {example}")
    print("      then run `flux run <ticket-id>`")
    return EXIT_OK


def cmd_index(args: argparse.Namespace) -> int:
    """Regenerate the repo map (ADR 0009). Zero LLM calls — it is a ranker, not a model."""
    root = Path(args.root).resolve()
    settings = FluxConfig.load(root)
    config = settings.repo_map
    if args.top is not None:
        config = replace(config, top=args.top)

    report = knowledge.generate(root, config, head=head_sha(root))
    print(f"tool:    {' '.join(config.command)}")
    print(f"mapped:  {report.map.file_count} file(s) -> {len(report.map.entries)} ranked")
    print(f"cache:   {report.path}")
    print(f"took:    {report.duration_ms / 1000:.1f}s")
    for warning in report.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    if args.install_hook:
        path, note = install_post_merge_hook(root, force=args.force)
        print(f"hook:    {path} — {note}")
    top = report.map.render(limit=5)
    if top:
        print(f"\ntop of the map:\n{top}")
    return EXIT_OK


def cmd_run(args: argparse.Namespace) -> int:
    """Drive one ticket through the pipeline until it finishes or parks."""
    root = Path(args.root).resolve()
    settings = FluxConfig.load(root)
    ticket = load_ticket(args.ticket, root=root, config=settings, worktree=args.worktree)
    pipeline = build_pipeline(settings)
    if args.dry_run:
        return _dry_run(ticket, pipeline)

    if not settings.gates:
        print(
            f"warning: no gates configured in {settings.path} — nothing will verify this "
            "change independently",
            file=sys.stderr,
        )
    result = run_ticket(ticket, pipeline, ClaudeAgentSDKExecutor())
    ran = ", ".join(result.stages_run) or "(nothing new to run)"
    print(f"ticket:  {result.ticket}")
    print(f"ran:     {ran}")
    if result.park is not None:
        print(f"status:  PARKED at {result.park.stage} ({result.park.reason})")
        print(f"         {result.park.note}")
        return EXIT_PARKED
    print("status:  completed")
    return EXIT_OK


def _dry_run(ticket: TicketContext, pipeline: Pipeline) -> int:
    """Show what the next stage would be sent, without starting a session.

    Hydration is pure code (design.md §2), so this is the whole input to the model —
    which makes it the cheapest way to check a context pack before paying for it.
    """
    store = CheckpointStore(ticket.state_dir)
    decision = next_stage(
        pipeline,
        completed=store.completed_stages(),
        state=store.load_state(ticket.ticket_id),
        config=ticket.config,
    )
    if decision.kind != "run" or decision.stage is None:
        print(f"next:    {decision.kind} ({decision.reason}) {decision.note}".rstrip())
        return EXIT_PARKED if decision.kind == "park" else EXIT_OK
    stage = decision.stage
    pack = stage.hydrate(ticket)
    cfg = stage.config(ticket)
    print(
        f"next:    {stage.name}  [{cfg.model} · effort={cfg.effort} · "
        f"max_turns={cfg.max_turns} · {cfg.permission_mode}]"
    )
    print(f"gates:   {', '.join(g.name for g in stage.gates(ticket)) or '(none)'}")
    print(f"pack:    {pack.size_chars} chars (~{pack.approx_tokens} tokens)")
    print(f"\n--- system prompt ---\n{pack.system_prompt}")
    print(f"\n--- prompt ---\n{pack.prompt}")
    return EXIT_OK


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
    subprocess. The next stage comes from the same pure transition function the runner
    uses, so status and run can never disagree about where a ticket is.
    """
    root = Path(args.root).resolve()
    settings = FluxConfig.load(root)
    ticket = TicketContext(ticket_id=args.ticket, root=root, config=settings.runner)
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
        return EXIT_OK
    print(f"status:  active ({state.stage_runs} stage run(s) so far)")
    decision = next_stage(
        build_pipeline(settings),
        completed=store.completed_stages(),
        state=state,
        config=ticket.config,
    )
    if decision.kind == "run" and decision.stage is not None:
        print(f"next:    {decision.stage.name}")
    elif decision.kind == "finished":
        print("next:    (nothing — the pipeline is complete)")
    else:
        print(f"next:    park ({decision.reason}) — {decision.note}")
    return EXIT_OK


def cmd_unpark(args: argparse.Namespace) -> int:
    """Clear the park record so the next ``flux run`` resumes the ticket.

    A park means a human was asked to look; unparking is that human saying they did.
    The failed stage's checkpoint is deliberately left in place — it is not ``ok``, so
    the stage reruns — and the stage-run backstop resets, since a ticket that hit the
    backstop would otherwise park again on the next invocation without running anything.
    """
    root = Path(args.root).resolve()
    ticket = TicketContext(ticket_id=args.ticket, root=root)
    store = CheckpointStore(ticket.state_dir)
    state = store.load_state(ticket.ticket_id)
    if state.parked is None:
        print(f"ticket {ticket.ticket_id} is not parked")
        return EXIT_OK
    was = state.parked
    store.save_state(replace(state, parked=None, stage_runs=0))
    print(f"cleared the park at {was.stage} ({was.reason})")
    print(f"         {was.note}")
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
    except FluxError as failed:
        print(f"flux: {failed}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
