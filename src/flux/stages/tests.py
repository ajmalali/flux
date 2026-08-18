"""The tests stage: write the failing tests, and prove to the runner that they fail.

This is the first stage where the runner does not merely *check* a claim but *makes*
the one that matters. A session that says "I wrote three failing tests" has said
nothing; ``commit()`` runs those three tests itself and requires them to come back red
for a reason it recognises (design.md §2, Rule 2). That is the whole point of putting
the tests before the implementation: the red step is the only evidence that the tests
test anything at all, and it is evidence only if flux gathers it.

"Red for the right reason" is deliberately narrow:

* **no collection errors** — a test that cannot be imported fails for a reason the
  implementation cannot fix, and goes green the moment the file merely imports;
* **nothing passing** — a test that was already satisfied before any work started is
  not a specification of the change, it is a description of the status quo;
* **at least one failure** — an empty suite is not red, it is absent.

The session is told this in the prompt, including the one technique that makes it
achievable (import the module under test *inside* the test, not at module scope), so
the rule is one it can actually satisfy rather than a trap it discovers by parking.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from flux.config import FluxConfig
from flux.executor.types import ExecConfig, ExecResult, PromptPack
from flux.fsio import read_json_mapping, write_json_atomic
from flux.gates.spec import bash_permission
from flux.git import stage_commit
from flux.jsonio import JsonMapping, as_json_list, as_json_mapping
from flux.metrics.record import GateOutcome
from flux.runner.artifact import ArtifactSpec, digest_of
from flux.runner.context import TicketContext
from flux.runner.stage import Gate, Outcome
from flux.stages.guards import has_held_out, tests_dir, tests_stage_guard
from flux.stages.hydration import bullets, join, read_text, section
from flux.testrun import TestReport, run_tests

STAGE_NAME = "tests"

ARTIFACT_FILENAME = "tests.json"
CONTEXT_PACK_FILENAME = "context-pack.md"
PLAN_SUMMARY_FILENAME = "plan-summary.md"

TEST_FILES_KEY = "test_files"
CASES_KEY = "cases"
RED_KEY = "red"
RED_OUTPUT_KEY = "red_output"
DIGESTS_KEY = "test_digests"

NON_RED_KINDS: frozenset[str] = frozenset({"pytest", "coverage"})
"""Gate kinds the tests stage does not run. The suite is red by construction here, so
running it as a gate would fail the stage for doing its job."""


def artifact_path(ticket: TicketContext) -> Path:
    return ticket.context_dir / ARTIFACT_FILENAME


def read_artifact(ticket: TicketContext) -> JsonMapping | None:
    return read_json_mapping(artifact_path(ticket))


def check_artifact(payload: JsonMapping) -> str:
    """Structural check the runner applies before the stage is allowed to commit.

    Runs at validation time rather than in ``commit()`` so that a malformed map costs
    one nudged retry instead of a park — the difference between a session that made a
    formatting mistake and a session that failed the task.
    """
    files = as_json_list(payload.get(TEST_FILES_KEY))
    if not files or any(not isinstance(item, str) or not item.strip() for item in files):
        return f"{TEST_FILES_KEY!r} must be a non-empty list of test file paths"
    cases = as_json_list(payload.get(CASES_KEY))
    if not cases:
        return f"{CASES_KEY!r} must be a non-empty list mapping tests to acceptance criteria"
    for entry in cases:
        case = as_json_mapping(entry)
        if case is None:
            return f"every {CASES_KEY!r} entry must be an object with 'test' and 'criterion'"
        missing = [key for key in ("test", "criterion") if not str(case.get(key, "")).strip()]
        if missing:
            return f"a {CASES_KEY!r} entry is missing a non-empty {' and '.join(missing)}"
    return ""


ARTIFACT_SPEC = ArtifactSpec(
    path=ARTIFACT_FILENAME,
    kind="json",
    required_keys=(TEST_FILES_KEY, CASES_KEY),
    check=check_artifact,
    description=(
        "it names the test files you wrote and maps each test to the acceptance "
        "criterion it checks, which is the only description of this ticket the "
        "implement stage receives."
    ),
)

SYSTEM_PROMPT = """\
You are the tests stage of the flux pipeline, working in a checkout of a real \
repository.

Write tests that describe the change the ticket asks for, and stop. You are not \
implementing anything, and you are not making anything pass.

Four things about this environment are enforced by the harness, not left to your \
judgement:

1. You can only write test files. Attempts to edit the implementation are blocked \
before they happen; there is no way around it, and trying is a wasted turn.
2. When your session ends, the harness runs the tests you wrote. They must ALL fail, \
and they must fail on an assertion. If any test passes, or the suite errors during \
collection, this stage fails.
3. "Fails on an assertion" is a real constraint when the code does not exist yet. \
Import the module under test INSIDE the test function, not at the top of the file, so \
a missing module is an assertion-time failure rather than a collection error. Where \
that is impossible, write the test against the seam that already exists.
4. Nothing you say in this session is carried forward. The next stage starts with an \
empty context, is given your test *paths* and the failure output but never your test \
source, and reads the handoff artifact you leave behind.

