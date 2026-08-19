"""Reading the A/B store: paired comparison, cadence, kill-criterion (ADR 0008).

`flux.ab` writes the baseline arm; this module is the half that decides what the two
arms mean. Three questions, all answered from the JSONL store alone so the answer is a
function of recorded data and never of anyone's recollection:

1. **Per ticket, who won?** Only tickets that ran *both* ways are compared — an
   unpaired ticket says nothing, and averaging over unpaired tickets is how a
   comparison becomes a story.
2. **Is a baseline sample due?** ``[ab] vanilla_every`` counts harness tickets since
   the last baseline. The cadence exists because a comparison nobody re-runs quietly
   becomes an old comparison.
3. **Has the kill-criterion fired?** ``[ab] kill_streak`` consecutive paired wins for
   vanilla, most recent first, and the answer is printed whether or not it is welcome.

**How "wins" is defined**, because the criterion's prose does not say and the code must:

* **Cost** is uncached input + output — what actually consumes a subscription window
  (`Usage.budget_tokens`), summed over every line the ticket cost including retries.
  Cache reads are excluded for the same reason the runner's budget excludes them.
* **Quality** is an ordinal from the gates the runner itself ran: acceptance green (3)
  beats all gates green (2) beats no gates at all (1) beats a failure (0). "Nothing
  verified it" cannot outrank "gates green", and it is not scored as a failure either.
  The top level exists because the one below it cannot detect an unimplemented feature
  (ADR 0011): the repo's own suite stays green when a session changes nothing, so
  "gates green" is only evidence that nothing broke, never that the ticket was done.
  "Acceptance green" is the verdict of the per-ticket held-out tests — written before
  either arm runs, stored outside both worktrees, run by flux against each arm's tree —
  and those are red until the feature exists.
* **Vanilla wins** a ticket when it is *strictly cheaper* and *not worse* on quality.
  Read the asymmetry as the criterion means it: the harness is the thing on trial, so a
  tie on quality at a lower price is a loss for the harness, not a draw.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from flux.metrics.record import MetricRecord


class AbPolicy(Protocol):
    """The ``[ab]`` half of the repo's config, as this module needs to read it.

    Structural rather than an import of :class:`~flux.config.AbConfig`: the metrics
    layer is underneath the config layer (config depends on gates, gates on metrics),
    and importing upward would close that cycle for the sake of three numbers.
    """

    @property
    def vanilla_every(self) -> int: ...

    @property
    def kill_streak(self) -> int: ...

    @property
    def kill_criterion(self) -> str: ...


HARNESS_VARIANT = "harness"
VANILLA_VARIANT = "vanilla"

ACCEPTANCE_GATE = "held-out"
"""Name of the gate that runs a ticket's held-out acceptance tests (ADR 0005/0011).

Defined here, at the bottom of the layering, so the stages that append the gate and
this module that scores it share one spelling — the quality ordinal keys on it, and a
drifted name would silently demote every acceptance verdict to "gates green"."""

# Quality ordinal. Deliberately coarse: the gate suite is a verdict, not a score.
QUALITY_FAILED = 0
QUALITY_UNVERIFIED = 1
QUALITY_GREEN = 2
QUALITY_ACCEPTED = 3

_QUALITY_LABELS = {
    QUALITY_FAILED: "gates red",
    QUALITY_UNVERIFIED: "no gates",
    QUALITY_GREEN: "gates green",
    QUALITY_ACCEPTED: "acceptance green",
}


@dataclass(frozen=True, slots=True)
class Arm:
    """One ticket's cost and quality under one variant, over all of its lines."""

    ticket: str
    variant: str
    runs: int = 0
    billable_tokens: int = 0
    """Uncached in + out: what the ticket actually consumed from the usage window."""

    wall_ms: int = 0
    failed_sessions: int = 0
    """Attempts that did not complete. A cost signal, not a quality one — a retry that
    then succeeded is money spent, not a defect shipped."""

    gates: tuple[tuple[str, bool], ...] = ()
    """Latest verdict per gate name, in first-seen order.

    Latest, not every, because the review↔fix loop re-runs the suite: a gate that was
    red at implement and green after the fix ends green, and a ticket whose last stage
    happens to run no gates keeps the verdict of the stage that did."""

    final_ok: bool = True
    """Did the ticket's last recorded attempt complete? A park lands here."""

    last_ts: str = ""

    @property
    def quality(self) -> int:
        """The ordinal the pairing is judged on — see the module docstring.

        An arm reaches :data:`QUALITY_ACCEPTED` only through a green
        :data:`ACCEPTANCE_GATE` verdict; "every gate green" without one tops out at
        :data:`QUALITY_GREEN`, because a suite that predates the ticket cannot say the
        ticket was done (ADR 0011). Any red gate — acceptance included — is a failure.
        """
        if not self.final_ok or any(not passed for _, passed in self.gates):
            return QUALITY_FAILED
        if not self.gates:
            return QUALITY_UNVERIFIED
        if any(name == ACCEPTANCE_GATE for name, _ in self.gates):
            return QUALITY_ACCEPTED
        return QUALITY_GREEN

    @property
    def quality_label(self) -> str:
        return _QUALITY_LABELS[self.quality]


