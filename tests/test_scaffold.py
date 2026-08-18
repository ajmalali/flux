"""``flux init``: idempotent, non-destructive, and honest about a repo it cannot gate."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from flux.config import CONFIG_FILENAME, FluxConfig
from flux.errors import ConfigError
from flux.scaffold import COMMITTED_DIRS, IGNORED_DIRS, init_repo


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
