"""Loading a ticket brief. At M0 the brief is a file a human wrote."""

from __future__ import annotations

from pathlib import Path

import pytest

from flux.config import FluxConfig
from flux.errors import ConfigError
from flux.tickets import load_ticket, ticket_path


def write_ticket(root: Path, ticket_id: str, brief: str) -> Path:
    path = ticket_path(root, ticket_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(brief, encoding="utf-8")
    return path


def test_a_ticket_loads_its_brief_and_addressing(tmp_path: Path) -> None:
    write_ticket(tmp_path, "flux-1", "  Add a --json flag.  \n")
    ticket = load_ticket("flux-1", root=tmp_path)

    assert ticket.brief == "Add a --json flag."
    assert ticket.ticket_id == "flux-1"
    assert ticket.root == tmp_path.resolve()
    assert ticket.worktree == tmp_path.resolve()
    assert ticket.context_dir == tmp_path.resolve() / ".flux" / "context" / "flux-1"


def test_loop_bounds_come_from_the_repo_config(tmp_path: Path) -> None:
    write_ticket(tmp_path, "flux-1", "work")
    (tmp_path / ".flux" / "flux.toml").write_text("[runner]\nmax_review_iters = 2\n", "utf-8")

    ticket = load_ticket("flux-1", root=tmp_path, config=FluxConfig.load(tmp_path))
    assert ticket.config.max_review_iters == 2


def test_a_separate_worktree_can_be_given(tmp_path: Path) -> None:
    write_ticket(tmp_path, "flux-1", "work")
    worktree = tmp_path / "wt"
    worktree.mkdir()

    ticket = load_ticket("flux-1", root=tmp_path, worktree=worktree)
    assert ticket.worktree == worktree.resolve()
    assert ticket.context_dir.is_relative_to(tmp_path.resolve())


def test_a_missing_brief_names_the_path_to_write(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match=r"ticket\.md"):
        load_ticket("flux-1", root=tmp_path)


def test_an_empty_brief_is_the_same_mistake(tmp_path: Path) -> None:
    write_ticket(tmp_path, "flux-1", "   \n")
    with pytest.raises(ConfigError, match="is empty"):
        load_ticket("flux-1", root=tmp_path)


def test_an_unsafe_ticket_id_is_rejected_before_a_path_is_built_from_it(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not a safe path component"):
        ticket_path(tmp_path, "../escape")
    with pytest.raises(ConfigError, match="not a safe path component"):
        load_ticket("../escape", root=tmp_path)
