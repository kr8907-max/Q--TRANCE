"""Threshold derivation: the one reference methodology.

The reference methodology
-------------------------
**Honest-null quantile with an upper confidence bound on the honest mismatch
probability.** In full:

1. From an honest-only calibration dataset, form the pooled per-state mismatch
   count ``K`` out of ``T`` usable observations.
2. Bound the honest per-state mismatch probability from above with the exact
   one-sided Clopper-Pearson bound at confidence ``1 - alpha_cal``::

       p_upper = Beta^{-1}(1 - alpha_cal; K + 1, T - K)

3. For a session of ``N`` usable observations, take the ``1 - alpha_eval``
   quantile of the honest null distribution evaluated at that bound::

       k_crit(N) = min { k : P[Binomial(N, p_upper) <= k] >= 1 - alpha_eval }
       theta(N)  = k_crit(N) / N

4. Reject ``H0`` when ``N_mismatch > k_crit(N)``.

Why this construction, and not the alternatives
-----------------------------------------------
**Not "5% mismatch means attack".** No number is written into the detector. The
threshold is an output of a stated procedure applied to stated data, and
:class:`~backend.calibration.models.ThresholdResult` records the procedure, the
data, the error budget and the resulting count.

**Sample size is load-bearing.** ``k_crit(N)`` is a quantile of a distribution
whose spread grows like ``sqrt(N)`` while its mean grows like ``N``, so
``theta(N)`` falls towards ``p_upper`` as ``N`` grows. A threshold derived at
``N = 100`` is therefore *not* valid at ``N = 10_000``, and
:meth:`~backend.calibration.models.ThresholdResult.rejects` refuses to apply one
at a size it was not derived for rather than silently mis-sizing the test.

**The error budget is split, not doubled.** Two sources of randomness enter:
the finite calibration sample fixes ``p_upper``, and the session under test is
itself a finite sample. Spending ``alpha`` on each would bound the total
false-rejection probability only by roughly ``2 * alpha``. The configuration
splits the budget instead (``alpha_cal + alpha_eval = alpha`` by default, evenly),
which is what makes ``alpha`` the number the operating point actually claims.

**It is conservative, and the project says so.** ``p_upper`` is already an upper
bound, and the quantile is then taken at that bound, so the empirical
false-rejection rate is expected to fall *below* ``alpha``. That is measured,
not assumed -- the reference operating point records the honest rejection rate
it actually observed on its own calibration data.

Alternatives considered
-----------------------
``honest-distribution quantile at the point estimate``
    Uses ``pooled_rate`` directly instead of an upper bound. Less conservative,
    and its level is only nominal: the point estimate is wrong by a random
    amount, so the realised rejection rate is not controlled. Rejected as the
    reference method; available because it is one line away, and *not* used.

``Neyman-Pearson operating point``
    Requires a specified alternative hypothesis and its likelihood ratio. The
    project has no defensible single alternative -- attacks differ in kind, and
    choosing one would silently privilege it. Deferred; not used.

``explicit target-FAR calibration``
    Requires malicious data to calibrate against, which the calibration/evaluation
    split forbids. This is what the *evaluation* layer measures afterwards, not
    what calibration optimises.
"""

from __future__ import annotations

from typing import Sequence, Tuple

from scipy import stats

from backend.calibration.confidence import upper_bound
from backend.calibration.models import (
    CalibrationResult,
    DatasetRole,
    ThresholdConfig,
    ThresholdResult,
)

__all__ = [
    "REFERENCE_THRESHOLD_METHOD",
    "critical_count",
    "derive_threshold",
    "derive_threshold_table",
    "rejection_probability",
    "expected_false_rejection_rate",
]


REFERENCE_THRESHOLD_METHOD = "honest-null-quantile-with-upper-confidence-bound"


def critical_count(
    p_upper: float,
    state_count: int,
    *,
    alpha: float,
) -> int:
    """Return the largest mismatch count still consistent with ``p_upper``.

    ``k_crit`` is the smallest ``k`` whose binomial cumulative probability at
    ``(state_count, p_upper)`` reaches ``1 - alpha``. A session is rejected when
    it exceeds ``k_crit``, so ``k_crit`` itself is still accepted.
    """
    if isinstance(state_count, bool) or not isinstance(state_count, int):
        raise ValueError(f"state_count must be an int, got {state_count!r}")
    if state_count < 1:
        raise ValueError(f"state_count must be positive, got {state_count}")
    if not 0.0 <= float(p_upper) <= 1.0:
        raise ValueError(f"p_upper must lie in [0, 1], got {p_upper!r}")
    if not 0.0 < float(alpha) < 1.0:
        raise ValueError(f"alpha must lie in (0, 1), got {alpha!r}")

    quantile = float(stats.binom.ppf(1.0 - float(alpha), state_count, float(p_upper)))
    if quantile != quantile:
        raise AssertionError("binomial quantile returned NaN for valid input")
    return max(0, min(int(quantile), state_count))