Write tests that would still fail if someone implemented the wrong thing. A test that \
asserts what the code happens to do is worse than no test, because it will be believed.\
"""


@dataclass(frozen=True, slots=True)
class TestsStage:
    """The first stage of the M1 pipeline: the specification, in executable form."""

    settings: FluxConfig
    name: str = STAGE_NAME

    # -- inputs ---------------------------------------------------------------

    def hydrate(self, ticket: TicketContext) -> PromptPack:
        """Assemble the pack from disk. Pure: same files in, same pack out."""
        context = ticket.context_dir
        return PromptPack(
            system_prompt=SYSTEM_PROMPT,
            plan_summary=read_text(context / PLAN_SUMMARY_FILENAME),
            context_pack=join(
                section("Ticket", ticket.brief),
                read_text(context / CONTEXT_PACK_FILENAME),
            ),
            stage_tail=join(
                self._where_section(ticket),
                self._red_section(),
                self._output_section(ticket),
            ),
        )

    def _where_section(self, ticket: TicketContext) -> str:
        command = self.settings.tests_command()
        lines = [f"Write your tests under `{self.settings.tests.dir}/` in {ticket.worktree}."]
        if command:
            lines.append(f"The harness will run them with `{' '.join(command)}`.")
        if has_held_out(ticket, self.settings):
            lines.append(
                "This ticket also has held-out tests you cannot see. They run against the "
                "implementation later, so write for the requirement, not for the file."
            )
        return section("Where the tests go", "\n".join(lines))

    def _red_section(self) -> str:
        return section(
            "The red step",
            "After your session ends the harness runs exactly the files you list in the "
            "handoff artifact, and this stage only stands if:\n\n"
            + bullets(
                (
                    "every one of those tests fails,",
                    "none of them passes,",
                    "and the suite collects cleanly — no import errors, no fixture errors.",
                )
            ),
        )

    def _output_section(self, ticket: TicketContext) -> str:
        path = ARTIFACT_SPEC.resolve(ticket)
        example = json.dumps(
            {
                TEST_FILES_KEY: [f"{self.settings.tests.dir}/test_example.py"],
                CASES_KEY: [
                    {
                        "test": f"{self.settings.tests.dir}/test_example.py::test_name",
                        "criterion": "the acceptance criterion from the ticket this checks",
                    }
                ],
            },
            indent=2,
        )
        return section(
            "Required output",
            f"Write `{path}` as a JSON object of exactly this shape:\n\n"
            f"```json\n{example}\n```\n\n"
            f"`{TEST_FILES_KEY}` are paths relative to the repository root. Every test you "
            f"wrote gets a `{CASES_KEY}` entry naming the acceptance criterion it checks — "
            "a test nobody can trace back to a requirement is a test nobody can delete.",
        )

    # -- policy ---------------------------------------------------------------

    def config(self, ticket: TicketContext) -> ExecConfig:
        """Model, effort and the write guard that makes this stage's verdict mean something."""
        command = self.settings.tests_command()
        return self.settings.profile(self.name).exec_config(
            cwd=ticket.worktree,
            allowed_tools=(bash_permission(command),) if command else (),
            add_dirs=(ticket.context_dir,),
            guards=(tests_stage_guard(ticket, self.settings),),
        )

    def required_artifact(self) -> ArtifactSpec | None:
        return ARTIFACT_SPEC

    def gates(self, ticket: TicketContext) -> Sequence[Gate]:
        """Everything the repo gates on except running the suite.

        Lint and typecheck still apply — a test file is code, and a test that does not
        parse is not a specification of anything. The suite itself is excluded because
        this stage is judged on the suite being *red*, and a gate that demanded green
        would fail every tests stage that worked.
        """
        return self.settings.build_gates(exclude=self._excluded_gates())

    def _excluded_gates(self) -> tuple[str, ...]:
        excluded = {spec.name for spec in self.settings.gates if spec.kind in NON_RED_KINDS}
        suite = self.settings.test_gate()
        if suite is not None:
            excluded.add(suite.name)
        return tuple(sorted(excluded))

    # -- verification ---------------------------------------------------------

    def commit(
        self,
        ticket: TicketContext,
        result: ExecResult,
        gate_results: Sequence[GateOutcome],
    ) -> Outcome:
        """Run the tests the session wrote and require them to be red for the right reason."""
        failed = [gate for gate in gate_results if not gate.passed]
        if failed:
            names = ", ".join(gate.name for gate in failed)
            return Outcome(
                ok=False,
                parked=True,
                reason="gates-failed",
                note=f"gates failed on the new tests: {names}",
                detail={"failed_gates": [gate.name for gate in failed]},
            )

        payload = read_artifact(ticket)
        if payload is None:  # unreachable: the runner validated this file moments ago
            return Outcome(
                ok=False,
                parked=True,
                reason="artifact-invalid",
                note=f"{ARTIFACT_FILENAME} is gone",
            )

        command = self.settings.tests_command()
        if not command:
            return Outcome(
                ok=False,
                parked=True,
                reason="no-test-command",
                note=(
                    "there is no way to run the tests, so the red step cannot be verified — "
                    f"set [tests] command or a test gate in {self.settings.path}. A tests "
                    "stage nobody can check is worse than no tests stage."
                ),
            )

        files = _paths(payload)
        misplaced = self._misplaced(ticket, files)
        if misplaced:
            return Outcome(
                ok=False,
                parked=True,
                reason="tests-misplaced",
                note=(
                    f"{ARTIFACT_FILENAME} names files that are missing or outside "
                    f"{self.settings.tests.dir}/: {', '.join(misplaced)}"
                ),
                detail={"misplaced": misplaced},
            )

        report = run_tests(
            command,
            cwd=ticket.worktree,
            paths=files,
            timeout_s=self.settings.tests.timeout_s,
        )
        problem = red_step_problem(report)
        self._record_red(ticket, payload, report, files)
        if problem:
            return Outcome(
                ok=False,
                parked=True,
                reason="red-step-failed",
                note=f"the new tests are not red for the right reason: {problem}",
                detail={"red": report.to_json()},
            )

        commit = self._record_commit(ticket)
        return Outcome(
            ok=True,
            note=f"{len(files)} test file(s) written and verified red ({report.summary})",
            detail={
                "test_files": files,
                "red": report.to_json(),
                "commit": commit,
                "session_id": result.session_id,
            },
        )

    def _misplaced(self, ticket: TicketContext, files: Sequence[str]) -> list[str]:
        """Listed paths that do not exist, or that sit outside the tests directory.

        The write guard already stops the session putting a test elsewhere, so this
        catches the other half: an artifact that *names* a file the session never wrote,
        which would otherwise make the red step a measurement of nothing.
        """
        allowed = tests_dir(ticket, self.settings).resolve()
        wrong: list[str] = []
        for entry in files:
            path = (ticket.worktree / entry).resolve()
            if not path.is_file() or not (path == allowed or allowed in path.parents):
                wrong.append(entry)
        return wrong

    def _record_red(
        self,
        ticket: TicketContext,
        payload: JsonMapping,
        report: TestReport,
        files: Sequence[str],
    ) -> None:
        """Store the run flux observed into the artifact, red or not.

        Written even when the step failed: the next human to look is triaging, and the
        output that explains the park is the whole of what they need.
        """
        updated = dict(payload)
        updated[RED_KEY] = report.to_json()
        updated[RED_OUTPUT_KEY] = report.detail()
        updated[DIGESTS_KEY] = digests(ticket, files)
        write_json_atomic(artifact_path(ticket), updated)

    def _record_commit(self, ticket: TicketContext) -> dict[str, object]:
        if not self.settings.stage_commits:
            return {"committed": False, "skipped": "stage_commits is off"}
        outcome = stage_commit(
            ticket.worktree,
            ticket=ticket.ticket_id,
            stage=self.name,
            message=f"flux({ticket.ticket_id}): {self.name}",
        )
        recorded: dict[str, object] = dict(outcome.to_detail())
        if not outcome.ok:
            recorded["problem"] = outcome.detail
        return recorded


