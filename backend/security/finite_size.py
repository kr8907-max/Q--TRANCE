"""Finite-sample statements about an unknown rate.

Two methods, both with a verified primary citation
--------------------------------------------------
**Exact Clopper-Pearson binomial interval.** Inverts the binomial tail exactly,
so the coverage guarantee is at least the nominal confidence for every sample
size, including very small ones. It is the method the threshold is derived from,
because it is conservative where it matters: the upper bound it produces is the
honest mismatch probability the threshold is built on, and an under-estimated
bound is a threshold that rejects honest sessions.

    C. J. Clopper and E. S. Pearson, "The use of confidence or fiducial limits
    illustrated in the case of the binomial", *Biometrika* **26**(4), 404-413
    (1934). DOI: 10.1093/biomet/26.4.404

**Hoeffding's concentration inequality.** A distribution-free bound on how far an
empirical mean of bounded independent variables can sit from its expectation.
It is reported as a *cross-check* on the exact interval, never as a replacement:
it is valid under weaker distributional assumptions but is uniformly looser, so
using it to set the threshold would cost false rejections for no benefit.

    W. Hoeffding, "Probability inequalities for sums of bounded random
    variables", *Journal of the American Statistical Association* **58**(301),
    13-30 (1963). DOI: 10.1080/01621459.1963.10500830

What these bounds are not
-------------------------
Neither is a cryptographic security parameter, and neither is a forgery bound.
The sample size ``n`` is the number of usable verification states, which is an
experimental design value: it can be raised by the operator, it is public, and
it is not a secret. A cryptographic security parameter is a property of an
adversary's power, not of an experiment. Every record this module returns carries
``is_cryptographic_security_bound=False``, and constructing one with ``True``
raises.

The formulas used
-----------------
One-sided upper Hoeffding bound at confidence ``1 - alpha``::

    p  <=  p_hat + sqrt( ln(1/alpha) / (2n) )

Two-sided Hoeffding bound at confidence ``1 - alpha``::

    |p - p_hat|  <=  sqrt( ln(2/alpha) / (2n) )

Exact Clopper-Pearson upper bound at confidence ``1 - alpha``::

    p_upper  =  Beta^{-1}(1 - alpha; k + 1, n - k)

where ``k`` is the number of observed mismatches and ``n`` the number of usable
states. The implementation delegates to :mod:`backend.calibration.confidence`,
so the interval the threshold is built from and the interval reported here are
the same computation.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Tuple

from backend.calibration.confidence import lower_bound as _cp_lower
from backend.calibration.confidence import two_sided_interval as _cp_two_sided
from backend.calibration.confidence import upper_bound as _cp_upper
from backend.calibration.models import STATISTIC_MISMATCH_RATE

from backend.security.models import (
    BoundKind,
    BoundSidedness,
    FiniteSizeBound,
)

__all__ = [
    "CLOPPER_PEARSON_CITATION",
    "HOEFFDING_CITATION",
    "CLOPPER_PEARSON_ASSUMPTIONS",
    "HOEFFDING_ASSUMPTIONS",
    "clopper_pearson_bound",
    "hoeffding_radius",
    "hoeffding_bound",
    "required_sample_size",
    "compare_bounds",
    "observed_vs_bound_margin",
    "prediction_interval",
]

CLOPPER_PEARSON_CITATION = (
    "C. J. Clopper and E. S. Pearson, 'The use of confidence or fiducial limits "
    "illustrated in the case of the binomial', Biometrika 26(4), 404-413 (1934), "
    "DOI 10.1093/biomet/26.4.404"
)

HOEFFDING_CITATION = (
    "W. Hoeffding, 'Probability inequalities for sums of bounded random "
    "variables', Journal of the American Statistical Association 58(301), 13-30 "
    "(1963), DOI 10.1080/01621459.1963.10500830"
)


CLOPPER_PEARSON_ASSUMPTIONS: Tuple[str, ...] = (
    "each usable verification state contributes one Bernoulli mismatch indicator",
    "the mismatch indicators are independent",
    "the mismatch indicators share a common probability within the pooled sample",
)



HOEFFDING_ASSUMPTIONS: Tuple[str, ...] = (
    "the mismatch indicators are independent",
    "each indicator is bounded in [0, 1], which is automatic for a 0/1 variable",
    "the indicators need not share a common probability, so the bound covers the "
    "Poisson-binomial case as well",
)


def _check_counts(successes: int, trials: int) -> None:
    """Raise ``ValueError`` unless ``0 <= successes <= trials``."""
    if trials < 0:
        raise ValueError(f"trials must be non-negative, got {trials}")
    if successes < 0:
        raise ValueError(f"successes must be non-negative, got {successes}")
    if successes > trials:
        raise ValueError(
            f"successes ({successes}) cannot exceed trials ({trials})"
        )


def _check_confidence(confidence: float) -> None:
    """Raise ``ValueError`` unless ``0 < confidence < 1``."""
    if not 0.0 < float(confidence) < 1.0:
        raise ValueError(f"confidence must lie in (0, 1), got {confidence!r}")


def clopper_pearson_bound(
    successes: int,
    trials: int,
    *,
    confidence: float = 0.95,
    sidedness: BoundSidedness = BoundSidedness.UPPER,
    statistic: str = STATISTIC_MISMATCH_RATE,
) -> FiniteSizeBound:
    """Return the exact Clopper-Pearson bound for ``successes`` of ``trials``.

    The interval is exact in the sense that its coverage is at least the nominal
    confidence for every ``n``; it is deliberately conservative for small ``n``,
    which is the correct direction for a threshold that must not reject honest
    sessions.
    """
    _check_counts(successes, trials)
    _check_confidence(confidence)

    if trials == 0:



        return FiniteSizeBound(
            kind=BoundKind.EXACT_CLOPPER_PEARSON,
            sidedness=sidedness,
            statistic=statistic,
            sample_size=0,
            successes=0,
            confidence=float(confidence),
            lower=0.0,
            upper=1.0,
            point_estimate=None,
            method="Clopper-Pearson exact binomial interval",
            citation=CLOPPER_PEARSON_CITATION,
            assumptions=CLOPPER_PEARSON_ASSUMPTIONS,
            notes=(
                "with no trials the interval is the whole unit interval: an empty "
                "sample constrains nothing",
                "this is a statement about the unknown mismatch probability, not a "
                "decision rule",
            ),
        )

    if sidedness is BoundSidedness.UPPER:
        record = _cp_upper(successes, trials, confidence=confidence)
        lower, upper = record.lower, record.upper
    elif sidedness is BoundSidedness.LOWER:
        record = _cp_lower(successes, trials, confidence=confidence)
        lower, upper = record.lower, record.upper
    else:
        record = _cp_two_sided(successes, trials, confidence=confidence)
        lower, upper = record.lower, record.upper

    point = (successes / trials) if trials else None
    notes = [
        "the exact interval inverts the binomial tail, so its coverage is at "
        "least the nominal confidence for every sample size, including very small "
        "ones",
        "this is a statement about the unknown mismatch probability, not a "
        "decision rule; the decision rule derived from it lives in "
        "backend.calibration.thresholds",
    ]
    return FiniteSizeBound(
        kind=BoundKind.EXACT_CLOPPER_PEARSON,
        sidedness=sidedness,
        statistic=statistic,
        sample_size=int(trials),
        successes=int(successes),
        confidence=float(confidence),
        lower=lower,
        upper=upper,
        point_estimate=point,
        method="Clopper-Pearson exact binomial interval",
        citation=CLOPPER_PEARSON_CITATION,
        assumptions=CLOPPER_PEARSON_ASSUMPTIONS,
        notes=tuple(notes),
    )


def hoeffding_radius(
    trials: int,
    *,
    confidence: float = 0.95,
    sidedness: BoundSidedness = BoundSidedness.TWO_SIDED,
) -> float:
    """Return the Hoeffding radius ``epsilon`` for ``trials`` at ``confidence``.

    ``epsilon`` is the half-width of the deviation Hoeffding's inequality
    controls, so it is also the answer to "how many trials do I need for a given
    precision?" via :func:`required_sample_size`.
    """
    if trials < 0:
        raise ValueError(f"trials must be non-negative, got {trials}")
    _check_confidence(confidence)
    alpha = 1.0 - float(confidence)
    if trials == 0:
        return math.inf
    multiplier = 2.0 if sidedness is BoundSidedness.TWO_SIDED else 1.0
    return math.sqrt(math.log(multiplier / alpha) / (2.0 * trials))


def hoeffding_bound(
    successes: int,
    trials: int,
    *,
    confidence: float = 0.95,
    sidedness: BoundSidedness = BoundSidedness.UPPER,
    statistic: str = STATISTIC_MISMATCH_RATE,
) -> FiniteSizeBound:
    """Return the Hoeffding concentration bound for ``successes`` of ``trials``.

    Reported as a cross-check on the exact interval. It is valid under weaker
    assumptions but is uniformly looser, so a threshold derived from it would
    reject honest sessions more often for no gain in validity.
    """
    _check_counts(successes, trials)
    _check_confidence(confidence)

    point = (successes / trials) if trials else None
    radius = hoeffding_radius(
        trials, confidence=confidence, sidedness=sidedness
    )
    if point is None:
        lower = upper = None
    elif sidedness is BoundSidedness.UPPER:
        lower, upper = 0.0, min(1.0, point + radius)
    elif sidedness is BoundSidedness.LOWER:
        lower, upper = max(0.0, point - radius), 1.0
    else:
        lower, upper = max(0.0, point - radius), min(1.0, point + radius)

    return FiniteSizeBound(
        kind=BoundKind.HOEFFDING,
        sidedness=sidedness,
        statistic=statistic,
        sample_size=int(trials),
        successes=int(successes),
        confidence=float(confidence),
        lower=lower,
        upper=upper,
        point_estimate=point,
        method="Hoeffding concentration inequality",
        citation=HOEFFDING_CITATION,
        assumptions=HOEFFDING_ASSUMPTIONS,
        notes=(
            "distribution-free: it needs bounded independent indicators but not a "
            "common probability, so it also covers the inhomogeneous case",
            "it is uniformly looser than the exact interval, which is why the "
            "threshold is derived from the exact interval and this is a "
            "cross-check",
            "the radius shrinks as 1/sqrt(n): quadrupling the sample size halves "
            "it, which is a statement about estimator precision and not about "
            "security",
        ),
    )


def required_sample_size(
    radius: float,
    *,
    confidence: float = 0.95,
    sidedness: BoundSidedness = BoundSidedness.TWO_SIDED,
) -> int:
    """Return the smallest ``n`` whose Hoeffding radius is at most ``radius``.

    Inverts ``epsilon = sqrt(ln(m/alpha) / (2n))``. Useful for showing that the
    sample sizes in the benchmark are chosen for precision rather than being
    arbitrary, and for showing how fast the cost of precision grows.
    """
    if not 0.0 < float(radius) <= 1.0:
        raise ValueError(f"radius must lie in (0, 1], got {radius!r}")
    _check_confidence(confidence)
    alpha = 1.0 - float(confidence)
    multiplier = 2.0 if sidedness is BoundSidedness.TWO_SIDED else 1.0
    return math.ceil(math.log(multiplier / alpha) / (2.0 * float(radius) ** 2))


def compare_bounds(
    successes: int,
    trials: int,
    *,
    confidence: float = 0.95,
) -> Tuple[FiniteSizeBound, FiniteSizeBound]:
    """Return ``(exact, hoeffding)`` upper bounds for the same counts.

    Provided so a report can show both and state which one the threshold uses,
    rather than leaving a reader to wonder why two numbers are quoted.
    """
    return (
        clopper_pearson_bound(
            successes, trials, confidence=confidence, sidedness=BoundSidedness.UPPER
        ),
        hoeffding_bound(
            successes, trials, confidence=confidence, sidedness=BoundSidedness.UPPER
        ),
    )


def observed_vs_bound_margin(
    observed_successes: int,
    bound_upper: float,
    trials: int,
) -> Dict[str, Any]:
    """Return the margin between an observed count and an upper bound.

    The bound is expected to be a conservative upper bound (e.g. from
    :func:`clopper_pearson_bound`), so the margin is ``observed - upper`` in
    rate units. A positive margin means the observed count exceeds the bound.

    This is a **distance**, not a security parameter. It describes how far the
    observation sits from the calibrated honest model, not how secure the
    protocol is.
    """
    _check_counts(observed_successes, trials)
    if trials == 0:
        return {
            "observed_rate": None,
            "bound_upper": float(bound_upper),
            "margin_rate": None,
            "margin_count": None,
            "exceeds": False,
            "note": "no trials: the margin is undefined",
        }
    observed_rate = observed_successes / trials
    margin_rate = observed_rate - float(bound_upper)
    bound_count = float(bound_upper) * trials
    margin_count = observed_successes - bound_count
    return {
        "observed_rate": observed_rate,
        "bound_upper": float(bound_upper),
        "margin_rate": margin_rate,
        "margin_count": margin_count,
        "exceeds": margin_rate > 0,
        "note": (
            "margin_rate > 0 means the observation exceeds the honest upper "
            "bound; this is evidence of inconsistency with the honest model, "
            "not a forgery bound"
        ),
    }


def prediction_interval(
    trials: int,
    p: float,
    *,
    confidence: float = 0.95,
) -> Dict[str, Any]:
    """Return a prediction interval for a future Binomial(trials, p) count.

    This is **not** a confidence interval for the parameter ``p``; it is the
    range within which a future observation is expected to fall. It is wider
    than a confidence interval because it must account for the randomness of
    the future count as well as the parameter uncertainty.

    Here ``p`` is treated as fixed (e.g. the conservative ``p_upper`` from a
    calibration), so the interval is simply the ``alpha/2`` and ``1-alpha/2``
    quantiles of ``Binomial(trials, p)``.
    """
    from scipy import stats

    if trials < 0:
        raise ValueError(f"trials must be non-negative, got {trials}")
    if not 0.0 <= float(p) <= 1.0:
        raise ValueError(f"p must lie in [0, 1], got {p!r}")
    _check_confidence(confidence)
    alpha = 1.0 - float(confidence)
    lower_q = alpha / 2.0
    upper_q = 1.0 - lower_q
    k_low = max(0, int(stats.binom.ppf(lower_q, trials, float(p))))
    k_high = min(trials, int(stats.binom.ppf(upper_q, trials, float(p))))
    return {
        "sample_size": trials,
        "p": float(p),
        "confidence": float(confidence),
        "predicted_min": k_low,
        "predicted_max": k_high,
        "note": (
            "this is a prediction interval for a future observation, not a "
            "confidence interval for the parameter p"
        ),
    }
