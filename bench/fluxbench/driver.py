"""Spawn one headless Claude Code session and hand back its result envelope.

Everything an arm cannot control lives here, on purpose. Model, effort,
permission mode, tool allow-list, setting sources and the environment scrub are
set identically for every arm; the arm supplies only its plugin directories and
its prompt. If a knob ever needs to vary per arm, it has to move into the Arm
dataclass deliberately -- it cannot drift in through the driver.

Two isolation choices are load-bearing:

* ``--setting-sources project`` keeps the operator's own ``~/.claude`` out of the
  measurement. Verified empirically: a bare session costs ~6.5k prefix tokens
  with it, and every installed personal plugin would otherwise ride along in
  every arm's cached prefix and drown the differences being measured.
* the environment is scrubbed of ``CLAUDECODE``/``CLAUDE_CODE_*``, because the
  bench is itself usually run from inside a Claude Code session and those
  variables would leak the parent's identity into the child.

A third rule was learned the expensive way, in run ``meridian-002``: **a
transport failure is not a result.** When the account hit its rate limit, 32
sessions came back in under a second with ``api_error_status: 429``, and the
runner scored them as arms that had failed to deliver. Four of six arms were
graded on work that never ran. So statuses in :data:`RETRYABLE_API_STATUSES` are
now waited out and retried here, and whatever survives that is handed up as an
API error the runner must refuse to score rather than attribute to the arm.

The retry is only ever attempted on an attempt that cost nothing. A session
billed for turns may already have edited the repo, and re-running it would
measure an arm against a tree its own half-finished work had moved.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

# Uniform across arms. AskUserQuestion is denied because a headless run has no
# user: an arm whose workflow asks a question would otherwise stall or, worse,
# be silently handicapped relative to arms that never ask.
DISALLOWED_TOOLS = ["AskUserQuestion"]
DEFAULT_TIMEOUT_S = 1800

# Transport failures, not answers: the request never reached a model that could
# have tried the task. 429 is the subscription rate limit (the one that spoiled
# meridian-002); 5xx and 529 are upstream capacity.
RETRYABLE_API_STATUSES = {"429", "500", "502", "503", "504", "529"}

# The same transport failure, reported without a status code. meridian-005 hit
# it: after the retries were exhausted the CLI came back `terminal_reason:
# api_error` with an EMPTY `api_error_status`, so every status-keyed check below
# saw nothing, and five speckit sessions that never reached a model were graded
# as an arm delivering 0/19. That is meridian-002's lie in a new shape, so the
# transport test keys on "did this reach a model", not on "did it name a code".
TRANSPORT_TERMINAL_REASONS = {"api_error"}

# Rate-limit windows are measured in minutes, so the waits are too. Three
# attempts spread over ~13 minutes rides out a window without stalling a run
# behind an outage that is not going to clear.
DEFAULT_BACKOFF_S = (60, 180, 600)


@dataclass
class SessionOutcome:
    ok: bool
    payload: Dict[str, Any]
    stdout: str
    stderr: str
    wall_ms: int
    argv: List[str]
    error: str = ""
    api_error_status: str = ""
    attempts: int = 1


def claude_binary() -> str:
    found = shutil.which("claude")
    if not found:
        raise RuntimeError("`claude` is not on PATH; the benchmark drives the real CLI")
    return found


def child_env() -> Dict[str, str]:
    env = dict(os.environ)
    for key in list(env):
        if key == "CLAUDECODE" or key.startswith("CLAUDE_CODE_"):
            env.pop(key, None)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    return env


def build_argv(
    prompt: str,
    *,
    model: str,
    effort: Optional[str],
    plugin_dirs: Sequence[str],
    setting_sources: str,
    settings_file: Optional[Path],
    max_usd: Optional[float],
) -> List[str]:
    argv = [
        claude_binary(),
        "-p",
        prompt,
        "--output-format",
        "json",
        "--model",
        model,
        "--permission-mode",
        "bypassPermissions",
        "--setting-sources",
        setting_sources,
        "--disallowed-tools",
        ",".join(DISALLOWED_TOOLS),
    ]
    if effort:
        argv += ["--effort", effort]
    if settings_file is not None:
        argv += ["--settings", str(settings_file)]
    for d in plugin_dirs:
        argv += ["--plugin-dir", d]
    if max_usd:
        argv += ["--max-budget-usd", str(max_usd)]
    return argv


def _attempt(
    prompt: str,
    cwd: Path,
    *,
    model: str,
    effort: Optional[str] = None,
    plugin_dirs: Sequence[str] = (),
    setting_sources: str = "project",
    settings_file: Optional[Path] = None,
    max_usd: Optional[float] = None,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> SessionOutcome:
    argv = build_argv(
        prompt,
        model=model,
        effort=effort,
        plugin_dirs=plugin_dirs,
        setting_sources=setting_sources,
        settings_file=settings_file,
        max_usd=max_usd,
    )
    started = time.monotonic()
    try:
        proc = subprocess.run(
            argv,
            cwd=str(cwd),
            env=child_env(),
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return SessionOutcome(
            ok=False,
            payload={},
            stdout="",
            stderr="",
            wall_ms=int((time.monotonic() - started) * 1000),
            argv=argv,
            error="timeout after %ss" % timeout_s,
        )
    wall_ms = int((time.monotonic() - started) * 1000)

    payload: Dict[str, Any] = {}
    error = ""
    try:
        payload = json.loads(proc.stdout.strip().splitlines()[-1]) if proc.stdout.strip() else {}
    except (ValueError, IndexError):
        error = "unparseable output"
    if not payload and not error:
        error = "empty output (exit %d)" % proc.returncode
    ok = bool(payload) and not payload.get("is_error") and payload.get("subtype") == "success"
    status = "" if ok else str(payload.get("api_error_status") or "")
    if not ok and not error:
        error = str(status or payload.get("terminal_reason") or "session failed")
    return SessionOutcome(
        ok=ok,
        payload=payload,
        stdout=proc.stdout,
        stderr=proc.stderr,
        wall_ms=wall_ms,
        argv=argv,
        error=error,
        api_error_status=status,
    )


def is_transport_failure(outcome: SessionOutcome) -> bool:
    """Did the request fail to reach a model at all?

    Two shapes of the same thing: a named retryable status, or a bare
    ``api_error`` terminal reason with no status attached. Either way the arm was
    never given the chance to try, so neither may be scored as its answer.
    """
    if outcome.ok:
        return False
    if outcome.api_error_status in RETRYABLE_API_STATUSES:
        return True
    reason = str(outcome.payload.get("terminal_reason") or "")
    return reason in TRANSPORT_TERMINAL_REASONS


def is_retryable(outcome: SessionOutcome) -> bool:
    """Wait-and-try-again, or give up and refuse to score?

    Both halves matter. The failure has to be transport rather than the model's
    answer, *and* the attempt has to have cost nothing -- a session that was
    billed for turns may already have written to the repo, and re-running it
    would judge the arm against a tree its own abandoned attempt had moved.
    """
    if not is_transport_failure(outcome):
        return False
    return float(outcome.payload.get("total_cost_usd") or 0.0) == 0.0


def run_session(
    prompt: str,
    cwd: Path,
    *,
    model: str,
    effort: Optional[str] = None,
    plugin_dirs: Sequence[str] = (),
    setting_sources: str = "project",
    settings_file: Optional[Path] = None,
    max_usd: Optional[float] = None,
    timeout_s: int = DEFAULT_TIMEOUT_S,
    backoff_s: Sequence[int] = DEFAULT_BACKOFF_S,
    on_retry: Optional[Callable[[int, int, SessionOutcome], None]] = None,
    sleep: Callable[[float], None] = time.sleep,
) -> SessionOutcome:
    """One session, retried through rate limits but never through an answer."""
    outcome = None
    for attempt, wait in enumerate(list(backoff_s) + [None], start=1):
        outcome = _attempt(
            prompt, cwd,
            model=model, effort=effort, plugin_dirs=plugin_dirs,
            setting_sources=setting_sources, settings_file=settings_file,
            max_usd=max_usd, timeout_s=timeout_s,
        )
        outcome.attempts = attempt
        if wait is None or not is_retryable(outcome):
            return outcome
        if on_retry:
            on_retry(attempt, wait, outcome)
        sleep(wait)
    return outcome
