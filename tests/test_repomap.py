"""The repo map adapter: cache it, know when it went stale, slice it to fit.

The extraction is bought (ADR 0009), so nothing here tests a ranking algorithm. What is
tested is everything flux owns around it — and the rule that a map which cannot be
produced is an error, never an empty map that would later read as "this repo has no
important files".
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from flux.config import FluxConfig
from flux.errors import ConfigError, FluxError
from flux.knowledge import RepoMap, RepoMapConfig, RepoMapEntry, cache_path, generate, load

PY = sys.executable

PAYLOAD = {
    "root": "/repo",
    "file_count": 42,
    "entries": [
        {"rank": 1, "path": "src/core.py", "score": 1.0, "language": "python", "lines": 120},
        {"rank": 2, "path": ".flux/plans/x.md", "score": 0.9, "language": "markdown", "lines": 5},
        {"rank": 3, "path": "src/util.py", "score": 0.4, "language": "python", "lines": 60},
    ],
}


def ranker(
    tmp_path: Path, payload: object = PAYLOAD, *, code: int = 0, noise: str = ""
) -> tuple[str, ...]:
    """A stand-in for `repowiki map`: prints a fixed payload, exits how we say."""
    script = tmp_path / "ranker.py"
    script.write_text(
        f"import sys\nsys.stdout.write({noise!r})\n"
        f"sys.stdout.write({json.dumps(payload)!r})\nsys.exit({code})\n",
        encoding="utf-8",
    )
    return (PY, str(script))


def test_generate_caches_a_ranked_map(tmp_path: Path) -> None:
    report = generate(tmp_path, RepoMapConfig(command=ranker(tmp_path)), head="abc123")

    assert report.path == cache_path(tmp_path)
    assert report.path.exists()
    assert report.map.file_count == 42
    assert report.map.head == "abc123"
    assert report.map.generated_at


def test_flux_owned_paths_are_dropped(tmp_path: Path) -> None:
    """A ranker will happily rank flux's own artifacts; they are not the repo's code."""
    report = generate(tmp_path, RepoMapConfig(command=ranker(tmp_path)))

    assert [e.path for e in report.map.entries] == ["src/core.py", "src/util.py"]
    assert any("dropped 1" in w for w in report.warnings)


def test_the_cache_round_trips(tmp_path: Path) -> None:
    generate(tmp_path, RepoMapConfig(command=ranker(tmp_path)), head="abc123")

    loaded = load(tmp_path)
    assert loaded is not None
    assert [e.path for e in loaded.entries] == ["src/core.py", "src/util.py"]
    assert loaded.head == "abc123"
    assert loaded.command[0] == PY


def test_no_cache_reads_as_absent_not_empty(tmp_path: Path) -> None:
    assert load(tmp_path) is None


def test_a_corrupt_cache_reads_as_absent(tmp_path: Path) -> None:
    path = cache_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")
    assert load(tmp_path) is None


def test_progress_chatter_before_the_json_is_tolerated(tmp_path: Path) -> None:
    command = ranker(tmp_path, noise="Downloading repowiki...\nInstalled 57 packages\n")
    report = generate(tmp_path, RepoMapConfig(command=command))
    assert len(report.map.entries) == 2


def test_a_ranker_that_cannot_run_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(FluxError, match="not on PATH"):
        generate(tmp_path, RepoMapConfig(command=("flux-no-such-ranker",)))


def test_a_ranker_that_fails_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(FluxError, match="exited 2"):
        generate(tmp_path, RepoMapConfig(command=ranker(tmp_path, code=2)))


def test_output_that_is_not_json_is_an_error(tmp_path: Path) -> None:
    script = tmp_path / "bad.py"
    script.write_text("print('no json here')", encoding="utf-8")
    with pytest.raises(FluxError, match="no JSON object"):
        generate(tmp_path, RepoMapConfig(command=(PY, str(script))))


def test_json_without_entries_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(FluxError, match="no 'entries' array"):
        generate(tmp_path, RepoMapConfig(command=ranker(tmp_path, {"file_count": 3})))


def test_an_empty_map_is_warned_about_rather_than_passed_off_as_a_result(tmp_path: Path) -> None:
    report = generate(tmp_path, RepoMapConfig(command=ranker(tmp_path, {"entries": []})))
    assert report.map.entries == ()
    assert any("no files" in w for w in report.warnings)


def test_the_kept_map_is_not_shrunk_by_exclusions(tmp_path: Path) -> None:
    """Exclusions are applied after the ranker picked its top N, so flux overfetches."""
    entries = [{"path": f"src/m{n}.py", "score": 1.0 / (n + 1)} for n in range(10)]
    entries.insert(0, {"path": ".flux/noise.md", "score": 9.9})
    config = RepoMapConfig(command=ranker(tmp_path, {"entries": entries}), top=5)
    report = generate(tmp_path, config)

    assert len(report.map.entries) == 5
    assert all(not e.path.startswith(".flux/") for e in report.map.entries)


def test_staleness_is_a_moved_head(tmp_path: Path) -> None:
    generated = RepoMap(head="abc123")
    assert generated.is_stale("def456")
    assert not generated.is_stale("abc123")


def test_staleness_is_unknowable_without_a_head_on_either_side() -> None:
    """A non-git worktree is not evidence of freshness, but it is not evidence of rot."""
    assert not RepoMap(head="").is_stale("abc123")
    assert not RepoMap(head="abc123").is_stale("")


def test_render_fits_a_limit_and_says_what_it_left_out() -> None:
    entries = tuple(RepoMapEntry(path=f"src/m{n}.py", score=0.5, lines=n) for n in range(10))
    rendered = RepoMap(entries=entries).render(limit=3)

    assert rendered.count("\n") == 3  # three rows plus the summary line
    assert "and 7 further files" in rendered


def test_render_of_an_empty_map_is_empty() -> None:
    assert RepoMap().render() == ""


@pytest.mark.parametrize(
    "kwargs",
    [{"command": ()}, {"top": 0}, {"pack_entries": 0}, {"timeout_s": 0}],
)
def test_a_nonsensical_config_is_rejected(kwargs: dict[str, object]) -> None:
    with pytest.raises(ConfigError):
        RepoMapConfig(**kwargs)  # pyright: ignore[reportArgumentType]


def test_the_command_is_configurable_from_flux_toml(tmp_path: Path) -> None:
    path = tmp_path / ".flux" / "flux.toml"
    path.parent.mkdir(parents=True)
    path.write_text(
        '[repo_map]\ncommand = "my-ranker --fast"\ntop = 12\npack_entries = 4\n', encoding="utf-8"
    )
    config = FluxConfig.load(tmp_path).repo_map

    assert config.command == ("my-ranker", "--fast")
    assert (config.top, config.pack_entries) == (12, 4)


def test_the_default_command_survives_a_config_round_trip(tmp_path: Path) -> None:
    path = tmp_path / ".flux" / "flux.toml"
    path.parent.mkdir(parents=True)
    path.write_text(FluxConfig(root=tmp_path).to_toml(), encoding="utf-8")
    assert FluxConfig.load(tmp_path).repo_map == RepoMapConfig()
