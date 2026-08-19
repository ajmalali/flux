"""The two ``PreToolUse`` guards the pipeline runs on (ADR 0005, design.md I/O table).

Both exist because of the same failure: pre-written tests plus "make them pass" is the
canonical reward-hacking target, and the cheapest way to pass a test is to change it.
So the stage that writes the tests may write nothing else, and the stages that write
the code may not reach the tests at all. Neither is a request in a prompt — a prompt is
a behavioural control and ADR 0005 is explicit that the hardening is structural.

The guards are built here rather than inside a stage so the implement and fix stages
(and anything later that edits code) are provably guarded by the *same* policy object.
"""

from __future__ import annotations

from pathlib import Path

from flux.config import FluxConfig
from flux.executor.guard import EDIT_TOOLS, READ_TOOLS, PathGuard, guarded_dirs
from flux.runner.context import TicketContext

TEST_NAME_GLOBS: tuple[str, ...] = (
    "test_*.py",
    "*_test.py",
    "*.test.*",
    "*.spec.*",
    "conftest.py",
)
"""Test files by name, wherever they sit. A repo that keeps tests beside the code it
tests is a normal repo; a guard that only knew about ``tests/`` would protect nothing
there. ``conftest.py`` is included because a fixture can make a test pass just as
effectively as the assertion can."""


def tests_dir(ticket: TicketContext, settings: FluxConfig) -> Path:
    """Where this ticket's new tests go. Inside the worktree — they are the deliverable."""
    return ticket.worktree / settings.tests.dir


def held_out_dir(ticket: TicketContext, settings: FluxConfig) -> Path:
    """This ticket's held-out tests. Under the *root*, so ``--worktree`` puts them out
    of the session's filesystem reach entirely rather than merely out of policy."""
    return ticket.root / settings.tests.held_out_dir / ticket.ticket_id


def tests_stage_guard(ticket: TicketContext, settings: FluxConfig) -> PathGuard:
    """Allow-only: the tests stage writes tests, and nothing else.

    Reading source is untouched — a test written without reading the code it exercises
    is a worse test. It is *writing* that is confined, because a tests stage that can
    also edit the implementation can satisfy its own red step.
    """
    return PathGuard(
        name="tests-only",
        tools=EDIT_TOOLS,
        root=ticket.worktree,
        only_dirs=guarded_dirs(tests_dir(ticket, settings), ticket.context_dir),
        reason=(
            f"the tests stage may only write test files under {settings.tests.dir}/ and its "
            "handoff artifact. Do not change the implementation — the tests you write must "
            "fail against the code as it stands, and the implement stage makes them pass."
        ),
    )


def source_stage_guard(ticket: TicketContext, settings: FluxConfig) -> PathGuard:
    """Deny: the stages that write code may neither read nor edit the tests.

    Reading is blocked as well as writing, and that is the less obvious half. A session
    that can read the assertion can write the narrowest code that satisfies *that
    assertion* rather than the requirement behind it, which is the failure the opaque
    test runner exists to prevent — leaving the test readable would hand back through
    the Read tool exactly what the gate withholds.
    """
    return PathGuard(
        name="no-test-edits",
        tools=(*EDIT_TOOLS, *READ_TOOLS),
        root=ticket.worktree,
        deny_dirs=guarded_dirs(tests_dir(ticket, settings), held_out_dir(ticket, settings)),
        deny_globs=TEST_NAME_GLOBS,
        reason=(
            "the tests are the specification for this ticket and this stage may not read or "
            "change them. Work from the test paths and the failure output in your context, "
            "and change the implementation until the gate goes green."
        ),
    )


def review_stage_guard(ticket: TicketContext) -> PathGuard:
    """Allow-only: the reviewer writes its findings file and touches nothing else.

    This is what makes the reviewer read-only, in place of the SDK's ``plan`` mode.
    Plan mode is documented as "no execution of tools", which would also stop the
    reviewer writing ``review.json`` — the one artifact the stage is judged on — so a
    plan-mode reviewer parks every time. Confining writes to the context directory
    forbids strictly more of the *repo* than plan mode does, and unlike a permission
    mode it is flux's own data, so what the reviewer may write is a pytest assertion
    rather than a property of the CLI.
    """
    return PathGuard(
        name="review-read-only",
        tools=EDIT_TOOLS,
        root=ticket.worktree,
        only_dirs=guarded_dirs(ticket.context_dir),
        reason=(
            "the review stage may not change the code it is reviewing. Write your "
            "findings to the handoff artifact; the fix stage makes the changes."
        ),
    )


def diff_exclusions(ticket: TicketContext, settings: FluxConfig) -> tuple[str, ...]:
    """Git pathspecs for what the review diff must not contain.

    Two kinds of thing, for two different reasons.

    The **tests** are excluded because :func:`source_stage_guard` excludes them: a guard
    stops a session reaching for a test file, and this stops one arriving unasked inside
    a diff — the tests stage commits its work, so a ticket's diff contains the test
    source unless it is taken out here. Both are derived from the same two facts (the
    tests directory and the test-name globs), so widening one widens the other.

    The **ticket's own context directory** is excluded because it is flux's plumbing,
    not the change: ``tests.json`` and ``impl-notes.md`` are committed alongside the
    code, and without this the reviewer would be shown its own inputs as if they were
    work under review — including the handoff artifacts the stage I/O table deliberately
    does not give it. Found by a review pack that quoted the very notes it was not
    supposed to receive.
    """
    specs = [
        f":(exclude,glob){settings.tests.dir}/**",
        *(f":(exclude,glob)**/{pattern}" for pattern in TEST_NAME_GLOBS),
    ]
    try:
        relative = ticket.context_dir.relative_to(ticket.worktree)
    except ValueError:
        return tuple(specs)  # a worktree elsewhere never contains the context dir
    return (*specs, f":(exclude,glob){relative.as_posix()}/**")


def has_held_out(ticket: TicketContext, settings: FluxConfig) -> bool:
    """Does this ticket have held-out tests? Most tickets do not."""
    directory = held_out_dir(ticket, settings)
    return directory.is_dir() and any(path.is_file() for path in directory.rglob("*"))
