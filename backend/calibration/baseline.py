"""The honest baseline: what an honest but noisy session looks like.

The null model, stated exactly
------------------------------
``H0``
    The observed verification statistic is consistent with an **authorised
    honest session** under the specified channel/noise configuration.
``H1``
    The observed statistic is inconsistent with the calibrated honest model.

"No attack" does not mean "zero error". The honest channel is a real physical
process and it moves the received qubits, so the honest null is a distribution
over mismatch counts with a **non-zero** mean. For the depolarizing channel with
parameter ``eta`` every reference state has projective match probability
``1 - eta/2``, so a single projective measurement per state disagrees with the
expected eigenvalue with probability ``eta/2``. A calibration that assumed zero
honest error would reject honest sessions at a rate set by the noise, not by
``alpha``.

What is independent, what is identical, what is approximate
-----------------------------------------------------------
The model behind the interval is

    ``N_mismatch ~ Binomial(N, p0)``

and it rests on three claims, which the project states rather than assumes:

**Independent.** Conditional on the honest channel and the fixed signature state
sequence, the per-state outcomes are produced from independent per-state
generator streams (``backend.simulation.seed`` derives one stream per state), so
treating them as independent is faithful to the simulator. The analytic
probabilities the channel induces are treated as fixed, not random.

**Identically distributed.** This holds when the honest channel acts identically
on every reference state. The depolarizing channel does: its projective match
probability is ``1 - eta/2`` for all six Pauli eigenstates, so ``p_i`` is the
same for every ``i`` and the binomial model is *exact*. It does **not** hold for
the flip channels: a bit flip leaves ``|+>`` unchanged but flips ``|0>``, so the
``p_i`` differ and the count is Poisson-binomial, not binomial.
:class:`~backend.calibration.models.HomogeneityDiagnostic` measures the spread
and says which case applies.

**Approximate.** When the ``p_i`` differ, the Clopper-Pearson interval computed
from the pooled count is an approximation to an interval for the *mean*
probability. Its coverage is not guaranteed. The diagnostic reports the spread
so the approximation's size is visible; the reference operating point is
configured on a channel for which the model is exact.

Honest-only, enforced
---------------------
:func:`estimate_baseline` accepts only :class:`CalibrationObservation` records
whose role is ``CALIBRATION``, and that record type has no field for an attack
type, an attack fraction, a noise label or a ground-truth flag. There is
therefore no code path by which attack information could reach a baseline
estimate, and the test suite asserts the package never imports the attack or
simulation layers.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence, Tuple

from scipy import stats

from backend.calibration.confidence import two_sided_interval, upper_bound
from backend.calibration.models import (
    CalibrationConfig,
    CalibrationObservation,
    CalibrationResult,
    DatasetRole,
    HomogeneityDiagnostic,
)

__all__ = [
    "DEFAULT_PROJECTIVE_TOLERANCE",
    "HOMOGENEITY_TOLERANCE",
    "implied_mismatch_probability",
    "build_homogeneity_diagnostic",
    "estimate_baseline",
]




DEFAULT_PROJECTIVE_TOLERANCE = 1e-9





HOMOGENEITY_TOLERANCE = 1e-9


def implied_mismatch_probability(
    probability_expected: float,
    *,
    measurement_mode: str,
    shot_count: int,
    tolerance: float = DEFAULT_PROJECTIVE_TOLERANCE,
) -> float:
    """Return the per-state mismatch probability a configuration implies.

    The verifier's ``probability_expected`` is the analytic projective match
    probability ``q`` of the expected eigenvalue. How often the *recorded*
    outcome disagrees depends on how the outcome is produced:

    ``"projective-analytic"``
        The outcome is the deterministic analytic result, so the state is
        recorded as matching exactly when ``q >= 1 - tolerance`` and as
        mismatching otherwise. The implied probability is therefore 0 or 1 --
        this mode has no sampling distribution at all, which is why it cannot
        support a finite-sample calibration.

    ``"sampled"``
        ``shot_count`` finite-shot outcomes are drawn and the majority decides
        the recorded bit, so the state mismatches when fewer than half the shots
        land on the expected eigenvalue::

            p = P[Binomial(shot_count, q) < shot_count / 2]

        With ``shot_count = 1`` -- one projective measurement per state, the
        physical model -- this is exactly ``1 - q``.
    """
    if not 0.0 <= float(probability_expected) <= 1.0:
        raise ValueError(
            f"probability_expected must lie in [0, 1], got {probability_expected!r}"
        )
    if isinstance(shot_count, bool) or not isinstance(shot_count, int):
        raise ValueError(f"shot_count must be an int, got {shot_count!r}")
    if shot_count < 1:
        raise ValueError(f"shot_count must be positive, got {shot_count}")

    q = float(probability_expected)
    if measurement_mode != "sampled":
        return 0.0 if q >= 1.0 - float(tolerance) else 1.0




    threshold = (shot_count + 1) // 2 - 1
    return float(stats.binom.cdf(threshold, shot_count, q))


def build_homogeneity_diagnostic(
    predicted_probabilities: Sequence[float],
    *,
    tolerance: float = HOMOGENEITY_TOLERANCE,
) -> HomogeneityDiagnostic:
    """Return the homogeneity diagnostic for the implied mismatch probabilities.

    ``predicted_probabilities`` are the per-state mismatch probabilities the
    honest configuration implies. They are computed from the verifier's own
    analytic ``probability_expected`` values, which are observable, so no ground
    truth is involved.
    """
    values = tuple(float(value) for value in predicted_probabilities)
    if not values:
        return HomogeneityDiagnostic(
            state_count=0,
            predicted_probabilities=(),
            minimum=None,
            maximum=None,
            mean=None,
            spread=None,
            homogeneous=None,
            tolerance=float(tolerance),
            notes=(
                "no predicted probabilities were supplied, so the homogeneity of "
                "the binomial assumption could not be assessed",
            ),
        )

    minimum = min(values)
    maximum = max(values)
    spread = maximum - minimum
    homogeneous = bool(spread <= float(tolerance))
    notes = []
    if homogeneous:
        notes.append(
            "every reference state shares one implied mismatch probability, so "
            "the binomial model behind the interval is exact for this "
            "configuration"
        )
    else:
        notes.append(
            "the implied mismatch probabilities differ across reference states, "
            "so the mismatch count is Poisson-binomial rather than binomial; the "
            "interval computed from the pooled count is then an approximation "
            "whose coverage is not guaranteed"
        )
    return HomogeneityDiagnostic(
        state_count=len(values),
        predicted_probabilities=values,
        minimum=minimum,
        maximum=maximum,
        mean=sum(values) / len(values),
        spread=spread,
        homogeneous=homogeneous,
        tolerance=float(tolerance),
        notes=tuple(notes),
    )


def estimate_baseline(
    config: CalibrationConfig,
    observations: Iterable[CalibrationObservation],
    *,
    homogeneity_tolerance: float = HOMOGENEITY_TOLERANCE,
) -> CalibrationResult:
    """Estimate the honest baseline from an honest-only calibration dataset.

    Raises
    ------
    ValueError
        If the configuration is not a calibration configuration, if any
        observation carries a different dataset role, if the dataset is empty,
        or if an observation's sample size disagrees with the configuration.
        These are programming errors: a threshold fitted on the wrong data is
        worse than no threshold.
    """
    config.validate()
    records: Tuple[CalibrationObservation, ...] = tuple(
        observation.validate() for observation in observations
    )
    if not records:
        raise ValueError(
            "a calibration dataset must contain at least one honest observation"
        )
    for record in records:
        if record.dataset_role is not DatasetRole.CALIBRATION:
            raise ValueError(
                f"observation {record.experiment_id!r} carries dataset role "
                f"{record.dataset_role.value!r}; a calibration dataset accepts "
                f"only {DatasetRole.CALIBRATION.value!r}"
            )
        if record.state_count != config.state_count:
            raise ValueError(
                f"observation {record.experiment_id!r} has state_count "
                f"{record.state_count}, but the configuration specifies "
                f"{config.state_count}"
            )

    total_valid = sum(record.n_valid for record in records)
    total_mismatch = sum(record.n_mismatch for record in records)

    notes: list[str] = []
    if total_valid == 0:
        notes.append(
            "no usable observations: the honest mismatch probability is undefined "
            "rather than zero"
        )
        pooled_rate: float | None = None
        interval = None
        upper = None
    else:
        pooled_rate = total_mismatch / total_valid
        interval = two_sided_interval(
            total_mismatch, total_valid, confidence=config.confidence
        )
        upper = upper_bound(
            total_mismatch, total_valid, confidence=config.confidence
        )

    predicted: list[float] = []
    for record in records:
        predicted.extend(
            implied_mismatch_probability(
                probability,
                measurement_mode=config.measurement_mode,
                shot_count=config.shot_count,
            )
            for probability in record.analytic_match_probabilities
        )
    homogeneity = build_homogeneity_diagnostic(
        predicted, tolerance=homogeneity_tolerance
    )

    notes.append(
        "the baseline is estimated from honest sessions only; the dataset carries "
        "no attack label and the record type has no field for one"
    )
    notes.append(
        "the pooled rate treats every usable verification state as one Bernoulli "
        "observation, which is the null model's assertion, not a measurement"
    )

    return CalibrationResult(
        config=config,
        observations=records,
        total_valid=total_valid,
        total_mismatch=total_mismatch,
        pooled_rate=pooled_rate,
        interval=interval,
        upper_bound=upper,
        per_session_rates=tuple(
            record.mismatch_rate
            for record in records
            if record.mismatch_rate is not None
        ),
        homogeneity=homogeneity,
        notes=tuple(notes),
    )


def summarise_homogeneity(diagnostic: HomogeneityDiagnostic) -> dict[str, Any]:
    """Return a compact, JSON-ready summary of a homogeneity diagnostic."""
    return diagnostic.to_dict()
