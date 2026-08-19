"""``.flux/flux.toml`` — the per-repo configuration (plan.md §4).

What belongs here is everything that differs between target repos and must not differ
between *runs* of the same repo: which gates constitute "green", which model and effort
each stage gets, and the loop bounds. Keeping it on disk rather than in flags is what
makes a run reproducible and a kill-criterion (ADR 0008) auditable.

Defaults are complete: a repo with no ``flux.toml`` still gets a working configuration,
so nothing is silently disabled by an absent file. What is *not* defaulted is the gate
suite for an unrecognised target — a pipeline with no gates is a real decision, and
``flux init`` says so out loud rather than shipping an empty list quietly.
"""

from __future__ import annotations

import shlex
import tomllib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, cast

from flux.errors import ConfigError
from flux.executor.guard import PathGuard
from flux.executor.types import (
    EFFORT_LEVELS,
    NO_HOOKS,
    PERMISSION_MODES,
    EffortLevel,
    ExecConfig,
    PermissionMode,
)
from flux.gates.spec import GateSpec, build_gates
from flux.jsonio import JsonMapping, as_json_list, as_json_mapping
from flux.knowledge.repomap import RepoMapConfig
from flux.proc import DEFAULT_TIMEOUT_S
from flux.runner.context import FLUX_DIRNAME, RunnerConfig
from flux.runner.stage import Gate

CONFIG_FILENAME = "flux.toml"
SCHEMA_VERSION = 1

IMPLEMENT_STAGE = "implement"
VANILLA_STAGE = "vanilla"
"""The A/B baseline arm. Not a pipeline stage — it names the metrics rows and the
optional ``[stages.vanilla]`` override (ADR 0008)."""

SONNET = "claude-sonnet-5"
OPUS = "claude-opus-5"
HAIKU = "claude-haiku-4-5-20251001"


@dataclass(frozen=True, slots=True)
class StageProfile:
    """Model, effort and caps for one stage's sessions.

    Model and effort are required, never inherited from an SDK default (ADR 0007) —
    an unstated model is a silent cost and quality decision.
    """

    model: str
    effort: EffortLevel
    permission_mode: PermissionMode = "acceptEdits"
    max_turns: int = 40
    max_tokens: int = 200_000
    """Uncached tokens the stage may consume before the runner parks it. Cache reads
    are excluded, so this bounds work rather than turns (see ``Usage.budget_tokens``)."""

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise ConfigError("a stage profile needs a model id")
        if self.effort not in EFFORT_LEVELS:
            raise ConfigError(f"stage effort {self.effort!r} not one of {sorted(EFFORT_LEVELS)}")
        if self.permission_mode not in PERMISSION_MODES:
            raise ConfigError(
                f"stage permission_mode {self.permission_mode!r} not one of "
                f"{sorted(PERMISSION_MODES)}"
            )

    def exec_config(
        self,
        *,
        cwd: Path | None = None,
        allowed_tools: Sequence[str] = (),
        disallowed_tools: Sequence[str] = (),
        add_dirs: Sequence[Path] = (),
        guards: Sequence[PathGuard] = (),
        hooks: Mapping[str, Sequence[Any]] | None = None,
    ) -> ExecConfig:
        """Turn the profile into the executor's per-call config."""
        return ExecConfig(
            model=self.model,
            effort=self.effort,
            permission_mode=self.permission_mode,
            allowed_tools=tuple(allowed_tools),
            disallowed_tools=tuple(disallowed_tools),
            max_turns=self.max_turns,
            max_tokens=self.max_tokens,
            cwd=cwd,
            add_dirs=tuple(add_dirs),
            guards=tuple(guards),
            hooks=MappingProxyType(dict(hooks)) if hooks else NO_HOOKS,
        )

    def to_toml(self, stage: str) -> str:
        return "\n".join(
            [
                f"[stages.{stage}]",
                f'model = "{self.model}"',
                f'effort = "{self.effort}"',
                f'permission_mode = "{self.permission_mode}"',
                f"max_turns = {self.max_turns}",
                f"max_tokens = {self.max_tokens}",
            ]
        )


