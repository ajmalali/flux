#!/usr/bin/env python3
"""fluxbench — run the same project through several Claude Code setups and compare.

    ./bench/run.py list
    ./bench/run.py run --project meridian --arms vanilla,flux,paul --model sonnet
    ./bench/run.py report <run-id>

Stdlib only, no install step. Run outputs land outside the repo (default
~/.flux-bench/runs) so a benchmark never bloats the plugin this repo ships.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fluxbench import report as report_mod  # noqa: E402
from fluxbench.verify import verify_project  # noqa: E402
from fluxbench.runner import DEFAULT_RUNS_DIR, RunConfig, Runner  # noqa: E402
from fluxbench.spec import Arm, Project, available_arms, available_projects  # noqa: E402


def cmd_list(args: argparse.Namespace) -> int:
    print("arms:")
    for name in available_arms():
        arm = Arm.load(name)
        print("  %-10s %s" % (name, arm.title))
        print("             steps: %s" % " -> ".join(s.label for s in arm.steps))
    print("\nprojects:")
    for name in available_projects():
        project = Project.load(name)
        print("  %-10s %s (%d tasks, gate: %s)"
              % (name, project.title, len(project.tasks), project.gate or "none"))
        for task in project.tasks:
            print("             %-6s %s%s" % (task.id, task.title,
                                              "" if task.has_acceptance else "  [NO ACCEPTANCE TESTS]"))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    project = Project.load(args.project)
    names = [n.strip() for n in args.arms.split(",") if n.strip()]
    arms = [Arm.load(n) for n in names]
    config = RunConfig(
        project=args.project,
        arms=names,
        model=args.model,
        effort=args.effort,
        max_usd=args.max_usd,
        max_usd_per_session=args.max_usd_per_session,
        timeout_s=args.timeout,
        tasks=[t.strip() for t in args.tasks.split(",")] if args.tasks else None,
        runs_dir=Path(args.runs_dir).expanduser(),
        run_id=args.run_id or "",
    )
    runner = Runner(config, project, arms)
    if args.dry_run:
        print("would run %d arms x %d tasks into %s"
              % (len(arms), len(config.tasks or project.tasks), runner.out))
        for arm in arms:
            print("  %s: %s" % (arm.name, " -> ".join(s.label for s in arm.steps)))
        return 0
    runner.run()
    text = report_mod.report(runner.records_path)
    (runner.out / "report.md").write_text(text, encoding="utf-8")
    print("\n" + text)
    print("report written to %s" % (runner.out / "report.md"))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    project = Project.load(args.project)
    verdicts = verify_project(project)
    print("verifying corpus: %s" % project.title)
    bad = 0
    for v in verdicts:
        status = "ok" if v.ok else "BROKEN"
        print("  %-6s %-7s red %s (%d/%d before)  green %s (%d/%d after)  gate %s"
              % (v.task, status,
                 "ok" if v.red_ok else "NO", v.before_passed, v.before_total,
                 "ok" if v.green_ok else "NO", v.after_passed, v.after_total,
                 "ok" if v.gate_ok else "NO"))
        if not v.ok:
            bad += 1
            if v.detail:
                for line in v.detail.splitlines():
                    print("         %s" % line)
    if bad:
        print("\n%d of %d tasks are not fit to judge an arm." % (bad, len(verdicts)))
        return 1
    print("\nall %d tasks verified: red on the seed, green on the reference." % len(verdicts))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    target = Path(args.run).expanduser()
    if not target.exists():
        target = Path(args.runs_dir).expanduser() / args.run
    if target.is_dir():
        target = target / "records.jsonl"
    if not target.exists():
        print("no records at %s" % target, file=sys.stderr)
        return 1
    text = report_mod.report(target)
    print(text)
    if args.write:
        (target.parent / "report.md").write_text(text, encoding="utf-8")
        print("\nwritten to %s" % (target.parent / "report.md"))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="fluxbench", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="show available arms and projects").set_defaults(func=cmd_list)

    run = sub.add_parser("run", help="execute a benchmark run")
    run.add_argument("--project", required=True)
    run.add_argument("--arms", required=True, help="comma-separated arm names")
    run.add_argument("--model", default="sonnet")
    run.add_argument("--effort", default=None)
    run.add_argument("--tasks", default=None, help="comma-separated task ids (default: all)")
    run.add_argument("--max-usd", type=float, default=40.0, help="hard ceiling for the whole run")
    run.add_argument("--max-usd-per-session", type=float, default=4.0)
    run.add_argument("--timeout", type=int, default=1800, help="per-session timeout in seconds")
    run.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR))
    run.add_argument("--run-id", default=None)
    run.add_argument("--dry-run", action="store_true")
    run.set_defaults(func=cmd_run)

    ver = sub.add_parser("verify", help="check every task is red on the seed and green on its reference")
    ver.add_argument("--project", required=True)
    ver.set_defaults(func=cmd_verify)

    rep = sub.add_parser("report", help="re-render the report for a run")
    rep.add_argument("run", help="run id, run directory, or path to records.jsonl")
    rep.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR))
    rep.add_argument("--write", action="store_true")
    rep.set_defaults(func=cmd_report)

    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
