"""Threat-specific bounds: deterministic exceedance and conservative separation.

This module provides the mathematical bridge between an observed mismatch count
and a security-relevant statement about it. It does **not** convert a detection
rate into a forgery probability, and it does **not** label a confidence interval
as a cryptographic bound.

What it provides
----------------
:func:`threshold_exceedance`
    For one session's mismatch count, the threshold's critical count and the
    session size: does it exceed? By how many states? By what rate?

:func:`statistical_separation`
    Between an observed mismatch rate and the calibrated honest upper bound:
    what is the conservative gap?

:func:`honest_prediction`
    The predicted range of mismatch counts under the calibrated honest model,
    so that an observed count outside that range is visible as anomalous.

What it does not provide
------------------------
* No forgery probability. FAR is an empirical acceptance rate, not a
  cryptographic adversary success probability.
* No information-theoretic security parameter. The sample size is a design
  value, not a security parameter.
* No optimal threshold. The reference point is specified, not optimised.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple

from backend.calibration.models import STATISTIC_MISMATCH_RATE, ThresholdResult
from backend.security.finite_size import (
    CLOPPER_PEARSON_CITATION,
    clopper_pearson_bound,
)
from backend.security.models import (
    BoundKind,
    BoundSidedness,
    FiniteSizeBound,
)

__all__ = [
    "ThresholdExceedance",
    "StatisticalSeparation",
    "HonestPrediction",
    "threshold_exceedance",
    "statistical_separation",
    "honest_prediction",
    "exceedance_probability",
]


@dataclass(frozen=True)
class ThresholdExceedance:
    """The deterministic result of applying a threshold to one session."""

    n_mismatch: int
    n_valid: int
    critical_count: int
    exceeds: bool
    margin: int
    margin_rate: float | None
    notes: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "n_mismatch": int(self.n_mismatch),
            "n_valid": int(self.n_valid),
            "critical_count": int(self.critical_count),
            "exceeds": bool(self.exceeds),
            "margin": int(self.margin),
            "margin_rate": self.margin_rate,
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class StatisticalSeparation:
    """Conservative gap between an observed rate and the honest upper bound.

    The ``separation_rate`` is ``observed_rate - honest_upper``. When it is
    positive the observed rate lies outside the calibrated honest range at the
    stated confidence level. This is evidence of inconsistency with the honest
    model, not attribution of a cause and not a forgery bound.
    """

    honest_upper: float
    observed_rate: float
    separation_rate: float | None
    conclusion: str
    notes: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "honest_upper": float(self.honest_upper),
            "observed_rate": float(self.observed_rate),
            "separation_rate": self.separation_rate,
            "conclusion": self.conclusion,
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class HonestPrediction:
    """The range of mismatch counts expected under the calibrated honest model.

    This is a **prediction interval** for a future observation, not a confidence
    interval for the parameter. The distinction matters: a confidence interval
    says where the true rate probably lies; a prediction interval says where a
    single future count probably lies. The prediction interval is wider because
    it accounts for both parameter uncertainty and the randomness of the future
    observation itself.
    """

    sample_size: int
    honest_upper_rate: float
    predicted_max_mismatch: int
    predicted_min_mismatch: int
    confidence: float
    notes: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sample_size": int(self.sample_size),
            "honest_upper_rate": float(self.honest_upper_rate),
            "predicted_max_mismatch": int(self.predicted_max_mismatch),
            "predicted_min_mismatch": int(self.predicted_min_mismatch),
            "confidence": float(self.confidence),
            "notes": list(self.notes),
        }


def threshold_exceedance(
    n_mismatch: int,
    n_valid: int,
    threshold: ThresholdResult,
) -> ThresholdExceedance:
    """Return the deterministic exceedance of a threshold by one session.

    The threshold carries its own ``state_count``, which is the ``N`` it was
    derived for. If ``n_valid`` differs from that, the threshold refuses to
    decide, and this function raises rather than silently guessing.
    """
    if n_valid != threshold.state_count:
        raise ValueError(
            f"the threshold was derived for N={threshold.state_count}, "
            f"but the session has n_valid={n_valid}; a threshold is not "
            f"valid outside the sample size it was derived for"
        )
    k_crit = threshold.critical_count
    exceeds = int(n_mismatch) > k_crit
    margin = int(n_mismatch) - k_crit
    margin_rate = (margin / n_valid) if n_valid > 0 else None
    notes: Tuple[str, ...] = (
        "exceeds=True means the session's mismatch count is strictly greater "
        "than the critical count; the critical count itself is still accepted",
        "margin = n_mismatch - k_crit; a positive margin means the count "
        "exceeds the threshold, a negative margin means it falls below it",
        "margin_rate = margin / N; it is comparable across sample sizes "
        "because both margin and N scale together",
    )
    return ThresholdExceedance(
        n_mismatch=int(n_mismatch),
        n_valid=int(n_valid),
        critical_count=k_crit,
        exceeds=exceeds,
        margin=margin,
        margin_rate=margin_rate,
        notes=notes,
    )


def statistical_separation(
    observed_mismatch_rate: float,
    honest_upper_rate: float,
    *,
    notes: Tuple[str, ...] = (),
) -> StatisticalSeparation:
    """Return the conservative gap between an observed rate and the honest upper bound.

    ``honest_upper_rate`` is typically ``threshold.p_upper`` or the upper end of
    a two-sided confidence interval. ``observed_mismatch_rate`` is the rate from
    one session under test.

    The separation is ``observed - upper``. A positive value means the observed
    rate exceeds the honest upper bound. A negative value means it lies inside
    the bound. Zero means it sits exactly on the bound.

    This is a **conservative** quantity because the upper bound is already
    conservative: the true honest rate is expected to fall below it with the
    stated confidence, so a positive separation is stronger evidence than the
    raw difference from a point estimate would be.
    """
    separation = float(observed_mismatch_rate) - float(honest_upper_rate)
    if separation > 0:
        conclusion = (
            "the observed mismatch rate exceeds the calibrated honest upper "
            "bound: the session is inconsistent with the honest model at the "
            "stated confidence level. This is evidence of inconsistency, not "
            "attribution of a cause and not a forgery bound."
        )
    elif separation < 0:
        conclusion = (
            "the observed mismatch rate lies within the calibrated honest "
            "upper bound: the session is consistent with the honest model at "
            "the stated confidence level. Consistency is not a proof of "
            "honesty, because an adversary can produce consistent observations."
        )
    else:
        conclusion = (
            "the observed mismatch rate equals the calibrated honest upper "
            "bound: the session is at the boundary of the calibrated honest "
            "model. This is the most ambiguous case and is treated as consistent "
            "because the threshold is strict (k_crit itself is accepted)."
        )
    return StatisticalSeparation(
        honest_upper=float(honest_upper_rate),
        observed_rate=float(observed_mismatch_rate),
        separation_rate=separation,
        conclusion=conclusion,
        notes=notes,
    )


def honest_prediction(
    threshold: ThresholdResult,
    *,
    confidence: float = 0.95,
) -> HonestPrediction:
    """Return a prediction interval for a future honest observation.

    A prediction interval for a future Binomial(N, p_upper) count is wider than
    a confidence interval for p itself, because it must account for the
    randomness of both the parameter estimate and the future observation. Here
    the parameter is treated as fixed at ``p_upper`` (the conservative bound),
    so the interval is the two-sided ``alpha/2`` and ``1 - alpha/2`` quantiles of
    that distribution, with ``alpha = 1 - confidence``::

        predicted_min = floor( binom.ppf(alpha / 2,     N, p_upper) )
        predicted_max = floor( binom.ppf(1 - alpha / 2, N, p_upper) )

    The upper end is the same quantile the threshold takes its critical count
    from whenever the threshold's evaluation alpha equals ``alpha / 2``, which is
    the default configuration (the error budget is split evenly between the
    calibration bound and the evaluation quantile, and the default confidence is
    0.95). In that configuration a count above the predicted maximum is exactly a
    count the threshold rejects, so the prediction interval and the decision rule
    agree by construction rather than by coincidence.
    """
    from scipy import stats

    n = threshold.state_count
    p = threshold.p_upper
    alpha = 1.0 - float(confidence)



    k_crit = stats.binom.ppf(1.0 - alpha / 2.0, n, p)

    k_low = stats.binom.ppf(alpha / 2.0, n, p) if alpha < 1.0 else 0.0
    return HonestPrediction(
        sample_size=n,
        honest_upper_rate=float(p),
        predicted_max_mismatch=max(0, int(k_crit)),
        predicted_min_mismatch=max(0, int(k_low)),
        confidence=float(confidence),
        notes=(
            "the prediction interval is for a future observation, not a "
            "confidence interval for the parameter; it is wider because it "
            "accounts for the randomness of the future count as well as the "
            "parameter uncertainty",
            "the predicted maximum is the 1 - alpha/2 quantile of "
            "Binomial(N, p_upper), the same quantile the threshold takes its "
            "critical count from when the threshold's evaluation alpha is "
            "alpha/2; that is the default configuration, so a count above the "
            "predicted maximum is a count the threshold rejects",
        ),
    )


def exceedance_probability(
    n_mismatch: int,
    n_valid: int,
    p_upper: float,
) -> float:
    """Return the probability of observing at least ``n_mismatch`` under H0.

    ``p_upper`` is the honest mismatch probability upper bound. The probability
    is ``P[Binomial(N, p_upper) >= n_mismatch]``, which is the p-value of the
    test that rejects when the count exceeds the critical value.

    This is **not** a cryptographic security parameter. It is the Type-I error
    rate for one specific count under the conservative honest model. It is
    smaller than alpha when the count exceeds the critical value, and larger
    when it does not. No quantity produced by this module is a cryptographic
    security parameter.
    """
    from scipy import stats

    _check_counts(n_mismatch, n_valid)
    if n_valid == 0:
        return 1.0
    if n_mismatch == 0:
        return 1.0

    return float(stats.binom.sf(n_mismatch - 1, n_valid, float(p_upper)))


def _check_counts(successes: int, trials: int) -> None:
    if trials < 0:
        raise ValueError(f"trials must be non-negative, got {trials}")
    if successes < 0:
        raise ValueError(f"successes must be non-negative, got {successes}")
    if successes > trials:
        raise ValueError(
            f"successes ({successes}) cannot exceed trials ({trials})"
        )