# plan.md §3 routing table. Review deliberately runs a *different* model from the stage
# that wrote the code, and may not touch it — a reviewer that can edit is not a reviewer.
#
# Its read-only-ness is a flux guard, not the SDK's `plan` mode. design.md originally
# specified plan mode; the SDK documents it as "Planning mode, no execution of tools",
# which also stops the reviewer writing `review.json` — the artifact the stage is judged
# on. `review_stage_guard` confines every write to the ticket's context directory
# instead, which forbids more of the repo than plan mode and is provable in pytest.
DEFAULT_STAGE_PROFILES: Mapping[str, StageProfile] = MappingProxyType(
    {
        "tests": StageProfile(model=SONNET, effort="high"),
        "implement": StageProfile(model=SONNET, effort="high"),
        "review": StageProfile(model=OPUS, effort="high", max_turns=30),
        "fix": StageProfile(model=SONNET, effort="high"),
        "pr": StageProfile(model=HAIKU, effort="low", max_turns=15),
    }
)


@dataclass(frozen=True, slots=True)
class AbConfig:
    """The A/B baseline policy and its standing kill-criterion (ADR 0008, design.md §3)."""

    vanilla_every: int = 10
    """Run every Nth ticket through plain ``claude -p`` for comparison. 0 disables."""

    kill_streak: int = 3
    """Consecutive paired samples vanilla must win before the criterion fires.

    The machine-readable half of :attr:`kill_criterion`. The prose is what a human
    reads at a phase gate; this is what ``flux metrics`` actually checks, and they are
    kept adjacent so a change to one is visibly a change to the other."""

    kill_criterion: str = (
        "If vanilla Claude Code wins on cost AND quality for 3 consecutive samples, "
        "freeze harness feature work and investigate."
    )

    def __post_init__(self) -> None:
        if self.vanilla_every < 0:
            raise ConfigError(f"[ab] vanilla_every must not be negative, got {self.vanilla_every}")
        if self.kill_streak <= 0:
            raise ConfigError(f"[ab] kill_streak must be positive, got {self.kill_streak}")


SEVERITIES: tuple[str, ...] = ("blocker", "major", "minor", "nit")
"""Review severities, most serious first. A closed set because the fix loop keys off
it: a severity nobody defined is a finding nobody can route."""


@dataclass(frozen=True, slots=True)
class ReviewConfig:
    """What the reviewer is asked for, and which of its findings turn the fix loop."""

    fix_severities: tuple[str, ...] = ("blocker",)
    """Severities that must be resolved before the ticket may move on (design.md's
    stage I/O table: *blocker findings force fix stage*).

    Deliberately narrow. Every severity in here is one the review↔fix loop will spend
    a paid session on and, at ``max_review_iters``, park a ticket over — so widening it
    converts advisory findings into blocking ones. Lower severities are still recorded
    in ``review.json`` and still read by a human; they simply do not turn the loop.
    """

    max_diff_chars: int = 60_000
    """Cap on the diff the reviewer is shown. Truncation drops whole files and says so
    (a half-shown hunk reads as a complete one)."""

    max_hunks: int = 12
    """Diff hunks the fix stage carries. The pack is findings plus the hunks they point
    at; past a dozen the ticket is too big, which is a decomposition problem rather than
    a context-window one."""

    def __post_init__(self) -> None:
        unknown = [s for s in self.fix_severities if s not in SEVERITIES]
        if unknown:
            raise ConfigError(
                f"[review] fix_severities has unknown severities: {unknown} — "
                f"expected some of {list(SEVERITIES)}"
            )
        if not self.fix_severities:
            raise ConfigError(
                "[review] fix_severities must name at least one severity; with none, no "
                "finding could ever route to the fix stage and the reviewer is decoration"
            )
        if self.max_diff_chars <= 0:
            raise ConfigError(
                f"[review] max_diff_chars must be positive, got {self.max_diff_chars}"
            )
        if self.max_hunks <= 0:
            raise ConfigError(f"[review] max_hunks must be positive, got {self.max_hunks}")

    def blocks(self, severity: str) -> bool:
        return severity in self.fix_severities

    def to_toml(self) -> str:
        return "\n".join(
            [
                "[review]",
                f"fix_severities = {list(self.fix_severities)!r}".replace("'", '"'),
                f"max_diff_chars = {self.max_diff_chars}",
                f"max_hunks = {self.max_hunks}",
            ]
        )