def rejection_probability(
    probability: float,
    state_count: int,
    critical: int,
) -> float:
    """Return ``P[Binomial(state_count, probability) > critical]``.

    Used to state the *expected* rejection rate a threshold implies, both under
    the honest bound (where it should be at most ``alpha_eval``) and under a
    hypothetical alternative. It is a model calculation, not a measurement; the
    measured rates live in :mod:`backend.evaluation`.
    """
    if not 0.0 <= float(probability) <= 1.0:
        raise ValueError(f"probability must lie in [0, 1], got {probability!r}")
    return float(
        1.0 - stats.binom.cdf(int(critical), int(state_count), float(probability))
    )


def expected_false_rejection_rate(
    p_upper: float,
    state_count: int,
    critical: int,
) -> float:
    """Return the worst-case expected honest rejection rate for a threshold."""
    return rejection_probability(p_upper, state_count, critical)


def derive_threshold(
    calibration: CalibrationResult,
    *,
    state_count: int | None = None,
    config: ThresholdConfig | None = None,
) -> ThresholdResult:
    """Derive a threshold from an honest calibration result.

    ``state_count`` defaults to the calibration dataset's own session size, and
    may be set to any other size to derive the threshold *for that size*. The
    two are different derivations, not one threshold reused: see the module
    docstring.

    Raises
    ------
    ValueError
        If the calibration dataset has no usable observations, if it is not a
        calibration-role dataset, or if the parameters are out of range. A
        threshold cannot be derived from an empty sample, and pretending
        otherwise would mean inventing one.
    """
    settings = (config or ThresholdConfig()).validate()
    if settings.method != REFERENCE_THRESHOLD_METHOD:
        raise ValueError(
            f"the reference implementation derives thresholds with "
            f"{REFERENCE_THRESHOLD_METHOD!r}; got {settings.method!r}. Other "
            f"methodologies are documented as considered and not used."
        )
    if calibration.config.dataset_role is not DatasetRole.CALIBRATION:
        raise ValueError(
            "a threshold may be derived only from a calibration-role dataset; got "
            f"{calibration.config.dataset_role.value!r}"
        )
    if calibration.total_valid <= 0:
        raise ValueError(
            "a threshold cannot be derived from a calibration dataset with no "
            "usable observations"
        )

    size = calibration.config.state_count if state_count is None else state_count
    if isinstance(size, bool) or not isinstance(size, int):
        raise ValueError(f"state_count must be an int, got {size!r}")
    if size < 1:
        raise ValueError(f"state_count must be positive, got {size}")

    bound = upper_bound(
        calibration.total_mismatch,
        calibration.total_valid,
        confidence=1.0 - settings.calibration_alpha,
    )
    p_upper = bound.upper
    critical = critical_count(
        p_upper, size, alpha=settings.evaluation_alpha
    )

    return ThresholdResult(
        state_count=size,
        p_upper=p_upper,
        critical_count=critical,
        threshold_rate=critical / size,
        config=settings,
        calibration_fingerprint=calibration.config.fingerprint(),
        calibration_session_count=calibration.session_count,
        calibration_total_valid=calibration.total_valid,
        calibration_total_mismatch=calibration.total_mismatch,
        calibration_pooled_rate=calibration.pooled_rate,
        calibration_role=calibration.config.dataset_role,
    )


def derive_threshold_table(
    calibration: CalibrationResult,
    state_counts: Sequence[int],
    *,
    config: ThresholdConfig | None = None,
) -> Tuple[ThresholdResult, ...]:
    """Derive one threshold per sample size, from one calibration dataset.

    This is the sample-size study in miniature: the honest bound ``p_upper`` is
    a property of the channel and does not depend on the session size, while the
    critical count and the threshold rate both do.
    """
    settings = config or ThresholdConfig()
    return tuple(
        derive_threshold(calibration, state_count=size, config=settings)
        for size in state_counts
    )
