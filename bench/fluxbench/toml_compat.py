"""TOML for bench specs.

bin/flux carries a hand-rolled fallback parser so the CLI can stay Python 3.9
compatible, but that parser only covers the flat subset flux itself emits -- no
arrays of tables, which is exactly what an arm's step sequence needs. Rather
than silently mis-parse an arm spec (and quietly hand the comparison to whoever
happens to parse correctly), the bench requires a real TOML reader and says so.

The 3.9 floor is a constraint on the shipped CLI, not on this developer tool.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

try:
    import tomllib as _toml
except ImportError:  # pragma: no cover - depends on interpreter version
    try:
        import tomli as _toml  # type: ignore
    except ImportError:
        _toml = None  # type: ignore


def load_toml(path: Path) -> Dict[str, Any]:
    if _toml is None:
        raise RuntimeError(
            "fluxbench needs a TOML reader: Python >= 3.11 (tomllib) or `pip install tomli`. "
            "bin/flux's fallback parser cannot express arm step sequences and would "
            "mis-parse them silently."
        )
    with Path(path).open("rb") as fh:
        return _toml.load(fh)
