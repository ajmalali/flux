"""Loading a ticket into a :class:`~flux.runner.context.TicketContext`.

At M0 a ticket is a hand-written Markdown file — ``.flux/context/<ticket>/ticket.md`` —
because the point of M0 is to prove the pipeline, not the ticketing. At M4 the brief
comes from ``bd show`` instead and this module's body changes; its signature does not,
which is why the loading lives here rather than inside a stage.
"""

from __future__ import annotations

from pathlib import Path

from flux.config import FluxConfig
from flux.errors import ConfigError
from flux.runner.context import (
    CONTEXT_DIRNAME,
    FLUX_DIRNAME,
    TicketContext,
    validate_ticket_id,
)

TICKET_FILENAME = "ticket.md"


def ticket_path(root: Path, ticket_id: str) -> Path:
    """Where a ticket's brief lives. Validates the id first — it becomes a directory name."""
    return root / FLUX_DIRNAME / CONTEXT_DIRNAME / validate_ticket_id(ticket_id) / TICKET_FILENAME


def load_ticket(
    ticket_id: str,
    *,
    root: Path,
    config: FluxConfig | None = None,
    worktree: Path | None = None,
) -> TicketContext:
    """Read the ticket's brief and build its context.

    Raises:
        ConfigError: the ticket file is absent or empty. Both are the same mistake —
            a pipeline run with no statement of work — and the message names the path
            to create.
    """
    resolved = root.resolve()
    settings = config if config is not None else FluxConfig.load(resolved)
    path = ticket_path(resolved, ticket_id)
    try:
        brief = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        raise ConfigError(
            f"ticket {ticket_id!r} has no brief: write the statement of work to {path}"
        ) from None
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigError(f"ticket {ticket_id!r}: {path} could not be read: {exc}") from exc
    if not brief:
        raise ConfigError(f"ticket {ticket_id!r}: {path} is empty")
    return TicketContext(
        ticket_id=ticket_id,
        root=resolved,
        worktree=(worktree.resolve() if worktree is not None else resolved),
        brief=brief,
        config=settings.runner,
    )
