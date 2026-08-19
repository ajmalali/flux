"""The review↔fix loop, driven by the real stages in a real repository.

T3 proved the transition function turns this loop and parks it; that proof used fake
stages. This is the first time real ones drive it: a reviewer that raises a blocker, a
fix stage that resolves it, a reviewer that then re-reads the *code* rather than the
resolution, and a bound that parks the ticket when the two never agree. The executor is
scripted throughout — the sessions are played, the runner is not.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from flux.config import CONFIG_FILENAME, FluxConfig
from flux.executor.types import ExecConfig, ExecResult, PromptPack, Usage
from flux.proc import run_command
from flux.runner.checkpoint import CheckpointStore
from flux.runner.context import TicketContext
from flux.runner.loop import RunResult, run_ticket
from flux.scaffold import init_repo
from flux.stages import build_pipeline
from flux.tickets import load_ticket, ticket_path

PY = sys.executable

BRIEF = "Add greet(name) to greet.py returning 'hello, <name>'."

RED_TEST = """\
def test_greets_by_name():
    import greet

    assert greet.greet("ada") == "hello, ada"
"""

IMPLEMENTATION = "def greet(name):\n    return f'hello, {name}'\n"
FIXED = (
    "def greet(name):\n"
    "    if not name:\n"
    "        raise ValueError(name)\n"
    "    return f'hello, {name}'\n"
)

NOTES = "## Changed\n\ngreet.py\n\n## Deviations\n\nNone.\n\n## Discovered work\n\nNone.\n"

PR_BODY = (
    "## Title\n\nAdd greet(name)\n\n"
    "## Summary\n\nAdds a greeting helper and rejects an empty name.\n\n"
    "## Changes\n\n- greet.py: new greet(name)\n\n"
    "## Review\n\nOne blocker about the empty name, resolved.\n\n"
    "## Risk\n\nNone worth naming.\n"
)

TESTS_ARTIFACT = json.dumps(
    {
        "test_files": ["tests/test_greet.py"],
        "cases": [
            {
                "test": "tests/test_greet.py::test_greets_by_name",
                "criterion": "greet returns a greeting",
            }
        ],
    }
)

BLOCKER = {
    "severity": "blocker",
    "axis": "correctness",
    "file": "greet.py",
    "line": 2,
    "finding": "greet('') returns 'hello, ', which is not a greeting",
    "suggestion": "reject an empty name",
}


@dataclass
class ScriptedExecutor:
    """Plays all four stages. ``blockers_per_review`` scripts the reviewer's verdicts."""

    ticket: TicketContext
    blockers_per_review: tuple[bool, ...] = (True, False)
    """One entry per review pass; the last repeats. ``True`` raises a blocker."""

    reviews: int = 0
    fixes: int = 0
    calls: list[tuple[str, PromptPack]] = field(default_factory=list[tuple[str, PromptPack]])

    def run(self, pack: PromptPack, cfg: ExecConfig) -> ExecResult:
        stage = self._stage_of(pack)
        self.calls.append((stage, pack))
        getattr(self, f"_{stage}")()
        return ExecResult(
            ok=True,
            text="done",
            session_id=f"session-{len(self.calls)}",
            model=cfg.model,
            effort=cfg.effort,
            billing_mode=cfg.billing_mode,
            usage=Usage(input_tokens=100, output_tokens=20),
            num_turns=3,
            pack_chars=pack.size_chars,
        )

    @staticmethod
    def _stage_of(pack: PromptPack) -> str:
        for stage in ("tests", "implement", "review", "fix", "pr"):
            if f"{stage} stage" in pack.system_prompt:
                return stage
        raise AssertionError(f"unrecognised system prompt: {pack.system_prompt[:80]}")

    def _tests(self) -> None:
        (self.ticket.worktree / "tests" / "test_greet.py").write_text(RED_TEST, encoding="utf-8")
        (self.ticket.context_dir / "tests.json").write_text(TESTS_ARTIFACT, encoding="utf-8")

    def _implement(self) -> None:
        (self.ticket.worktree / "greet.py").write_text(IMPLEMENTATION, encoding="utf-8")
        (self.ticket.context_dir / "impl-notes.md").write_text(NOTES, encoding="utf-8")

    def _review(self) -> None:
        index = min(self.reviews, len(self.blockers_per_review) - 1)
        findings = [dict(BLOCKER)] if self.blockers_per_review[index] else []
        self.reviews += 1
        (self.ticket.context_dir / "review.json").write_text(
            json.dumps({"summary": "a verdict", "findings": findings}), encoding="utf-8"
        )

    def _fix(self) -> None:
        self.fixes += 1
        (self.ticket.worktree / "greet.py").write_text(FIXED, encoding="utf-8")
        path = self.ticket.context_dir / "review.json"
        payload = json.loads(path.read_text())
        for entry in payload["findings"]:
            entry["resolved"] = True
            entry["resolution"] = "raised ValueError on an empty name"
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _pr(self) -> None:
        (self.ticket.context_dir / "pr.md").write_text(PR_BODY, encoding="utf-8")

    def packs_for(self, stage: str) -> list[PromptPack]:
        return [pack for name, pack in self.calls if name == stage]


