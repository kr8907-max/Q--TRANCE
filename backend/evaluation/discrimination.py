"""The central discrimination experiment.

The question
------------
A detector that looks only at the marginal mismatch rate ``D_m`` sees one number
per session. Two very different worlds can produce the same number:

* an **honest channel** that is simply noisy, which disturbs every state a
  little; and
* a **malicious channel attack** that disturbs a few states completely.

If the observable evidence is only ``D_m``, these are the same world, and the
milestone brief asks us to say so plainly rather than imply otherwise.

What is compared
----------------
For each attack type:

1. run honest populations over a noise sweep and malicious populations over an
   intensity sweep;
2. **match the marginals** -- select the honest/malicious pair whose mean
   ``D_m`` are closest, so the comparison is at comparable marginal disturbance;
3. compute a fixed, non-learned structural descriptor for both populations --
   by default the per-basis mismatch dispersion
   ``max_basis_rate - min_basis_rate``, which is large when a disturbance
   concentrates in some measurement bases and small when it is spread evenly;
4. report whether the descriptor ranges separate, alongside what the calibrated
   marginal rule does to the same two populations.

Why the criterion is deliberately conservative
----------------------------------------------
The criterion is *non-overlap of the descriptor ranges*. Ranges are sensitive to
a single outlier, so this criterion fails to declare a separation more readily
than a mean comparison would. That is the right direction to err in: the claim
being tested is "the observable evidence can tell these apart", and a
conservative test that still succeeds is stronger evidence than a permissive one
that barely does.

The verdict string when the ranges overlap is fixed and literal:
``"Not distinguishable under the current observable model."``

What this experiment does not do
--------------------------------
It does not attribute a cause to a session. It does not train anything. It does
not claim the descriptor is a detector: the descriptor is a diagnostic, and the
verification decision remains the single calibrated test on ``D_m``. What it
shows is whether a *future* observable would carry additional information -- and
that is a statement about the model, not about a running detector.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Sequence, Tuple

from backend.calibration.models import OperatingPoint
from backend.simulation import ScenarioConfig

from backend.evaluation.metrics import metrics, summarise_population
from backend.evaluation.models import (
    DiscriminationResult,
    PopulationSummary,
    TrialRecord,
)
from backend.evaluation.sweeps import run_attack_population, run_honest_population

__all__ = [
    "DEFAULT_DESCRIPTOR",
    "NOT_DISTINGUISHABLE_VERDICT",
    "DESCRIPTORS",
    "descriptor_values",
    "MatchPair",
    "match_marginals",
    "compare_populations",
    "discrimination_experiment",
]


DEFAULT_DESCRIPTOR = "basis_mismatch_dispersion"


NOT_DISTINGUISHABLE_VERDICT = (
    "Not distinguishable under the current observable model."
)



DESCRIPTORS: Mapping[str, Callable[[TrialRecord], float | None]] = {
    "basis_mismatch_dispersion": lambda record: record.statistics.basis_mismatch_dispersion,
    "mean_fidelity": lambda record: record.statistics.mean_fidelity,
    "minimum_fidelity": lambda record: record.statistics.minimum_fidelity,
    "disturbance_rate": lambda record: record.statistics.disturbance_rate,
}


def descriptor_values(
    records: Sequence[TrialRecord], descriptor: str = DEFAULT_DESCRIPTOR
) -> Tuple[float, ...]:
    """Return the descriptor value of every record that has one."""
    selector = DESCRIPTORS.get(descriptor)
    if selector is None:
        raise ValueError(
            f"unknown descriptor {descriptor!r}; known descriptors are "
            f"{sorted(DESCRIPTORS)}"
        )
    return tuple(
        value
        for value in (selector(record) for record in records)
        if value is not None
    )


@dataclass(frozen=True)
class MatchPair:
    """Two populations selected so that their marginal mismatch rates align."""

    honest_x: float
    honest_records: Tuple[TrialRecord, ...]
    malicious_x: float
    malicious_records: Tuple[TrialRecord, ...]
    honest_marginal: float | None
    malicious_marginal: float | None
    gap: float | None
    matched: bool
    tolerance: float


def _mean_marginal(records: Sequence[TrialRecord]) -> float | None:
    """Return the mean observed mismatch rate of ``records``, or ``None``."""
    values = [
        record.statistics.mismatch_rate
        for record in records
        if record.statistics.mismatch_rate is not None
    ]
    if not values:
        return None
    return sum(values) / len(values)


def match_marginals(
    honest_samples: Sequence[Tuple[float, Sequence[TrialRecord]]],
    malicious_samples: Sequence[Tuple[float, Sequence[TrialRecord]]],
    *,
    tolerance: float = 0.01,
) -> MatchPair:
    """Select the honest/malicious pair with the closest mean mismatch rates.

    Selection is by marginal only, which is the point: the two populations are
    chosen so that a marginal rule has as little to work with as the sweep
    allows. The chosen intensities are recorded so the selection is auditable.

    A pair whose marginals are both exactly zero is skipped. It has a gap of
    zero and would always win, but it compares two undisturbed populations and
    therefore demonstrates nothing.
    """
    honest_scored = [
        (x, tuple(records), _mean_marginal(records)) for x, records in honest_samples
    ]
    malicious_scored = [
        (x, tuple(records), _mean_marginal(records)) for x, records in malicious_samples
    ]

    best: Tuple[float, float, float, Tuple[Any, ...], Tuple[Any, ...]] | None = None
    for honest_x, honest_records, honest_mean in honest_scored:
        if honest_mean is None:
            continue
        for malicious_x, malicious_records, malicious_mean in malicious_scored:
            if malicious_mean is None:
                continue
            if honest_mean == 0.0 and malicious_mean == 0.0:

                continue
            gap = abs(honest_mean - malicious_mean)
            if best is None or gap < best[0]:
                best = (
                    gap,
                    honest_x,
                    malicious_x,
                    (honest_records, honest_mean),
                    (malicious_records, malicious_mean),
                )

    if best is None:
        raise ValueError(
            "cannot match marginals: no population in either sweep produced a "
            "defined mean mismatch rate"
        )

    gap, honest_x, malicious_x, honest_payload, malicious_payload = best
    honest_records, honest_mean = honest_payload
    malicious_records, malicious_mean = malicious_payload
    return MatchPair(
        honest_x=float(honest_x),
        honest_records=honest_records,
        malicious_x=float(malicious_x),
        malicious_records=malicious_records,
        honest_marginal=honest_mean,
        malicious_marginal=malicious_mean,
        gap=gap,
        matched=gap <= tolerance,
        tolerance=tolerance,
    )


def _separation_rate(
    malicious_values: Sequence[float], honest_values: Sequence[float]
) -> float | None:
    """Return the share of malicious values above the honest maximum."""
    if not malicious_values or not honest_values:
        return None
    ceiling = max(honest_values)
    return sum(1 for value in malicious_values if value > ceiling) / len(
        malicious_values
    )


def compare_populations(
    honest_records: Sequence[TrialRecord],
    malicious_records: Sequence[TrialRecord],
    *,
    point: OperatingPoint,
    honest_label: str,
    malicious_label: str,
    descriptor: str = DEFAULT_DESCRIPTOR,
    marginals_matched: bool = True,
    marginal_gap: float | None = None,
    notes: Sequence[str] = (),
) -> DiscriminationResult:
    """Compare two populations under the conservative range-separation rule."""
    honest_summary = summarise_population(honest_records, honest_label)
    malicious_summary = summarise_population(malicious_records, malicious_label)

    honest_values = descriptor_values(honest_records, descriptor)
    malicious_values = descriptor_values(malicious_records, descriptor)

    criterion = (
        f"the [{descriptor}] ranges of the two populations must not overlap; "
        "this is a conservative, non-learned criterion and it errs towards "
        "reporting 'not distinguishable'"
    )

    distinguishable: bool | None
    if not honest_values or not malicious_values:
        distinguishable = None
    else:
        honest_low, honest_high = min(honest_values), max(honest_values)
        malicious_low, malicious_high = min(malicious_values), max(malicious_values)
        overlapping = not (honest_high < malicious_low or malicious_high < honest_low)
        distinguishable = not overlapping

    separation = _separation_rate(malicious_values, honest_values)

    honest_rejection = metrics(honest_records).frr
    malicious_rejection = metrics(malicious_records).detection_rate

    composed = list(notes)
    composed.append(
        "the decision rule itself was not changed by this experiment: the "
        "verification decision remains the single calibrated test on the "
        "mismatch rate"
    )
    if marginals_matched:
        composed.append(
            "the two populations were selected to have comparable marginal "
            "mismatch rates, so any separation reported here is separation the "
            "marginal rate alone does not provide"
        )
    else:
        composed.append(
            "the marginal mismatch rates of the two populations are NOT "
            "comparable, so this comparison does not isolate structural "
            "information"
        )

    if distinguishable is None:
        verdict = (
            "the descriptor is undefined on one of the populations, so no "
            "statement about discrimination can be made"
        )
    elif distinguishable:
        verdict = (
            f"distinguishable on [{descriptor}]: the malicious population's "
            "range lies outside the honest population's range, which the "
            "marginal mismatch rate alone does not reveal"
        )
    else:
        verdict = NOT_DISTINGUISHABLE_VERDICT

    return DiscriminationResult(
        honest_label=honest_label,
        malicious_label=malicious_label,
        honest_marginal=honest_summary.mean_mismatch_rate,
        malicious_marginal=malicious_summary.mean_mismatch_rate,
        marginal_gap=marginal_gap,
        matched=bool(marginals_matched),
        descriptor=descriptor,
        honest_descriptor=honest_summary,
        malicious_descriptor=malicious_summary,
        distinguishable=distinguishable,
        criterion=criterion,
        verdict=verdict,
        honest_rejection_rate=honest_rejection,
        malicious_rejection_rate=malicious_rejection,
        descriptor_separation_rate=separation,
        notes=tuple(composed),
    )


def discrimination_experiment(
    base: ScenarioConfig,
    point: OperatingPoint,
    *,
    evaluation_id: str,
    seed_start: int,
    trial_count: int,
    noise_type: str = "depolarizing",
    noise_strengths: Sequence[float] = (0.0, 0.001, 0.005, 0.01, 0.02, 0.05),
    attack_types: Sequence[str] = ("channel_tampering", "intercept_resend"),
    attack_fractions: Sequence[float] = (0.05, 0.10, 0.20, 0.50),
    descriptor: str = DEFAULT_DESCRIPTOR,
    tolerance: float = 0.01,
) -> Tuple[DiscriminationResult, ...]:
    """Run the discrimination experiment for each attack type.

    Honest populations are run once and reused across attack types; each attack
    type gets its own disjoint seed block.

    A zero-intensity attack is deliberately **not** in the default sweep. At
    fraction ``0`` the attack is the honest baseline, so matching against it
    would trivially select a no-op pair and demonstrate nothing; the candidate
    intensities must all be ones at which the attack actually acts.
    """
    honest_samples: Tuple[Tuple[float, Tuple[TrialRecord, ...]], ...] = tuple(
        (
            strength,
            run_honest_population(
                base,
                point,
                evaluation_id=f"{evaluation_id}-disc-honest-{strength:g}",
                seed_start=seed_start + index * trial_count,
                trial_count=trial_count,
                noise_type=noise_type,
                noise_strength=strength,
            ),
        )
        for index, strength in enumerate(noise_strengths)
    )

    results = []
    for attack_index, attack_type in enumerate(attack_types):
        attack_samples: Tuple[Tuple[float, Tuple[TrialRecord, ...]], ...] = tuple(
            (
                fraction,
                run_attack_population(
                    base,
                    point,
                    evaluation_id=f"{evaluation_id}-disc-{attack_type}-{fraction:g}",
                    seed_start=seed_start + 20_000 + attack_index * 10_000 + index * trial_count,
                    trial_count=trial_count,
                    attack_type=attack_type,
                    fraction=fraction,
                    noise_type=noise_type,
                    noise_strength=0.0,
                ),
            )
            for index, fraction in enumerate(attack_fractions)
        )

        pair = match_marginals(honest_samples, attack_samples, tolerance=tolerance)
        results.append(
            compare_populations(
                pair.honest_records,
                pair.malicious_records,
                point=point,
                honest_label=f"honest noise {noise_type} eta={pair.honest_x:g}",
                malicious_label=f"{attack_type} at fraction {pair.malicious_x:g}",
                descriptor=descriptor,
                marginals_matched=pair.matched,
                marginal_gap=pair.gap,
                notes=(
                    f"matched at honest eta={pair.honest_x:g} and "
                    f"{attack_type} fraction={pair.malicious_x:g}, chosen by "
                    "minimum marginal gap over the sweeps",
                    f"marginal gap after matching: {pair.gap!r} "
                    f"(tolerance {pair.tolerance:g})",
                ),
            )
        )
    return tuple(results)
