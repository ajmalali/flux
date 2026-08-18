"""Required artifacts and the runner-side check on them (design.md §2, Rule 1).

A stage is done when its artifact validates, not when the model says it is. The
prompt asks for the artifact; this module is the guarantee. Everything here is plain
file IO and parsing — no model is consulted, so "did the handoff work?" is a question
pytest can answer.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

from flux.errors import ConfigError
from flux.jsonio import JsonMapping, as_json_mapping
from flux.runner.context import TicketContext

ArtifactKind = Literal["json", "text"]


@dataclass(frozen=True, slots=True)
class ArtifactSpec:
    """What a stage must leave behind, and how the runner recognises it."""

    path: str
    """Path relative to the ticket's ``.flux/context/<ticket>/`` directory."""

    kind: ArtifactKind = "json"
    required_keys: tuple[str, ...] = ()
    """Top-level keys a ``json`` artifact must carry."""

    required_sections: tuple[str, ...] = ()
    """Markdown headings a ``text`` artifact must carry — the skeleton, checked literally."""

    min_chars: int = 1
    description: str = ""
    """One line naming the artifact's job. Quoted back to the model in the retry nudge."""

    def __post_init__(self) -> None:
        pure = PurePosixPath(self.path)
        if not self.path or pure.is_absolute() or ".." in pure.parts:
            raise ConfigError(
                f"ArtifactSpec.path must be a relative path inside the context dir, "
                f"got {self.path!r}"
            )
        if self.kind not in ("json", "text"):
            raise ConfigError(f"ArtifactSpec.kind {self.kind!r} must be 'json' or 'text'")
        if self.kind != "json" and self.required_keys:
            raise ConfigError("ArtifactSpec.required_keys only applies to json artifacts")
        if self.kind != "text" and self.required_sections:
            raise ConfigError("ArtifactSpec.required_sections only applies to text artifacts")
        if self.min_chars < 0:
            raise ConfigError(f"ArtifactSpec.min_chars must not be negative, got {self.min_chars}")

    def resolve(self, ticket: TicketContext) -> Path:
        return ticket.context_dir / self.path


@dataclass(frozen=True, slots=True)
class ArtifactCheck:
    """The verdict on one artifact, plus its parsed content so callers need not re-read."""

    ok: bool
    path: Path
    spec: ArtifactSpec | None = None
    problem: str = ""
    """Empty when ``ok``. Otherwise a sentence naming what is wrong, shown to the model."""

    digest: str = ""
    """SHA-256 of the file's bytes, recorded in the checkpoint so a later stage can tell
    whether the artifact it is reading is the one that was validated."""

    payload: JsonMapping | None = None
    text: str = ""

    @classmethod
    def not_required(cls, ticket: TicketContext) -> ArtifactCheck:
        """The verdict for a stage that declares no artifact."""
        return cls(ok=True, path=ticket.context_dir)


def validate_artifact(ticket: TicketContext, spec: ArtifactSpec | None) -> ArtifactCheck:
    """Check the artifact ``spec`` describes, reading it from disk."""
    if spec is None:
        return ArtifactCheck.not_required(ticket)

    path = spec.resolve(ticket)
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return ArtifactCheck(ok=False, path=path, spec=spec, problem="the file does not exist")
    except OSError as exc:
        return ArtifactCheck(ok=False, path=path, spec=spec, problem=f"it could not be read: {exc}")

    digest = hashlib.sha256(raw).hexdigest()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return ArtifactCheck(
            ok=False, path=path, spec=spec, problem="it is not valid UTF-8", digest=digest
        )
    if len(text.strip()) < spec.min_chars:
        return ArtifactCheck(
            ok=False,
            path=path,
            spec=spec,
            problem=f"it is shorter than the required {spec.min_chars} characters",
            digest=digest,
            text=text,
        )

    if spec.kind == "json":
        return _check_json(path, spec, text, digest)
    return _check_text(path, spec, text, digest)


def _check_json(path: Path, spec: ArtifactSpec, text: str, digest: str) -> ArtifactCheck:
    try:
        parsed: object = json.loads(text)
    except json.JSONDecodeError as exc:
        return ArtifactCheck(
            ok=False,
            path=path,
            spec=spec,
            problem=f"it is not valid JSON ({exc.msg} at line {exc.lineno})",
            digest=digest,
            text=text,
        )
    payload = as_json_mapping(parsed)
    if payload is None:
        return ArtifactCheck(
            ok=False,
            path=path,
            spec=spec,
            problem="its top level is not a JSON object",
            digest=digest,
            text=text,
        )
    missing = [key for key in spec.required_keys if key not in payload]
    if missing:
        return ArtifactCheck(
            ok=False,
            path=path,
            spec=spec,
            problem=f"it is missing the required key(s): {', '.join(missing)}",
            digest=digest,
            payload=payload,
            text=text,
        )
    return ArtifactCheck(ok=True, path=path, spec=spec, digest=digest, payload=payload, text=text)


def _check_text(path: Path, spec: ArtifactSpec, text: str, digest: str) -> ArtifactCheck:
    missing = [section for section in spec.required_sections if not _has_heading(text, section)]
    if missing:
        return ArtifactCheck(
            ok=False,
            path=path,
            spec=spec,
            problem=f"it is missing the required heading(s): {', '.join(missing)}",
            digest=digest,
            text=text,
        )
    return ArtifactCheck(ok=True, path=path, spec=spec, digest=digest, text=text)


def _has_heading(text: str, section: str) -> bool:
    pattern = re.compile(rf"^\s*#{{1,6}}\s+{re.escape(section)}\s*$", re.IGNORECASE | re.MULTILINE)
    return pattern.search(text) is not None


def missing_artifact_nudge(check: ArtifactCheck, *, context_dir: Path) -> str:
    """The appendix appended to the pack for the single artifact retry (design.md §1).

    Says exactly which file, exactly what was wrong, and exactly what must be in it —
    the retry is worth spending only if it removes the ambiguity that lost the first one.
    """
    spec = check.spec
    if spec is None:
        return ""
    try:
        shown = check.path.relative_to(context_dir)
    except ValueError:
        shown = check.path
    lines = [
        "## Required artifact missing",
        "",
        f"The previous attempt did not leave a valid `{shown}` in `{context_dir}`: "
        f"{check.problem}.",
    ]
    if spec.description:
        lines.append(f"That file is the stage's handoff artifact — {spec.description}")
    if spec.kind == "json":
        lines.append("Write it as a JSON object.")
        if spec.required_keys:
            keys = ", ".join(f"`{k}`" for k in spec.required_keys)
            lines.append(f"It must contain these top-level keys: {keys}.")
    else:
        if spec.required_sections:
            heads = ", ".join(f"`## {s}`" for s in spec.required_sections)
            lines.append(f"It must contain these Markdown headings: {heads}.")
    lines.append(
        "Do the work needed to produce it, then write the file. Nothing else from this "
        "session is read by the next stage."
    )
    return "\n".join(lines)


FAILED_SESSION_NUDGE = (
    "## Previous attempt failed\n"
    "\n"
    "The previous session ended without completing the task. Work in smaller steps and "
    "make sure the required artifact is written before you finish."
)