@dataclass
class _ArmAccumulator:
    """Mutable half of :class:`Arm`; gates need last-wins semantics to fold."""

    ticket: str
    variant: str
    runs: int = 0
    billable_tokens: int = 0
    wall_ms: int = 0
    failed_sessions: int = 0
    final_ok: bool = True
    last_ts: str = ""
    gates: dict[str, bool] = field(default_factory=dict[str, bool])

    def add(self, record: MetricRecord) -> None:
        self.runs += 1
        self.billable_tokens += (
            record.input_tokens + record.cache_creation_tokens + record.output_tokens
        )
        self.wall_ms += record.wall_ms
        self.failed_sessions += int(not record.ok)
        self.final_ok = record.ok
        self.last_ts = max(self.last_ts, record.ts)
        for gate in record.gates:
            self.gates[gate.name] = gate.passed

    def build(self) -> Arm:
        return Arm(
            ticket=self.ticket,
            variant=self.variant,
            runs=self.runs,
            billable_tokens=self.billable_tokens,
            wall_ms=self.wall_ms,
            failed_sessions=self.failed_sessions,
            gates=tuple(self.gates.items()),
            final_ok=self.final_ok,
            last_ts=self.last_ts,
        )


@dataclass(frozen=True, slots=True)
class Pairing:
    """A ticket that ran both ways — the only unit the comparison is made of."""

    ticket: str
    harness: Arm
    vanilla: Arm

    @property
    def cheaper_variant(self) -> str:
        if self.vanilla.billable_tokens < self.harness.billable_tokens:
            return VANILLA_VARIANT
        if self.harness.billable_tokens < self.vanilla.billable_tokens:
            return HARNESS_VARIANT
        return "tie"

    @property
    def vanilla_wins(self) -> bool:
        """Strictly cheaper and not worse — see the module docstring on the asymmetry."""
        return (
            self.vanilla.billable_tokens < self.harness.billable_tokens
            and self.vanilla.quality >= self.harness.quality
        )

    @property
    def token_ratio(self) -> float | None:
        """Harness cost as a multiple of vanilla's. ``None`` when vanilla spent nothing."""
        if not self.vanilla.billable_tokens:
            return None
        return self.harness.billable_tokens / self.vanilla.billable_tokens

    @property
    def order_key(self) -> str:
        """Sort key: a pairing is as recent as the later of its two arms."""
        return max(self.harness.last_ts, self.vanilla.last_ts)


@dataclass(frozen=True, slots=True)
class AbVerdict:
    """Everything ``flux metrics`` says about the A/B baseline."""

    pairings: tuple[Pairing, ...] = ()
    unpaired_harness: tuple[str, ...] = ()
    """Tickets the harness ran that no baseline has ever been measured against."""

    tickets_since_baseline: int = 0
    vanilla_every: int = 0
    kill_streak: int = 0
    streak: int = 0
    """Consecutive most-recent pairings vanilla won."""

    criterion: str = ""

    @property
    def sample_due(self) -> bool:
        """Is it time to spend a baseline sample? ``vanilla_every = 0`` disables it."""
        return self.vanilla_every > 0 and self.tickets_since_baseline >= self.vanilla_every

    @property
    def triggered(self) -> bool:
        return self.kill_streak > 0 and self.streak >= self.kill_streak

    @property
    def has_data(self) -> bool:
        return bool(self.pairings)


def build_verdict(records: Sequence[MetricRecord], *, ab: AbPolicy) -> AbVerdict:
    """Fold the store into the A/B verdict. Pure: same lines in, same verdict out."""
    arms = _arms(records)
    pairings = tuple(
        sorted(
            (
                Pairing(ticket=ticket, harness=by_variant[HARNESS_VARIANT], vanilla=vanilla)
                for ticket, by_variant in arms.items()
                if (vanilla := by_variant.get(VANILLA_VARIANT)) is not None
                and HARNESS_VARIANT in by_variant
            ),
            key=lambda p: p.order_key,
        )
    )
    unpaired = tuple(
        ticket
        for ticket, by_variant in arms.items()
        if HARNESS_VARIANT in by_variant and VANILLA_VARIANT not in by_variant
    )
    return AbVerdict(
        pairings=pairings,
        unpaired_harness=unpaired,
        tickets_since_baseline=tickets_since_baseline(records),
        vanilla_every=ab.vanilla_every,
        kill_streak=ab.kill_streak,
        streak=_trailing_wins(pairings),
        criterion=ab.kill_criterion,
    )


def tickets_since_baseline(records: Sequence[MetricRecord]) -> int:
    """Distinct harness tickets recorded since the last baseline sample.

    Counted over the store's own order, which is append order, which is time order —
    the file is the clock. A ticket that spans the boundary counts as after it: what
    the cadence is measuring is "how long since the harness was last checked".
    """
    seen: set[str] = set()
    for record in reversed(records):
        if record.variant == VANILLA_VARIANT:
            break
        if record.variant == HARNESS_VARIANT and record.ticket:
            seen.add(record.ticket)
    return len(seen)


def _arms(records: Iterable[MetricRecord]) -> dict[str, dict[str, Arm]]:
    """Roll every line up to one :class:`Arm` per (ticket, variant), in record order."""
    acc: dict[str, dict[str, _ArmAccumulator]] = {}
    for record in records:
        if record.variant not in (HARNESS_VARIANT, VANILLA_VARIANT):
            continue
        by_variant = acc.setdefault(record.ticket, {})
        arm = by_variant.setdefault(
            record.variant, _ArmAccumulator(ticket=record.ticket, variant=record.variant)
        )
        arm.add(record)
    return {
        ticket: {variant: arm.build() for variant, arm in by_variant.items()}
        for ticket, by_variant in acc.items()
    }


def _trailing_wins(pairings: Sequence[Pairing]) -> int:
    """How many of the most recent pairings vanilla won, unbroken."""
    streak = 0
    for pairing in reversed(pairings):
        if not pairing.vanilla_wins:
            break
        streak += 1
    return streak
