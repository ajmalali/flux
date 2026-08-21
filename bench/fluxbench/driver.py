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
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

# Uniform across arms. AskUserQuestion is denied because a headless run has no
# user: an arm whose workflow asks a question would otherwise stall or, worse,
# be silently handicapped relative to arms that never ask.
DISALLOWED_TOOLS = ["AskUserQuestion"]
DEFAULT_TIMEOUT_S = 1800


@dataclass
class SessionOutcome:
    ok: bool
    payload: Dict[str, Any]
    stdout: str
    stderr: str
    wall_ms: int
    argv: List[str]
    error: str = ""


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
    if not ok and not error:
        error = str(payload.get("api_error_status") or payload.get("terminal_reason") or "session failed")
    return SessionOutcome(
        ok=ok,
        payload=payload,
        stdout=proc.stdout,
        stderr=proc.stderr,
        wall_ms=wall_ms,
        argv=argv,
        error=error,
    )
