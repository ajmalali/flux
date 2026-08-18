"""The opaque test runner: what it concludes, and what it refuses to repeat.

Opacity is the point of the module, so the fixtures deliberately contain test source
with a marker string in it — every assertion about what a report says is also an
assertion that the source did not come with it.
"""

from __future__ import annotations

import sys
from pathlib import Path

from flux.proc import CommandRun
from flux.testrun import MAX_NAMED_FAILURES, TestReport, parse, run_tests

PY = sys.executable

SECRET = "SECRET_FIXTURE_BODY_that_must_never_be_quoted_back"

FAILURE = f"""\
=================================== FAILURES ===================================
____________________________ test_discount_applies _____________________________

    def test_discount_applies() -> None:
        cart = Cart(items=[Item(price=100)])
        {SECRET} = "this is test source"
>       assert cart.total() == 90
E       assert 100 == 90

tests/test_cart.py:12: AssertionError
=========================== short test summary info ============================
FAILED tests/test_cart.py::test_discount_applies - assert 100 == 90
========================= 1 failed, 4 passed in 0.31s ==========================
"""

RED = """\
=========================== short test summary info ============================
FAILED tests/test_greet.py::test_greets_by_name - AssertionError
FAILED tests/test_greet.py::test_greets_politely - AssertionError
============================== 2 failed in 0.05s ===============================
"""

COLLECTION_ERROR = """\
==================================== ERRORS ====================================
ERROR tests/test_greet.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!!!
=============================== 1 error in 0.03s ===============================
"""


def run(output: str, returncode: int = 1) -> CommandRun:
    return CommandRun(argv=("pytest",), returncode=returncode, stdout=output)


# -- parsing ---------------------------------------------------------------------


def test_counts_come_from_pytests_own_totals_line() -> None:
    report = parse(run(FAILURE))
    assert (report.passed, report.failed, report.errors) == (4, 1, 0)
    assert report.summary == "1 failed, 4 passed in 0.31s"


def test_plural_errors_are_counted_under_one_name() -> None:
    assert parse(run("=== 2 errors in 0.1s ===", returncode=2)).errors == 2


def test_a_report_never_carries_test_source() -> None:
    report = parse(run(FAILURE))
    assert SECRET not in report.detail()
    assert SECRET not in str(report.to_json())
    assert "def test_discount_applies" not in report.detail()


def test_the_detail_names_the_failing_tests_and_the_first_assertion() -> None:
    detail = parse(run(FAILURE)).detail()
    assert "tests/test_cart.py::test_discount_applies" in detail
    assert "first assertion: assert 100 == 90" in detail


def test_named_failures_are_capped_and_the_rest_counted() -> None:
    many = "\n".join(f"FAILED tests/test_x.py::test_{n}" for n in range(30))
    detail = parse(run(f"{many}\n=== 30 failed in 2s ===")).detail()
    assert detail.count("tests/test_x.py::") == MAX_NAMED_FAILURES
    assert "and 20 more" in detail


def test_a_command_that_never_ran_reports_the_fault_not_a_verdict() -> None:
    faulted = CommandRun(argv=("pytest",), launched=False, fault="'pytest' is not on PATH")
    report = parse(faulted)
    assert not report.ran
    assert not report.all_red
    assert not report.green
    assert "not on PATH" in report.detail()


# -- the red-step verdict --------------------------------------------------------


def test_every_test_failing_is_red() -> None:
    assert parse(run(RED)).all_red


def test_a_suite_with_a_passing_test_is_not_red() -> None:
    """A test already satisfied before the work started describes the status quo."""
    assert not parse(run(FAILURE)).all_red


def test_a_collection_error_is_not_red() -> None:
    report = parse(run(COLLECTION_ERROR, returncode=2))
    assert report.collection_error
    assert not report.all_red


def test_an_empty_suite_is_not_red() -> None:
    assert not parse(run("=== no tests ran in 0.01s ===", returncode=5)).all_red


def test_green_and_red_are_not_the_same_question() -> None:
    green = parse(run("=== 12 passed in 1.2s ===", returncode=0))
    assert green.green and not green.all_red


# -- running a real suite --------------------------------------------------------


def test_run_tests_narrows_to_the_paths_it_is_given(tmp_path: Path) -> None:
    (tmp_path / "test_red.py").write_text("def test_x():\n    assert False\n", encoding="utf-8")
    (tmp_path / "test_green.py").write_text("def test_y():\n    assert True\n", encoding="utf-8")

    report = run_tests([PY, "-m", "pytest", "-q", "-rf"], cwd=tmp_path, paths=["test_red.py"])

    assert report.all_red
    assert report.failed == 1 and report.passed == 0


def test_run_tests_without_a_command_says_so_rather_than_passing() -> None:
    report = run_tests([], cwd=Path.cwd())
    assert not report.ran and not report.green
    assert "no test command" in report.fault


def test_a_missing_runner_is_a_fault_not_a_pass(tmp_path: Path) -> None:
    report = run_tests(["definitely-not-a-real-runner"], cwd=tmp_path)
    assert not report.ran and not report.all_red


def test_to_json_is_a_verdict_not_a_transcript() -> None:
    payload = TestReport(ran=True, returncode=1, failing=("a::b",), summary="1 failed").to_json()
    assert payload["failed"] == 0  # counts come from the summary line, not from guesswork
    assert payload["failing"] == ["a::b"]
    assert set(payload) >= {"ran", "returncode", "summary", "passed", "failed", "errors"}