@dataclass(frozen=True, slots=True)
class TestsConfig:
    """Where tests live, how flux runs them, and which tests the implementer never sees.

    The tests stage cannot be judged without a way to run what it wrote, so this is the
    one configuration block whose absence is not survivable: :attr:`command` falls back
    to the repo's own test gate, and if there is no test gate either, the stage says so
    rather than declaring an unverified red step green.
    """

    dir: str = "tests"
    """Where new tests go, relative to the worktree. The tests stage may write here and
    nowhere else; the implement and fix stages may not write here at all."""

    command: tuple[str, ...] = ()
    """Argv for the suite. Empty means "use the test gate's command", which is the
    right default: the red step and the gate must be the same measurement, or a stage
    can be red for the runner and green for the gate."""

    gate: str = ""
    """Name of the ``[[gates]]`` entry that runs the suite. Empty means "the pytest-kind
    gate, or one named 'test'". The tests stage skips it — new tests are red by
    construction, so running the whole suite there would fail the stage for succeeding."""

    held_out_dir: str = ".flux/held-out"
    """Held-out tests, keyed by ticket underneath, relative to the *root*. Outside the
    worktree whenever ``--worktree`` is used, and out of reach of the implement guard
    either way: a test the implementer cannot see is a test it cannot write code around
    (ADR 0005)."""

    timeout_s: int = DEFAULT_TIMEOUT_S

    def __post_init__(self) -> None:
        for name, value in (("dir", self.dir), ("held_out_dir", self.held_out_dir)):
            pure = PurePosixPath(value)
            if not value or pure.is_absolute() or ".." in pure.parts:
                raise ConfigError(f"[tests] {name} must be a relative path, got {value!r}")
        if self.timeout_s <= 0:
            raise ConfigError(f"[tests] timeout_s must be positive, got {self.timeout_s}")

    def to_toml(self) -> str:
        return "\n".join(
            [
                "[tests]",
                f'dir = "{self.dir}"',
                f"command = {list(self.command)!r}".replace("'", '"'),
                f'gate = "{self.gate}"',
                f'held_out_dir = "{self.held_out_dir}"',
            ]
        )


PR_CREATE_MODES: tuple[str, ...] = ("auto", "always", "never")
"""How hard the pr stage tries to open the pull request itself. ``auto`` opens one when
``gh`` is there and shrugs when it is not; ``always`` treats a failure to open one as a
park; ``never`` pushes the branch and stops."""


@dataclass(frozen=True, slots=True)
class PrConfig:
    """Where a finished ticket lands, and what flux refuses to do to get it there.

    This is the one block whose defaults are about *restraint*. Every other stage acts
    inside a checkout that git can reset; the pr stage is the first that leaves the
    machine, and a push cannot be undone by ``git reset --hard``.
    """

    push: bool = True
    """Push the branch when the stage stands. Turning this off leaves a repo whose pr
    stage writes the body and stops — legitimate for a repo with nowhere to land, and
    the only supported way to say so, since a push that *cannot* happen is a failure
    (ADR 0005: a gate that cannot run has failed)."""

    remote: str = "origin"

    base: str = ""
    """Branch the pull request targets. Empty means the remote's own default."""

    branch_prefix: str = "flux/"
    """Prefix for the branch flux opens when the checked-out one may not be pushed."""

    protected_branches: tuple[str, ...] = ("main", "master", "trunk", "develop")
    """Branches flux will never push to. Work done on one of these is pushed to
    ``<branch_prefix><ticket>`` instead — HEAD goes somewhere safe rather than the
    ticket parking after every stage but the last one succeeded."""

    create: str = "auto"
    draft: bool = True
    """Open pull requests as drafts. An unattended harness asking for review is asking
    a human for time; a draft asks for it without also claiming the work is ready."""

    def __post_init__(self) -> None:
        if self.create not in PR_CREATE_MODES:
            raise ConfigError(f"[pr] create {self.create!r} not one of {list(PR_CREATE_MODES)}")
        if self.push and not self.remote.strip():
            raise ConfigError("[pr] remote must be named when push is on")
        if not self.branch_prefix.strip():
            raise ConfigError(
                "[pr] branch_prefix must not be empty — without it, a ticket on a "
                "protected branch has nowhere to be pushed"
            )

    def protects(self, branch: str) -> bool:
        return branch in self.protected_branches

    def to_toml(self) -> str:
        return "\n".join(
            [
                "[pr]",
                f"push = {str(self.push).lower()}",
                f'remote = "{self.remote}"',
                f'base = "{self.base}"',
                f'branch_prefix = "{self.branch_prefix}"',
                f"protected_branches = {list(self.protected_branches)!r}".replace("'", '"'),
                f'create = "{self.create}"',
                f"draft = {str(self.draft).lower()}",
            ]
        )


