"""``GateSpec`` — a gate as data, so ``flux.toml`` can name one.

The suite a repo runs is configuration, not code: a Python target wants
ruff/pyright/pytest, a TypeScript one wants eslint/tsc/vitest, and a repo with its own
``just check`` wants that. ``kind`` picks only how the output is summarised; the
verdict always comes from the command.
"""

from __future__ import annotations

import shlex
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, cast, get_args

from flux.errors import ConfigError
from flux.gates.command import CommandGate, Summarizer, default_summary
from flux.gates.coverage import CoverageGate
from flux.gates.summaries import pyright_summary, pytest_summary, ruff_summary
from flux.jsonio import JsonMapping
from flux.proc import DEFAULT_TIMEOUT_S
from flux.runner.stage import Gate

GateKind = Literal["command", "ruff", "pyright", "pytest", "coverage"]
GATE_KINDS: frozenset[str] = frozenset(get_args(GateKind))

_SUMMARIZERS: dict[str, Summarizer] = {
    "command": default_summary,
    "ruff": ruff_summary,
    "pyright": pyright_summary,
    "pytest": pytest_summary,
}


@dataclass(frozen=True, slots=True)
class GateSpec:
    """One configured gate."""

    name: str
    command: tuple[str, ...]
    kind: GateKind = "command"
    timeout_s: int = DEFAULT_TIMEOUT_S
    min_percent: float = 0.0
    """Coverage floor. Only read by the ``coverage`` kind."""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ConfigError("a gate needs a non-empty name")
        if not self.command:
            raise ConfigError(f"gate {self.name!r} has an empty command")
        if self.kind not in GATE_KINDS:
            raise ConfigError(f"gate {self.name!r} has unknown kind {self.kind!r}")
        if self.timeout_s <= 0:
            raise ConfigError(f"gate {self.name!r} needs a positive timeout, got {self.timeout_s}")
        if not 0.0 <= self.min_percent <= 100.0:
            raise ConfigError(
                f"gate {self.name!r} min_percent must be between 0 and 100, got {self.min_percent}"
            )

    @classmethod
    def parse(cls, payload: JsonMapping, *, default_timeout_s: int = DEFAULT_TIMEOUT_S) -> GateSpec:
        """Build a spec from one ``[[gates]]`` table.

        ``command`` accepts a string (split with shell-like quoting but never run
        through a shell) or an argv list, so a repo can spell either.
        """
        name = payload.get("name")
        if not isinstance(name, str):
            raise ConfigError("every [[gates]] entry needs a string 'name'")
        kind = payload.get("kind", "command")
        if not isinstance(kind, str):
            raise ConfigError(f"gate {name!r}: 'kind' must be a string")
        timeout = payload.get("timeout_s", default_timeout_s)
        if not isinstance(timeout, int) or isinstance(timeout, bool):
            raise ConfigError(f"gate {name!r}: 'timeout_s' must be an integer")
        minimum = payload.get("min_percent", 0.0)
        if isinstance(minimum, bool) or not isinstance(minimum, int | float):
            raise ConfigError(f"gate {name!r}: 'min_percent' must be a number")
        return cls(
            name=name,
            command=_argv(name, payload.get("command")),
            kind=_kind(kind),
            timeout_s=timeout,
            min_percent=float(minimum),
        )

    def to_toml(self) -> str:
        """Render the spec as a ``[[gates]]`` table, for ``flux init``."""
        lines = [
            "[[gates]]",
            f'name = "{self.name}"',
            f'kind = "{self.kind}"',
            f"command = {list(self.command)!r}".replace("'", '"'),
        ]
        if self.timeout_s != DEFAULT_TIMEOUT_S:
            lines.append(f"timeout_s = {self.timeout_s}")
        if self.kind == "coverage":
            lines.append(f"min_percent = {self.min_percent}")
        return "\n".join(lines)

    def build(self) -> Gate:
        """Instantiate the gate this spec describes."""
        if self.kind == "coverage":
            return CoverageGate(
                name=self.name,
                argv=self.command,
                min_percent=self.min_percent,
                timeout_s=self.timeout_s,
            )
        return CommandGate(
            name=self.name,
            argv=self.command,
            timeout_s=self.timeout_s,
            summarize=_SUMMARIZERS[self.kind],
        )


def build_gates(specs: Sequence[GateSpec]) -> tuple[Gate, ...]:
    """Instantiate a whole suite, in the order it was configured."""
    return tuple(spec.build() for spec in specs)


def bash_permission(command: Sequence[str]) -> str:
    """The ``allowed_tools`` entry that pre-approves exactly ``command``."""
    return f"Bash({shlex.join(command)}:*)"


def bash_permissions(specs: Sequence[GateSpec]) -> tuple[str, ...]:
    """Tool permissions that let a session run its own gates and nothing else.

    A headless session has nobody to approve a tool prompt, so without this the
    instruction "run the gates before you finish" is one the stage cannot follow — and
    it will instead reason its way to a conclusion it could have measured. Granting
    exactly the configured commands adds no authority the harness was not going to
    exercise anyway: flux runs these same commands itself moments later.
    """
    return tuple(bash_permission(spec.command) for spec in specs)


def _argv(name: str, value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return tuple(shlex.split(value))
    if isinstance(value, list):
        parts: list[str] = []
        for item in cast(list[object], value):
            if not isinstance(item, str):
                raise ConfigError(f"gate {name!r}: every 'command' element must be a string")
            parts.append(item)
        return tuple(parts)
    raise ConfigError(f"gate {name!r}: 'command' must be a string or a list of strings")


def _kind(value: str) -> GateKind:
    if value not in GATE_KINDS:
        raise ConfigError(f"gate kind {value!r} not one of {sorted(GATE_KINDS)}")
    return value  # pyright: ignore[reportReturnType]
