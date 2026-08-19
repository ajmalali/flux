"""Reading the A/B store: who won a ticket, when a sample is owed, when to stop.

The kill-criterion is the one rule in the plan that can tell flux to stop building
itself, so its arithmetic is specified here rather than left to whoever reads the
table (ADR 0008).
"""

from __future__ import annotations

from flux.config import AbConfig
from flux.metrics.ab import (
    ACCEPTANCE_GATE,
    QUALITY_ACCEPTED,
    QUALITY_FAILED,
    QUALITY_GREEN,
    QUALITY_UNVERIFIED,
    build_verdict,
    tickets_since_baseline,
)
from flux.metrics.record import GateOutcome, MetricRecord


def line(
    ticket: str,
    variant: str,
    *,
    stage: str = "implement",
    tokens: int = 100,
    cache_read: int = 0,
    ok: bool = True,
    gates: tuple[GateOutcome, ...] = (),
    ts: str = "2026-08-18T00:00:00Z",
) -> MetricRecord:
    return MetricRecord(
        ticket=ticket,
        stage=stage,
        model="claude-sonnet-5",
        effort="high",
        billing_mode="subscription",
        variant=variant,
        ok=ok,
        ts=ts,
        input_tokens=tokens,
        output_tokens=0,
        cache_read_tokens=cache_read,
        gates=gates,
    )


GREEN = (GateOutcome(name="test", passed=True),)
RED = (GateOutcome(name="test", passed=False),)
ACCEPTED = (*GREEN, GateOutcome(name=ACCEPTANCE_GATE, passed=True))
REJECTED = (*GREEN, GateOutcome(name=ACCEPTANCE_GATE, passed=False))
AB = AbConfig(vanilla_every=10, kill_streak=3)


def test_only_tickets_that_ran_both_ways_are_compared() -> None:
    """An unpaired ticket is not evidence; it is a reminder to run the other arm."""
    verdict = build_verdict(
        [
            line("t-1", "harness", gates=GREEN),
            line("t-1", "vanilla", gates=GREEN),
            line("t-2", "harness", gates=GREEN),
        ],
        ab=AB,
    )
    assert [p.ticket for p in verdict.pairings] == ["t-1"]
    assert verdict.unpaired_harness == ("t-2",)


def test_cost_is_uncached_tokens_summed_over_every_attempt() -> None:
    """Retries are part of what a ticket cost, and cache reads are not.

    A cached prefix is re-read every turn (T4's 893k-token park), so counting it would
    make the arm with the better prompt cache look like the expensive one.
    """
    verdict = build_verdict(
        [
            line("t-1", "harness", tokens=100, cache_read=50_000),
            line("t-1", "harness", tokens=60, cache_read=50_000),
            line("t-1", "vanilla", tokens=200, cache_read=0),
        ],
        ab=AB,
    )
    (pairing,) = verdict.pairings
    assert pairing.harness.billable_tokens == 160
    assert pairing.vanilla.billable_tokens == 200
    assert not pairing.vanilla_wins


def test_cheaper_and_equally_good_is_a_win_for_vanilla() -> None:
    """The harness is what is on trial: a tie on quality at a lower price is a loss."""
    verdict = build_verdict(
        [
            line("t-1", "harness", tokens=500, gates=GREEN),
            line("t-1", "vanilla", tokens=200, gates=GREEN),
        ],
        ab=AB,
    )
    assert verdict.pairings[0].vanilla_wins


def test_cheaper_but_worse_is_not_a_win() -> None:
    verdict = build_verdict(
        [
            line("t-1", "harness", tokens=500, gates=GREEN),
            line("t-1", "vanilla", tokens=200, gates=RED),
        ],
        ab=AB,
    )
    assert not verdict.pairings[0].vanilla_wins


def test_ungated_beats_nothing_and_loses_to_green() -> None:
    """"Nothing verified it" is not a pass, and it is not a failure either."""
    verdict = build_verdict(
        [
            line("t-1", "harness", tokens=500, gates=GREEN),
            line("t-1", "vanilla", tokens=200),
            line("t-2", "harness", tokens=500, gates=RED),
            line("t-2", "vanilla", tokens=200),
        ],
        ab=AB,
    )
    by_ticket = {p.ticket: p for p in verdict.pairings}
    assert by_ticket["t-1"].vanilla.quality == QUALITY_UNVERIFIED
    assert not by_ticket["t-1"].vanilla_wins  # green outranks unverified
    assert by_ticket["t-2"].harness.quality == QUALITY_FAILED
    assert by_ticket["t-2"].vanilla_wins  # unverified outranks a red gate


def test_a_do_nothing_vanilla_run_loses_its_pairing() -> None:
    """The T5.5a criterion (ADR 0011): the repo's own suite stays green under a session
    that changes nothing, so a do-nothing vanilla arm used to win at near-zero cost.
    With both arms judged by the same held-out acceptance tests, it fails them instead.
    """
    verdict = build_verdict(
        [
            line("t-1", "harness", tokens=10_000, gates=ACCEPTED),
            line("t-1", "vanilla", tokens=50, gates=REJECTED),
        ],
        ab=AB,
    )
    (pairing,) = verdict.pairings
    assert pairing.vanilla.quality == QUALITY_FAILED
    assert pairing.harness.quality == QUALITY_ACCEPTED
    assert not pairing.vanilla_wins
    assert verdict.streak == 0