@dataclass(frozen=True, slots=True)
class FluxConfig:
    """The whole of a target repo's flux configuration."""

    root: Path
    target: str = "python"
    runner: RunnerConfig = field(default_factory=RunnerConfig)
    stages: Mapping[str, StageProfile] = DEFAULT_STAGE_PROFILES
    gates: tuple[GateSpec, ...] = ()
    stage_commits: bool = True
    """Have each stage's ``commit()`` make a git commit tagged ``flux/<ticket>/<stage>``,
    so "reset to the last good stage" is a ``git reset``, not bookkeeping (design.md §1)."""

    ab: AbConfig = field(default_factory=AbConfig)
    repo_map: RepoMapConfig = field(default_factory=RepoMapConfig)
    tests: TestsConfig = field(default_factory=TestsConfig)
    review: ReviewConfig = field(default_factory=ReviewConfig)
    pr: PrConfig = field(default_factory=PrConfig)
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.root.is_absolute():
            raise ConfigError(f"FluxConfig.root must be absolute, got {self.root}")
        names = [g.name for g in self.gates]
        duplicates = sorted({n for n in names if names.count(n) > 1})
        if duplicates:
            raise ConfigError(f"gate names must be unique; repeated: {duplicates}")

    @property
    def path(self) -> Path:
        return config_path(self.root)

    def profile(self, stage: str) -> StageProfile:
        """The profile for ``stage``, or a :class:`ConfigError` naming what is missing.

        The baseline arm mirrors ``implement`` unless the repo states otherwise, and it
        mirrors it *live* rather than by being copied at parse time: the A/B comparison
        only isolates the harness if both arms run the same model at the same effort, so
        re-routing ``implement`` must re-route the baseline with it. An explicit
        ``[stages.vanilla]`` breaks the mirror deliberately.
        """
        if stage == VANILLA_STAGE and stage not in self.stages:
            return self.profile(IMPLEMENT_STAGE)
        try:
            return self.stages[stage]
        except KeyError:
            raise ConfigError(
                f"no [stages.{stage}] profile in {self.path}; every stage needs an "
                "explicit model and effort"
            ) from None

    def build_gates(self, *, exclude: Sequence[str] = ()) -> tuple[Gate, ...]:
        """Instantiate the configured suite, optionally dropping gates by name."""
        return build_gates([spec for spec in self.gates if spec.name not in exclude])

    def test_gate(self) -> GateSpec | None:
        """The gate that runs the suite, if the repo has one.

        Named explicitly by ``[tests] gate`` when the repo says so; otherwise the
        ``pytest``-kind gate, otherwise one called ``test``. Resolution is a lookup
        rather than a guess at the command, so the tests stage and the implement
        stage's test gate can never end up running different suites.
        """
        if self.tests.gate:
            return next((spec for spec in self.gates if spec.name == self.tests.gate), None)
        by_kind = next((spec for spec in self.gates if spec.kind == "pytest"), None)
        if by_kind is not None:
            return by_kind
        return next((spec for spec in self.gates if spec.name == "test"), None)

    def tests_command(self) -> tuple[str, ...]:
        """Argv the red step and the held-out run use. Empty when the repo has neither."""
        if self.tests.command:
            return self.tests.command
        gate = self.test_gate()
        return gate.command if gate is not None else ()

    @classmethod
    def load(cls, root: Path) -> FluxConfig:
        """Read ``<root>/.flux/flux.toml``, falling back to defaults when it is absent."""
        resolved = root.resolve()
        path = config_path(resolved)
        if not path.exists():
            return cls(root=resolved, gates=default_gates(resolved), target=detect_target(resolved))
        try:
            payload = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError) as exc:
            raise ConfigError(f"{path} could not be read: {exc}") from exc
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f"{path} is not valid TOML: {exc}") from exc
        return cls.parse(payload, root=resolved)

    @classmethod
    def parse(cls, payload: JsonMapping, *, root: Path) -> FluxConfig:
        """Build a config from an already-parsed TOML mapping."""
        version = _int(payload, "schema_version", SCHEMA_VERSION)
        if version > SCHEMA_VERSION:
            raise ConfigError(
                f"flux.toml declares schema_version {version}, but this flux understands "
                f"{SCHEMA_VERSION} — upgrade flux rather than guessing at the fields"
            )
        runner_table = _table(payload, "runner")
        gates = tuple(
            GateSpec.parse(entry)
            for entry in _tables(payload, "gates")  # [[gates]] array
        )
        return cls(
            root=root,
            target=_str(payload, "target", detect_target(root)),
            runner=RunnerConfig(
                max_review_iters=_int(runner_table, "max_review_iters", 3),
                artifact_retries=_int(runner_table, "artifact_retries", 1),
                max_stage_runs=_int(runner_table, "max_stage_runs", 40),
            ),
            stages=_stage_profiles(_table(payload, "stages")),
            gates=gates,
            stage_commits=_bool(runner_table, "stage_commits", True),
            ab=_ab(_table(payload, "ab")),
            repo_map=_repo_map(_table(payload, "repo_map")),
            tests=_tests(_table(payload, "tests")),
            review=_review(_table(payload, "review")),
            pr=_pr(_table(payload, "pr")),
            schema_version=version,
        )

    def to_toml(self) -> str:
        """Render the config as a commented ``flux.toml``. Used by ``flux init``."""
        blocks = [
            "# flux configuration (ADR 0006). Committed: a run is only reproducible if the",
            "# gate suite and the model routing are part of the repo, not of someone's shell.",
            "",
            f"schema_version = {self.schema_version}",
            f'target = "{self.target}"',
            "",
            "[runner]",
            f"max_review_iters = {self.runner.max_review_iters}",
            f"artifact_retries = {self.runner.artifact_retries}",
            f"max_stage_runs = {self.runner.max_stage_runs}",
            f"stage_commits = {str(self.stage_commits).lower()}",
            "",
            "# Model and effort are always explicit (ADR 0007) — never an SDK default.",
        ]
        for name in DEFAULT_STAGE_PROFILES:
            profile = self.stages.get(name)
            if profile is not None:
                blocks.extend(["", profile.to_toml(name)])
        blocks.extend(
            [
                "",
                "# Deterministic gates are the merge authority (ADR 0005). 'kind' only picks",
                "# how output is summarised; the verdict is always the command's exit status.",
            ]
        )
        for spec in self.gates:
            blocks.extend(["", spec.to_toml()])
        if not self.gates:
            blocks.extend(
                [
                    "",
                    "# No gates configured — flux cannot tell whether a change is good.",
                    "# Add at least a test gate before running a ticket, e.g.:",
                    "# [[gates]]",
                    '# name = "test"',
                    '# kind = "pytest"',
                    '# command = "pytest -q"',
                ]
            )
        blocks.extend(
            [
                "",
                "# A/B baseline against vanilla Claude Code, with a standing kill-criterion",
                "# (ADR 0008). Written down so it can be enforced, not remembered.",
                "[ab]",
                f"vanilla_every = {self.ab.vanilla_every}",
                f"kill_streak = {self.ab.kill_streak}",
                f"kill_criterion = {_toml_string(self.ab.kill_criterion)}",
                "",
                "# The baseline arm has no [stages.vanilla] entry on purpose: it mirrors",
                "# [stages.implement] so the comparison isolates the harness, not the model.",
                "# Add one only to break that mirror deliberately.",
                "",
                "# Repo map: bought, not built (ADR 0009). `flux index` runs this command and",
                "# caches the ranked file list; stages fold a slice into their context pack.",
                "[repo_map]",
                f"command = {list(self.repo_map.command)!r}".replace("'", '"'),
                f"top = {self.repo_map.top}",
                f"pack_entries = {self.repo_map.pack_entries}",
                "",
                "# The tests stage writes here and nowhere else; the implement stage may",
                "# not write here at all (ADR 0005). An empty 'command' means 'whatever the",
                "# test gate runs', so the red step and the gate cannot measure differently.",
                self.tests.to_toml(),
                "",
                "# The reviewer is advisory and runs on a different model (ADR 0005).",
                "# 'fix_severities' is the only part of its verdict the machine acts on:",
                "# those findings turn the review-fix loop and, unresolved, park the ticket.",
                self.review.to_toml(),
                "",
                "# Where a finished ticket lands. flux never pushes to a protected branch",
                "# and never force-pushes: the push is the one thing a git reset cannot",
                "# undo, so it is the one place the defaults are about restraint.",
                self.pr.to_toml(),
            ]
        )
        return "\n".join(blocks).rstrip() + "\n"