def red_step_problem(report: TestReport) -> str:
    """Why this run is not a red step, or ``""`` if it is one."""
    if not report.ran:
        return report.fault or "the test command did not run"
    if report.collection_error or report.errors:
        return (
            "the suite errored instead of failing — an import or fixture error is not a "
            f"failing test ({report.summary or report.raw_tail})"
        )
    if report.passed:
        return (
            f"{report.passed} test(s) already pass, so they do not describe a change "
            f"({report.summary})"
        )
    if not report.failed:
        return f"no tests ran ({report.summary or report.raw_tail})"
    return ""


def digests(ticket: TicketContext, files: Sequence[str]) -> dict[str, str]:
    """SHA-256 per test file, so a later stage can prove they were not edited."""
    return {entry: digest_of(ticket.worktree / entry) for entry in files}


def modified_tests(ticket: TicketContext) -> tuple[str, ...]:
    """Test files whose contents no longer match what the tests stage left behind.

    The guard blocks the tool calls that would edit a test; this catches every other
    route — a shell redirect, a script, a stray formatter — because it compares bytes
    rather than predicting behaviour. Silence when there is no ``tests.json`` is
    correct: a pipeline with no tests stage has no test digests to defend.
    """
    payload = read_artifact(ticket)
    if payload is None:
        return ()
    recorded = as_json_mapping(payload.get(DIGESTS_KEY))
    if not recorded:
        return ()
    changed = [
        entry
        for entry, digest in recorded.items()
        if isinstance(digest, str) and digest_of(ticket.worktree / entry) != digest
    ]
    return tuple(sorted(changed))


def _paths(payload: Mapping[str, object]) -> list[str]:
    entries = as_json_list(payload.get(TEST_FILES_KEY)) or []
    return [item for item in entries if isinstance(item, str) and item.strip()]
