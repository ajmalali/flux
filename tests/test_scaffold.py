"""``flux init``: idempotent, non-destructive, and honest about a repo it cannot gate."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from flux.config import CONFIG_FILENAME, FluxConfig
from flux.errors import ConfigError
from flux.scaffold import COMMITTED_DIRS, IGNORED_DIRS, init_repo, install_post_merge_hook


def python_repo(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    return tmp_path


def test_init_creates_the_whole_flux_namespace(tmp_path: Path) -> None:
    report = init_repo(python_repo(tmp_path))
    flux = tmp_path / ".flux"
    for name in (*COMMITTED_DIRS, *IGNORED_DIRS):
        assert (flux / name).is_dir()
    assert (flux / CONFIG_FILENAME).exists()
    assert (flux / ".gitignore").exists()
    assert report.target == "python"


def test_committed_directories_get_a_gitkeep_so_they_survive_a_clone(tmp_path: Path) -> None:
    init_repo(python_repo(tmp_path))
    for name in COMMITTED_DIRS:
        assert (tmp_path / ".flux" / name / ".gitkeep").exists()
    for name in IGNORED_DIRS:
        assert not (tmp_path / ".flux" / name / ".gitkeep").exists()


def test_the_gitignore_covers_exactly_the_machine_state(tmp_path: Path) -> None:
    init_repo(python_repo(tmp_path))
    ignored = (tmp_path / ".flux" / ".gitignore").read_text(encoding="utf-8")
    for name in IGNORED_DIRS:
        assert f"{name}/" in ignored
    for name in COMMITTED_DIRS:
        assert f"{name}/" not in ignored


def test_the_written_config_loads_back(tmp_path: Path) -> None:
    init_repo(python_repo(tmp_path))
    config = FluxConfig.load(tmp_path)
    assert [g.name for g in config.gates] == ["lint", "typecheck", "test"]
    assert config.profile("implement").effort == "high"


def test_init_is_idempotent(tmp_path: Path) -> None:
    init_repo(python_repo(tmp_path))
    second = init_repo(tmp_path)
    assert second.created == ()
    assert f".flux/{CONFIG_FILENAME}" in second.skipped


def test_init_never_silently_rewrites_a_tuned_gate_suite(tmp_path: Path) -> None:
    init_repo(python_repo(tmp_path))
    config_file = tmp_path / ".flux" / CONFIG_FILENAME
    extra = '\n[[gates]]\nname = "e2e"\ncommand = "just e2e"\n'
    tuned = config_file.read_text(encoding="utf-8") + extra
    config_file.write_text(tuned, encoding="utf-8")

    init_repo(tmp_path)
    assert "e2e" in config_file.read_text(encoding="utf-8")


def test_force_rewrites_the_config(tmp_path: Path) -> None:
    init_repo(python_repo(tmp_path))
    config_file = tmp_path / ".flux" / CONFIG_FILENAME
    config_file.write_text("schema_version = 1\n", encoding="utf-8")

    report = init_repo(tmp_path, force=True)
    assert f".flux/{CONFIG_FILENAME}" in report.created
    assert tomllib.loads(config_file.read_text(encoding="utf-8"))["gates"]


def test_a_repo_flux_cannot_gate_says_so(tmp_path: Path) -> None:
    """An ungated pipeline is a real decision, not a default to ship quietly."""
    report = init_repo(tmp_path)
    assert report.target == "generic"
    assert any("no gates" in w for w in report.warnings)
    assert FluxConfig.load(tmp_path).gates == ()


def test_the_warning_repeats_on_a_rerun_that_kept_the_config(tmp_path: Path) -> None:
    init_repo(tmp_path)
    assert any("no gates" in w for w in init_repo(tmp_path).warnings)


def test_init_on_a_missing_directory_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not a directory"):
        init_repo(tmp_path / "nope")


def test_init_does_not_touch_the_repo_outside_flux(tmp_path: Path) -> None:
    python_repo(tmp_path)
    before = sorted(p.name for p in tmp_path.iterdir())
    init_repo(tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted([*before, ".flux"])


def test_a_directory_that_already_has_content_gets_no_placeholder(tmp_path: Path) -> None:
    """A .gitkeep next to real files is litter — it only exists to hold an empty dir."""
    adr = tmp_path / ".flux" / "adr"
    adr.mkdir(parents=True)
    (adr / "0001-something.md").write_text("# ADR", encoding="utf-8")

    init_repo(python_repo(tmp_path))

    assert not (adr / ".gitkeep").exists()
    assert (tmp_path / ".flux" / "plans" / ".gitkeep").exists()


# -- the post-merge hook (opt-in) --------------------------------------------------


def git_repo(tmp_path: Path) -> Path:
    (tmp_path / ".git" / "hooks").mkdir(parents=True)
    return tmp_path


def test_the_hook_is_not_installed_by_plain_init(tmp_path: Path) -> None:
    """A hook runs on every merge in a repo flux does not own — never install it silently."""
    git_repo(python_repo(tmp_path))
    init_repo(tmp_path)
    assert not (tmp_path / ".git" / "hooks" / "post-merge").exists()


def test_installing_the_hook_writes_an_executable_script(tmp_path: Path) -> None:
    git_repo(tmp_path)
    path, note = install_post_merge_hook(tmp_path)

    assert note == "installed"
    assert path.read_text(encoding="utf-8").startswith("#!/bin/sh")
    assert "flux.cli index" in path.read_text(encoding="utf-8")
    assert path.stat().st_mode & 0o111


def test_the_hook_can_never_fail_a_merge(tmp_path: Path) -> None:
    """A ranker problem must not become a git problem; staleness is caught at hydration."""
    git_repo(tmp_path)
    path, _ = install_post_merge_hook(tmp_path)
    assert path.read_text(encoding="utf-8").rstrip().endswith("|| true")


def test_installing_twice_is_a_no_op(tmp_path: Path) -> None:
    git_repo(tmp_path)
    install_post_merge_hook(tmp_path)
    _, note = install_post_merge_hook(tmp_path)
    assert note == "already installed"


def test_someone_elses_hook_is_never_clobbered(tmp_path: Path) -> None:
    git_repo(tmp_path)
    existing = tmp_path / ".git" / "hooks" / "post-merge"
    existing.write_text("#!/bin/sh\nmake deps\n", encoding="utf-8")

    _, note = install_post_merge_hook(tmp_path)

    assert "already exists" in note
    assert "make deps" in existing.read_text(encoding="utf-8")


def test_force_replaces_an_existing_hook(tmp_path: Path) -> None:
    git_repo(tmp_path)
    existing = tmp_path / ".git" / "hooks" / "post-merge"
    existing.write_text("#!/bin/sh\nmake deps\n", encoding="utf-8")

    _, note = install_post_merge_hook(tmp_path, force=True)

    assert note == "installed"
    assert "make deps" not in existing.read_text(encoding="utf-8")


def test_a_non_git_repo_says_so(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not a git repository"):
        install_post_merge_hook(tmp_path)


def test_an_edited_gitignore_survives_init(tmp_path: Path) -> None:
    """What a repo tracks is that repo's decision, so init never restores the default.

    Not even under ``--force``, which is scoped to ``flux.toml``. Silently re-ignoring a
    directory the repo chose to track would revert the decision with no trace — the same
    reason ``flux index --install-hook`` refuses to clobber a live hook.
    """
    root = python_repo(tmp_path)
    init_repo(root)
    edited = "# ours\ntranscripts/\nusage/\ncache/\n"
    (tmp_path / ".flux" / ".gitignore").write_text(edited, encoding="utf-8")

    report = init_repo(root, force=True)

    assert (tmp_path / ".flux" / ".gitignore").read_text(encoding="utf-8") == edited
    assert any("state/" in warning for warning in report.warnings)


def test_a_comment_naming_a_directory_is_not_read_as_a_rule(tmp_path: Path) -> None:
    """The explanation for tracking `state/` contains the string `state/`."""
    root = python_repo(tmp_path)
    init_repo(root)
    (tmp_path / ".flux" / ".gitignore").write_text(
        "# state/ is deliberately tracked here\ntranscripts/\nusage/\ncache/\n", encoding="utf-8"
    )
    assert any("state/" in warning for warning in init_repo(root).warnings)


def test_an_unedited_gitignore_says_nothing(tmp_path: Path) -> None:
    root = python_repo(tmp_path)
    init_repo(root)
    assert init_repo(root).warnings == ()