def config_path(root: Path) -> Path:
    return root / FLUX_DIRNAME / CONFIG_FILENAME


def detect_target(root: Path) -> str:
    """Guess the repo's language from its manifests. Only ever a default."""
    if (root / "pyproject.toml").exists() or (root / "setup.py").exists():
        return "python"
    if (root / "package.json").exists():
        return "typescript"
    return "generic"


def default_gates(root: Path) -> tuple[GateSpec, ...]:
    """The starter gate suite for the repo's detected target.

    Commands are prefixed with the repo's own runner (``uv run``, ``pnpm``) when its
    lockfile says so: a gate that works when flux runs it but not when the developer
    does is a gate nobody trusts.
    """
    target = detect_target(root)
    if target == "python":
        prefix = ("uv", "run") if (root / "uv.lock").exists() else ()
        return (
            GateSpec(name="lint", kind="ruff", command=(*prefix, "ruff", "check", ".")),
            GateSpec(name="typecheck", kind="pyright", command=(*prefix, "pyright")),
            GateSpec(name="test", kind="pytest", command=(*prefix, "pytest", "-q", "-rf")),
        )
    if target == "typescript":
        runner = _node_runner(root)
        exec_prefix = ("pnpm", "exec") if runner == "pnpm" else ("npx",)
        return (
            GateSpec(name="lint", command=(runner, "run", "lint")),
            GateSpec(name="typecheck", command=(*exec_prefix, "tsc", "--noEmit")),
            GateSpec(name="test", command=(runner, "test")),
        )
    return ()


