"""Running a subprocess and reporting only what was observed.

Shared by the gate suite and the git helpers. The contract is that nothing raises: a
missing binary, a timeout and a non-zero exit are all ordinary results the caller turns
into a verdict. A helper that raised would let "we could not check" reach the runner
looking like "there was nothing to check".
"""

from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

DEFAULT_TIMEOUT_S = 600

MAX_DETAIL_CHARS = 2_000
"""Cap on a captured detail string. Details land in ``metrics.jsonl``, which stays greppable."""

ENVIRONMENT_TRAPS: tuple[str, ...] = (
    "VIRTUAL_ENV",
    "CONDA_PREFIX",
    "CONDA_DEFAULT_ENV",
    "PYTHONHOME",
    "PYTHONPATH",
    "UV_PROJECT",
    "UV_PROJECT_ENVIRONMENT",
)
"""Variables that would make a child resolve tools or imports from *flux's* environment.

flux is itself a Python program, usually launched from its own virtualenv, and a gate is
a subprocess of it. Left alone, a target repo's ``pytest`` gate can import flux's
site-packages and a ``pyright`` gate can resolve flux's pyright — reporting a confident
green about an environment the repo does not have. Same principle as the ADR 0010
credential strip: the parent's environment must not change what the child measures.
"""


def clean_env(base: Mapping[str, str] | None = None) -> dict[str, str]:
    """``base`` (default :data:`os.environ`) with flux's own environment removed.

    Removes the trap variables *and* the ``bin`` directories they point at from ``PATH``,
    because unsetting ``VIRTUAL_ENV`` alone still leaves flux's interpreter first on the
    path.
    """
    env = dict(os.environ if base is None else base)
    shadowed = [env[name] for name in ("VIRTUAL_ENV", "CONDA_PREFIX") if env.get(name)]
    for name in ENVIRONMENT_TRAPS:
        env.pop(name, None)
    path = env.get("PATH")
    if path and shadowed:
        unwanted = {str(Path(prefix) / "bin") for prefix in shadowed}
        kept = [entry for entry in path.split(os.pathsep) if entry not in unwanted]
        env["PATH"] = os.pathsep.join(kept)
    return env


@dataclass(frozen=True, slots=True)
class CommandRun:
    """What one subprocess did. Raw material for a verdict or a summary."""

    argv: tuple[str, ...]
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0

    launched: bool = True
    """False when the executable could not be started at all."""

    timed_out: bool = False
    fault: str = ""
    """Why the command never produced an exit status, when it did not."""

    @property
    def output(self) -> str:
        """stdout and stderr in the order a human reads them."""
        return "\n".join(part for part in (self.stdout.strip(), self.stderr.strip()) if part)

    @property
    def completed(self) -> bool:
        return self.launched and not self.timed_out


def tail(text: str, *, lines: int = 12, limit: int = MAX_DETAIL_CHARS) -> str:
    """The last ``lines`` lines of ``text``, clipped to ``limit`` characters.

    Failure output is read bottom-up — the assertion, the error count, the summary
    line all live at the end — so the tail is the part worth keeping.
    """
    kept = [line for line in text.splitlines() if line.strip()][-lines:]
    joined = "\n".join(kept).strip()
    if len(joined) <= limit:
        return joined
    return "…" + joined[-(limit - 1) :]


def run_command(
    argv: Sequence[str],
    *,
    cwd: Path,
    timeout_s: int = DEFAULT_TIMEOUT_S,
    env: Mapping[str, str] | None = None,
) -> CommandRun:
    """Run ``argv`` in ``cwd`` without a shell, and report what happened.

    No exception escapes: a missing binary, a timeout and a non-zero exit are all
    ordinary gate results, and the caller turns them into a failed :class:`GateOutcome`.
    """
    frozen = tuple(argv)
    started = time.monotonic()

    def elapsed() -> int:
        return int((time.monotonic() - started) * 1000)

    if not frozen:
        return CommandRun(argv=frozen, launched=False, fault="the gate has no command to run")
    try:
        # argv form, never a shell string: gate commands come from flux.toml and
        # must not become an injection surface.
        proc = subprocess.run(
            frozen,
            cwd=cwd,
            env=dict(env) if env is not None else None,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout_s,
            check=False,
        )
    except (FileNotFoundError, NotADirectoryError):
        # Both a missing executable and a missing cwd surface as FileNotFoundError, and
        # "binary not on PATH" is a badly misleading way to say "that directory is gone".
        missing = f"{frozen[0]!r} is not on PATH"
        if not cwd.is_dir():
            missing = f"working directory {cwd} does not exist"
        return CommandRun(argv=frozen, launched=False, duration_ms=elapsed(), fault=missing)
    except OSError as exc:
        return CommandRun(
            argv=frozen, launched=False, duration_ms=elapsed(), fault=f"it could not start: {exc}"
        )
    except subprocess.TimeoutExpired as expired:
        return CommandRun(
            argv=frozen,
            timed_out=True,
            duration_ms=elapsed(),
            stdout=_decode(expired.stdout),
            stderr=_decode(expired.stderr),
            fault=f"it did not finish within {timeout_s}s",
        )
    return CommandRun(
        argv=frozen,
        returncode=proc.returncode,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
        duration_ms=elapsed(),
    )


def _decode(value: str | bytes | None) -> str:
    """Partial output captured from a timed-out process arrives typed as ``str | bytes``."""
    if value is None:
        return ""
    return value if isinstance(value, str) else value.decode("utf-8", "replace")