def test_acceptance_green_outranks_gates_green() -> None:
    """"Every gate green" without an acceptance verdict is only "nothing broke" — an
    arm the acceptance tests passed is better evidence, whatever it cost."""
    verdict = build_verdict(
        [
            line("t-1", "harness", tokens=10_000, gates=ACCEPTED),
            line("t-1", "vanilla", tokens=50, gates=GREEN),
        ],
        ab=AB,
    )
    (pairing,) = verdict.pairings
    assert pairing.harness.quality == QUALITY_ACCEPTED
    assert pairing.harness.quality_label == "acceptance green"
    assert pairing.vanilla.quality == QUALITY_GREEN
    assert not pairing.vanilla_wins


def test_acceptance_follows_last_wins_like_any_gate() -> None:
    """Held-out red at implement and green after the fix is the loop doing its job."""
    verdict = build_verdict(
        [
            line("t-1", "harness", stage="implement", gates=REJECTED, ts="2026-08-18T00:00:01Z"),
            line("t-1", "harness", stage="fix", gates=ACCEPTED, ts="2026-08-18T00:00:02Z"),
            line("t-1", "vanilla", gates=GREEN, ts="2026-08-18T00:00:03Z"),
        ],
        ab=AB,
    )
    assert verdict.pairings[0].harness.quality == QUALITY_ACCEPTED


def test_a_gate_that_went_red_then_green_ends_green() -> None:
    """The review↔fix loop re-runs the suite; the last verdict is the verdict.

    Otherwise every ticket that needed a fix would be scored as a defect, and the loop
    that exists to catch defects would count against the harness that runs it.
    """
    verdict = build_verdict(
        [
            line("t-1", "harness", stage="implement", gates=RED, ts="2026-08-18T00:00:01Z"),
            line("t-1", "harness", stage="fix", gates=GREEN, ts="2026-08-18T00:00:02Z"),
            line("t-1", "harness", stage="pr", ts="2026-08-18T00:00:03Z"),
            line("t-1", "vanilla", gates=GREEN, ts="2026-08-18T00:00:04Z"),
        ],
        ab=AB,
    )
    assert verdict.pairings[0].harness.quality == QUALITY_GREEN


def test_a_parked_ticket_is_a_quality_failure() -> None:
    """The last attempt not completing is the park, and a park is not a pass."""
    verdict = build_verdict(
        [
            line("t-1", "harness", ok=False, ts="2026-08-18T00:00:01Z"),
            line("t-1", "vanilla", gates=GREEN, ts="2026-08-18T00:00:02Z"),
        ],
        ab=AB,
    )
    assert verdict.pairings[0].harness.quality == QUALITY_FAILED


def test_a_retry_that_then_succeeded_is_cost_not_a_defect() -> None:
    verdict = build_verdict(
        [
            line("t-1", "harness", ok=False, ts="2026-08-18T00:00:01Z"),
            line("t-1", "harness", gates=GREEN, ts="2026-08-18T00:00:02Z"),
            line("t-1", "vanilla", gates=GREEN, ts="2026-08-18T00:00:03Z"),
        ],
        ab=AB,
    )
    (pairing,) = verdict.pairings
    assert pairing.harness.quality == QUALITY_GREEN
    assert pairing.harness.failed_sessions == 1


def test_the_criterion_fires_on_three_consecutive_vanilla_wins() -> None:
    records: list[MetricRecord] = []
    for n in range(3):
        stamp = f"2026-08-1{n + 1}T00:00:00Z"
        records.append(line(f"t-{n}", "harness", tokens=500, gates=GREEN, ts=stamp))
        records.append(line(f"t-{n}", "vanilla", tokens=100, gates=GREEN, ts=stamp))
    verdict = build_verdict(records, ab=AB)
    assert verdict.streak == 3
    assert verdict.triggered


def test_one_harness_win_breaks_the_streak() -> None:
    """Consecutive means consecutive: the streak is counted from the most recent pair."""
    records = [
        line("t-0", "harness", tokens=500, gates=GREEN, ts="2026-08-11T00:00:00Z"),
        line("t-0", "vanilla", tokens=100, gates=GREEN, ts="2026-08-11T00:00:00Z"),
        line("t-1", "harness", tokens=500, gates=GREEN, ts="2026-08-12T00:00:00Z"),
        line("t-1", "vanilla", tokens=100, gates=GREEN, ts="2026-08-12T00:00:00Z"),
        line("t-2", "harness", tokens=100, gates=GREEN, ts="2026-08-13T00:00:00Z"),
        line("t-2", "vanilla", tokens=500, gates=GREEN, ts="2026-08-13T00:00:00Z"),
    ]
    verdict = build_verdict(records, ab=AB)
    assert verdict.streak == 0
    assert not verdict.triggered


def test_cadence_counts_distinct_harness_tickets_since_the_last_baseline() -> None:
    records = [
        line("t-0", "vanilla"),
        line("t-1", "harness", stage="implement"),
        line("t-1", "harness", stage="review"),
        line("t-2", "harness"),
    ]
    assert tickets_since_baseline(records) == 2


def test_a_sample_is_due_at_the_configured_cadence() -> None:
    records = [line(f"t-{n}", "harness") for n in range(10)]
    assert build_verdict(records, ab=AB).sample_due
    assert not build_verdict(records[:9], ab=AB).sample_due


def test_cadence_of_zero_disables_the_nudge() -> None:
    records = [line(f"t-{n}", "harness") for n in range(50)]
    assert not build_verdict(records, ab=AbConfig(vanilla_every=0)).sample_due


def test_an_empty_store_reports_no_comparison_rather_than_a_good_one() -> None:
    verdict = build_verdict([], ab=AB)
    assert not verdict.has_data
    assert not verdict.triggered
    assert verdict.streak == 0