def _node_runner(root: Path) -> str:
    for lockfile, runner in (
        ("pnpm-lock.yaml", "pnpm"),
        ("yarn.lock", "yarn"),
        ("bun.lockb", "bun"),
    ):
        if (root / lockfile).exists():
            return runner
    return "npm"


def _stage_profiles(table: JsonMapping) -> Mapping[str, StageProfile]:
    profiles = dict(DEFAULT_STAGE_PROFILES)
    for name, raw in table.items():
        entry = as_json_mapping(raw)
        if entry is None:
            raise ConfigError(f"[stages.{name}] must be a table")
        base = profiles.get(name)
        model = _str(entry, "model", base.model if base else "")
        effort = _str(entry, "effort", base.effort if base else "")
        if not model or not effort:
            # A stage flux does not ship a default for must state both itself.
            raise ConfigError(f"[stages.{name}] needs both 'model' and 'effort'")
        mode = _str(entry, "permission_mode", base.permission_mode if base else "acceptEdits")
        profiles[name] = StageProfile(
            model=model,
            effort=_effort(name, effort),
            permission_mode=_permission(name, mode),
            max_turns=_int(entry, "max_turns", base.max_turns if base else 40),
            max_tokens=_int(entry, "max_tokens", base.max_tokens if base else 200_000),
        )
    return MappingProxyType(profiles)


def _argv_option(table: JsonMapping, key: str, label: str) -> tuple[str, ...]:
    """A command spelled either as a shell-quoted string or an argv list. Never shelled out."""
    raw = table.get(key)
    if raw is None:
        return ()
    if isinstance(raw, str):
        return tuple(shlex.split(raw))
    items = as_json_list(raw)
    if items is None:
        raise ConfigError(f"{label} must be a string or a list of strings")
    return tuple(str(part) for part in items)