def scratch_repo(tmp_path: Path, *, max_review_iters: int = 3) -> Path:
    root = tmp_path / "target"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='target'\n", encoding="utf-8")
    (root / "tests").mkdir()
    run_command(["git", "init", "-q", "-b", "main"], cwd=root)
    run_command(["git", "config", "user.email", "dev@example.com"], cwd=root)
    run_command(["git", "config", "user.name", "Dev"], cwd=root)
    init_repo(root)
    (root / ".flux" / CONFIG_FILENAME).write_text(
        "\n".join(
            [
                "schema_version = 1",
                'target = "python"',
                "[runner]",
                f"max_review_iters = {max_review_iters}",
                "[pr]",
                # This scratch repo has no remote; the loop is what is under test here,
                # and `tests/test_pr_stage.py` is where a push is actually made.
                "push = false",
                "[[gates]]",
                'name = "test"',
                'kind = "pytest"',
                f'command = ["{PY}", "-m", "pytest", "-q", "-rf"]',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    path = ticket_path(root, "flux-1")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(BRIEF, encoding="utf-8")
    return root


def drive(root: Path, **kwargs: object) -> tuple[RunResult, TicketContext, ScriptedExecutor]:
    settings = FluxConfig.load(root)
    ticket = load_ticket("flux-1", root=root, config=settings)
    executor = ScriptedExecutor(ticket=ticket, **kwargs)  # pyright: ignore[reportArgumentType]
    return run_ticket(ticket, build_pipeline(settings), executor), ticket, executor


# -- the loop turns --------------------------------------------------------------


def test_a_blocker_routes_to_the_fix_stage_and_back_to_the_reviewer(tmp_path: Path) -> None:
    root = scratch_repo(tmp_path)

    result, ticket, executor = drive(root)

    assert result.completed
    assert result.stages_run == ("tests", "implement", "review", "fix", "review", "pr")
    assert (executor.reviews, executor.fixes) == (2, 1)
    assert "raise ValueError" in (root / "greet.py").read_text()
    assert CheckpointStore(ticket.state_dir).load_state().open_findings is False


def test_a_clean_review_ends_the_ticket_without_a_fix_stage(tmp_path: Path) -> None:
    root = scratch_repo(tmp_path)

    result, _, executor = drive(root, blockers_per_review=(False,))

    assert result.completed
    assert result.stages_run == ("tests", "implement", "review", "pr")
    assert executor.fixes == 0


def test_a_reviewer_that_never_agrees_parks_the_ticket(tmp_path: Path) -> None:
    """The bound is the point: a loop nobody stops is a loop that spends until it is noticed."""
    root = scratch_repo(tmp_path, max_review_iters=2)

    result, ticket, executor = drive(root, blockers_per_review=(True,))

    assert result.park is not None
    assert result.park.reason == "review-loop-exhausted"
    assert executor.reviews == 2, "the bound counts review passes, not fix attempts"
    assert CheckpointStore(ticket.state_dir).load_state().review_iterations == 2


def test_the_second_review_pass_re_reads_the_code_not_the_resolutions(tmp_path: Path) -> None:
    """A fixer that marks a finding resolved without changing anything gains nothing."""
    root = scratch_repo(tmp_path)

    _, _, executor = drive(root)
    second = executor.packs_for("review")[1].prompt

    assert "raised ValueError on an empty name" not in second, "the resolution is not hydrated"
    assert "raise ValueError(name)" in second, "the fixed code is"


def test_the_fix_session_is_handed_the_finding_and_its_hunk(tmp_path: Path) -> None:
    root = scratch_repo(tmp_path)

    _, _, executor = drive(root)
    fix_prompt = executor.packs_for("fix")[0].prompt

    assert "is not a greeting" in fix_prompt
    assert "hello, {name}" in fix_prompt, "the hunk the finding points at"
    assert 'greet.greet("ada")' not in fix_prompt, "never the test source"


# -- the invariant ---------------------------------------------------------------


def test_pack_size_does_not_grow_monotonically_across_the_pipeline(tmp_path: Path) -> None:
    """design.md §2: artifacts are referenced, not pasted. The proof is the measurement."""
    root = scratch_repo(tmp_path)

    _, _, executor = drive(root)
    sizes = [(stage, pack.size_chars) for stage, pack in executor.calls]
    values = [size for _, size in sizes]

    assert values != sorted(values), f"packs grew at every stage: {sizes}"
    fix_size = executor.packs_for("fix")[0].size_chars
    review_size = executor.packs_for("review")[0].size_chars
    assert fix_size < review_size, f"the fix pack ({fix_size}) is not a slice ({review_size})"


def test_every_stage_leaves_a_checkpoint_that_survives_a_restart(tmp_path: Path) -> None:
    root = scratch_repo(tmp_path)
    result, _, _ = drive(root)
    assert result.completed

    again, _, second = drive(root)

    assert again.completed
    assert again.stages_run == (), "a finished ticket re-runs nothing"
    assert second.calls == []
