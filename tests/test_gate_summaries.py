"""What a gate keeps from its output — and, for tests, what it must not keep.

The test gate is the opaque runner in gate form (design.md §2): the implement session
may learn *which* tests failed and the first assertion, never the test source. A
summariser that pasted the failure section would hand the model the thing it is
supposed to satisfy honestly.
"""

from __future__ import annotations

from flux.gates.summaries import (
    MAX_NAMED_FAILURES,
    coverage_percent,
    pyright_summary,
    pytest_summary,
    ruff_summary,
)
from flux.proc import CommandRun

PYTEST_FAILURE = """\
=================================== FAILURES ===================================
____________________________ test_discount_applies _____________________________

    def test_discount_applies() -> None:
        cart = Cart(items=[Item(price=100)])
        SECRET_FIXTURE_BODY = "this is test source and must not be quoted back"
>       assert cart.total() == 90
E       assert 100 == 90

tests/test_cart.py:12: AssertionError
=========================== short test summary info ============================
FAILED tests/test_cart.py::test_discount_applies - assert 100 == 90
========================= 1 failed, 4 passed in 0.31s ==========================
"""


def run(output: str, returncode: int = 1) -> CommandRun:
    return CommandRun(argv=("pytest",), returncode=returncode, stdout=output)


def test_pytest_summary_reports_counts_and_failing_ids() -> None:
    summary = pytest_summary(run(PYTEST_FAILURE))
    assert "1 failed, 4 passed" in summary
    assert "tests/test_cart.py::test_discount_applies" in summary
    assert "first assertion: assert 100 == 90" in summary


def test_pytest_summary_does_not_leak_test_source() -> None:
    summary = pytest_summary(run(PYTEST_FAILURE))
    assert "SECRET_FIXTURE_BODY" not in summary
    assert "def test_discount_applies" not in summary
    assert "Cart(items=" not in summary


def test_pytest_summary_on_a_green_run_is_just_the_totals() -> None:
    green = "========================= 12 passed in 1.20s =========================="
    assert pytest_summary(run(green, returncode=0)) == "12 passed in 1.20s"


def test_pytest_summary_caps_the_list_of_named_failures() -> None:
    many = "\n".join(f"FAILED tests/test_x.py::test_{n}" for n in range(30))
    summary = pytest_summary(run(f"{many}\n=== 30 failed in 2s ==="))
    assert summary.count("tests/test_x.py::") == MAX_NAMED_FAILURES
    assert "and 20 more" in summary


def test_pytest_summary_deduplicates_names_repeated_across_sections() -> None:
    repeated = "FAILED tests/a.py::test_one\nFAILED tests/a.py::test_one\n=== 1 failed in 1s ==="
    assert pytest_summary(run(repeated)).count("tests/a.py::test_one") == 1


def test_pytest_summary_reports_collection_errors() -> None:
    text = "ERROR tests/test_broken.py\n=== 1 error in 0.10s ==="
    summary = pytest_summary(run(text, returncode=2))
    assert "tests/test_broken.py" in summary
    assert "1 error" in summary


def test_pytest_summary_falls_back_to_the_tail_when_it_recognises_nothing() -> None:
    assert "segmentation fault" in pytest_summary(run("segmentation fault"))


def test_ruff_summary_keeps_diagnostics_and_the_count() -> None:
    output = "\n".join(
        [f"src/mod{n}.py:{n}:1: F401 unused import" for n in range(8)] + ["Found 8 errors."]
    )
    summary = ruff_summary(run(output))
    assert "Found 8 errors." in summary
    assert summary.count("F401") == 5  # first five, not all eight


def test_ruff_summary_is_empty_when_ruff_is_happy() -> None:
    assert ruff_summary(run("All checks passed!", returncode=0)) == ""


def test_pyright_summary_keeps_errors_and_the_tally() -> None:
    output = (
        "/repo/src/a.py:3:5 - error: Type is unknown\n"
        "/repo/src/b.py:9:1 - error: Missing return\n"
        "2 errors, 0 warnings, 0 informations"
    )
    summary = pyright_summary(run(output))
    assert "2 errors, 0 warnings, 0 informations" in summary
    assert "Missing return" in summary


def test_pyright_summary_is_empty_when_clean() -> None:
    assert pyright_summary(run("0 errors, 0 warnings, 0 informations", returncode=0)) == ""


def test_coverage_percent_reads_the_total_row() -> None:
    table = "Name    Stmts  Miss  Cover\nsrc/a.py   10     1   90%\nTOTAL      10     1   90%"
    assert coverage_percent(run(table, returncode=0)) == 90.0


def test_coverage_percent_handles_a_fractional_total() -> None:
    assert coverage_percent(run("TOTAL   100   7   93.5%", returncode=0)) == 93.5


def test_coverage_percent_is_none_without_a_total_row() -> None:
    assert coverage_percent(run("nothing here", returncode=0)) is None
