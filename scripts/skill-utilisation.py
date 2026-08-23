#!/usr/bin/env python3
"""Measure a skill listing's utilisation bar against the transcript corpus.

The bar (pre-registered 2026-08-23, `ecfcffb`, derived from flux's own
DEFAULT_STATE_BUDGET_TOKENS): an always-on skill listing may cost at most 2,000
tokens per session in which one of its skills is actually invoked --

    cost per session-of-use = tokens injected per session / share of sessions with >=1 invocation

and it must fail on BOTH denominators (all-corpus and real-interactive) to fire.

Two readings of "one of its skills", which the bar did not have to distinguish when it
was written (every mattpocock skill with recorded use was also listed) and which can
disagree. Both are printed; **listed-skills governs** -- a listing is only ever paid for
by the skills it lists, per the bar's own "a budget is a price for a thing, not a number
floating free of what it buys". Judging a listing by uses of skills it never showed
proves too much: fifty dead listed skills would pass on one live unlisted one.

Denominator note: only sessions that actually carried the listing count as billed. You
cannot be charged in a session where the plugin was not installed.

Two things this script exists to stop repeating:

1. **Count both invocation paths.** A skill is reached by a `Skill` tool-use OR by a
   user-typed `<command-name>`. The 2026-08-23 mattpocock scan counted only what it
   saw and undercounted by 6 sessions (`/mattpocock-skills:ask-matt`), publishing
   10.6x for what was 6.3x.
2. **Measure the numerator, don't project it.** Transcripts record the rendered roster
   verbatim as an attachment of type `skill_listing`; `claude plugin details` projects
   instead, and bills `disable-model-invocation` skills that reach no session at all.

Usage:  python3 scripts/skill-utilisation.py flux:            # namespace prefix
        python3 scripts/skill-utilisation.py mattpocock-skills:
        python3 scripts/skill-utilisation.py flux: --since 2026-08-20
"""
import argparse
import glob
import json
import os
import re
import sys

# A `claude -p` bench session is handed its task; it invokes by construction.
# Kept identical to bench/fluxbench/ramp.py's BENCH_MARKERS.
BENCH_MARKERS = ("flux-bench", "private-tmp", "scratchpad")
DEFAULT_ROOT = "~/.claude/projects"
BAR_TOKENS = 2000
CMD = re.compile(r"<command-name>\s*/?([A-Za-z0-9_:-]+)")


def is_bench(project):
    return any(m in project for m in BENCH_MARKERS)


def scan(path, prefix):
    """One transcript -> (date, listing bytes for `prefix`, set of skills invoked)."""
    date = ""
    listing = None
    invoked = set()
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if not date:
                date = str(entry.get("timestamp") or "")[:10]
            att = entry.get("attachment")
            if isinstance(att, dict) and att.get("type") == "skill_listing":
                content = att.get("content") or ""
                # Sessions can re-render the roster; the fullest one is the cost.
                if listing is None or len(content) > len(listing):
                    listing = content
            msg = entry.get("message") or {}
            if msg.get("role") == "assistant":
                blocks = msg.get("content")
                if isinstance(blocks, list):
                    for b in blocks:
                        if not (isinstance(b, dict) and b.get("type") == "tool_use"):
                            continue
                        if b.get("name") != "Skill":
                            continue
                        name = str((b.get("input") or {}).get("skill") or "")
                        if name.startswith(prefix):
                            invoked.add(name)
            else:
                content = msg.get("content")
                text = content if isinstance(content, str) else (
                    json.dumps(content) if content else "")
                for m in CMD.finditer(text):
                    if m.group(1).startswith(prefix):
                        invoked.add(m.group(1))
    lines = [l for l in (listing or "").splitlines() if l.startswith("- " + prefix)]
    listed = set()
    for l in lines:
        listed.add(l[2:].split(":", 2)[0] + ":" + l[2:].split(":", 2)[1])
    return (date, sum(len((l + "\n").encode()) for l in lines), len(lines),
            invoked, listed)


def _cell(tok, share, bar):
    if not share:
        return "undefined (never invoked)   FAILS"
    v = tok / share
    return "%8.0f tok/session-of-use   %s" % (
        v, "PASS" if v <= bar else "FAILS by %.1fx" % (v / bar))


def verdict(label, rows, bar):
    """Only sessions that carried the listing can have been billed by it."""
    billed = [r for r in rows if r["bytes"] > 0]
    if not billed:
        print("  %-20s  no session billed for this listing" % label)
        return
    tok = sum(r["bytes"] for r in billed) / len(billed) / 4.0
    # Reading B (governs): the listing can only be paid for by the skills it lists.
    b_used = [r for r in billed if r["invoked"] & r["listed"]]
    # Reading A: any skill in the namespace, including ones the listing never showed.
    a_used = [r for r in billed if r["invoked"]]
    print("  %-20s  n=%-4d billed=%-4d  %6.1f tok/session" % (label, len(rows),
                                                             len(billed), tok))
    for name, used in (("listed skills  ", b_used), ("any in namespace", a_used)):
        share = len(used) / float(len(billed))
        print("      %s  used=%-4d %6.2f%% util   %s"
              % (name, len(used), share * 100, _cell(tok, share, bar)))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("prefix", help="skill namespace prefix, e.g. 'flux:'")
    ap.add_argument("--root", default=DEFAULT_ROOT, help="transcript root")
    ap.add_argument("--since", default="", help="only sessions on/after this YYYY-MM-DD")
    ap.add_argument("--bar", type=int, default=BAR_TOKENS)
    args = ap.parse_args(argv)

    files = sorted(glob.glob(os.path.join(os.path.expanduser(args.root), "**", "*.jsonl"),
                             recursive=True))
    if not files:
        print("no transcripts under %s" % args.root, file=sys.stderr)
        return 1
    rows = []
    for f in files:
        date, nbytes, nlines, invoked, listed = scan(f, args.prefix)
        if args.since and date < args.since:
            continue
        rows.append(dict(date=date, bench=is_bench(os.path.basename(os.path.dirname(f))),
                         bytes=nbytes, lines=nlines, invoked=invoked,
                         listed=listed))

    print("%s — %d transcripts%s" % (args.prefix, len(rows),
                                     " since %s" % args.since if args.since else ""))
    verdict("all-corpus", rows, args.bar)
    verdict("real-interactive", [r for r in rows if not r["bench"]], args.bar)
    verdict("bench (never a bar)", [r for r in rows if r["bench"]], args.bar)

    sizes = sorted({(r["lines"], r["bytes"]) for r in rows if r["bytes"]})
    print("\n  listing sizes seen (lines, bytes): %s" % (sizes or "none"))
    print("  skills ever LISTED:  %s"
          % (", ".join(sorted({s for r in rows for s in r["listed"]})) or "none"))
    print("  skills ever INVOKED: %s"
          % (", ".join(sorted({s for r in rows for s in r["invoked"]})) or "none"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