def _repo_map(table: JsonMapping) -> RepoMapConfig:
    default = RepoMapConfig()
    command = _argv_option(table, "command", "[repo_map] command") or default.command
    return RepoMapConfig(
        command=command,
        top=_int(table, "top", default.top),
        pack_entries=_int(table, "pack_entries", default.pack_entries),
        timeout_s=_int(table, "timeout_s", default.timeout_s),
    )


def _tests(table: JsonMapping) -> TestsConfig:
    default = TestsConfig()
    return TestsConfig(
        dir=_str(table, "dir", default.dir),
        command=_argv_option(table, "command", "[tests] command"),
        gate=_str(table, "gate", default.gate),
        held_out_dir=_str(table, "held_out_dir", default.held_out_dir),
        timeout_s=_int(table, "timeout_s", default.timeout_s),
    )


def _review(table: JsonMapping) -> ReviewConfig:
    default = ReviewConfig()
    raw = table.get("fix_severities")
    if raw is None:
        severities = default.fix_severities
    else:
        items = as_json_list(raw)
        if items is None:
            raise ConfigError("[review] fix_severities must be a list of severity names")
        severities = tuple(str(item) for item in items)
    return ReviewConfig(
        fix_severities=severities,
        max_diff_chars=_int(table, "max_diff_chars", default.max_diff_chars),
        max_hunks=_int(table, "max_hunks", default.max_hunks),
    )


def _pr(table: JsonMapping) -> PrConfig:
    default = PrConfig()
    raw = table.get("protected_branches")
    if raw is None:
        protected = default.protected_branches
    else:
        items = as_json_list(raw)
        if items is None:
            raise ConfigError("[pr] protected_branches must be a list of branch names")
        protected = tuple(str(item) for item in items)
    return PrConfig(
        push=_bool(table, "push", default.push),
        remote=_str(table, "remote", default.remote),
        base=_str(table, "base", default.base),
        branch_prefix=_str(table, "branch_prefix", default.branch_prefix),
        protected_branches=protected,
        create=_str(table, "create", default.create),
        draft=_bool(table, "draft", default.draft),
    )


def _ab(table: JsonMapping) -> AbConfig:
    default = AbConfig()
    return AbConfig(
        vanilla_every=_int(table, "vanilla_every", default.vanilla_every),
        kill_streak=_int(table, "kill_streak", default.kill_streak),
        kill_criterion=_str(table, "kill_criterion", default.kill_criterion),
    )


def _table(payload: JsonMapping, key: str) -> JsonMapping:
    raw = payload.get(key)
    if raw is None:
        return {}
    table = as_json_mapping(raw)
    if table is None:
        raise ConfigError(f"[{key}] must be a table")
    return table


def _tables(payload: JsonMapping, key: str) -> Iterable[JsonMapping]:
    raw = payload.get(key)
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ConfigError(f"[[{key}]] must be an array of tables")
    entries: list[JsonMapping] = []
    for item in cast(list[object], raw):
        table = as_json_mapping(item)
        if table is None:
            raise ConfigError(f"every [[{key}]] entry must be a table")
        entries.append(table)
    return entries


def _str(payload: JsonMapping, key: str, default: str) -> str:
    value = payload.get(key, default)
    if not isinstance(value, str):
        raise ConfigError(f"flux.toml: {key!r} must be a string, got {type(value).__name__}")
    return value


def _int(payload: JsonMapping, key: str, default: int) -> int:
    value = payload.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"flux.toml: {key!r} must be an integer, got {type(value).__name__}")
    return value


def _bool(payload: JsonMapping, key: str, default: bool) -> bool:
    value = payload.get(key, default)
    if not isinstance(value, bool):
        raise ConfigError(f"flux.toml: {key!r} must be a boolean, got {type(value).__name__}")
    return value


def _effort(stage: str, value: str) -> EffortLevel:
    if value not in EFFORT_LEVELS:
        raise ConfigError(f"[stages.{stage}] effort {value!r} not one of {sorted(EFFORT_LEVELS)}")
    return value  # pyright: ignore[reportReturnType]


def _permission(stage: str, value: str) -> PermissionMode:
    if value not in PERMISSION_MODES:
        raise ConfigError(
            f"[stages.{stage}] permission_mode {value!r} not one of {sorted(PERMISSION_MODES)}"
        )
    return value  # pyright: ignore[reportReturnType]


def _toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
