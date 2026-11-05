"""Confidence intervals for the honest mismatch probability.

What a confidence interval is, and what it is not
-------------------------------------------------
An interval estimate describes a **parameter** given a sample. It is a
statement of the form "if the model holds, an interval built this way covers the
true probability in at least ``confidence`` of repetitions". It is:

* not a decision rule (see :mod:`backend.calibration.thresholds`);
* not a classification threshold;
* not a cryptographic security bound;
* not a forgery probability.

The four are different objects in different layers, and the project's
documentation states the distinction in the same words.

The construction
----------------
Clopper-Pearson, inverted from the exact binomial test. For ``k`` successes in
``n`` trials at confidence ``c`` with ``alpha = 1 - c``::

    two-sided lower  L = 0                                    if k = 0
                     L = Beta^{-1}(alpha/2;   k,     n - k + 1)  otherwise
    two-sided upper  U = 1                                    if k = n
                     U = Beta^{-1}(1-alpha/2; k + 1, n - k)      otherwise

    one-sided upper  U = 1                                    if k = n
                     U = Beta^{-1}(1-alpha;   k + 1, n - k)      otherwise
    one-sided lower  L = 0                                    if k = 0
                     L = Beta^{-1}(alpha;     k,     n - k + 1)  otherwise

The two-sided construction is Milestone 4's, reused here rather than
reimplemented so the project has exactly one definition of an exact binomial
interval. The one-sided bounds are what a threshold derivation needs, because
the decision it supports is one-directional: "is the mismatch rate *too high*?"

Coverage is *at least* the stated confidence -- Clopper-Pearson is conservative,
never anti-conservative -- and that is a property of the construction, not an
assumption about the data. The assumption it does make is that the trials are
independent and share one probability. Where that fails, the interval is an
approximation, and :class:`~backend.calibration.models.HomogeneityDiagnostic`
is what reports whether it fails for the configuration being used.
"""

from __future__ import annotations

from typing import Tuple

from scipy import stats

from backend.calibration.models import ConfidenceInterval
from backend.detection.statistics import exact_binomial_interval

__all__ = [
    "CLOPPER_PEARSON_TWO_SIDED",
    "CLOPPER_PEARSON_ONE_SIDED",
    "two_sided_interval",
    "upper_bound",
    "lower_bound",
    "require_confidence",
    "require_counts",
]


CLOPPER_PEARSON_TWO_SIDED = "clopper-pearson-exact-two-sided"


CLOPPER_PEARSON_ONE_SIDED = "clopper-pearson-exact-one-sided"


def require_confidence(confidence: float) -> float:
    """Return ``confidence`` as a float in ``(0, 1)``, or raise."""
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise ValueError(
            f"confidence must be a real number in (0, 1), got "
            f"{type(confidence).__name__}"
        )
    value = float(confidence)
    if not 0.0 < value < 1.0:
        raise ValueError(f"confidence must lie in (0, 1), got {value!r}")
    return value


def require_counts(successes: int, trials: int) -> Tuple[int, int]:
    """Return ``(successes, trials)`` after validating them, or raise."""
    if isinstance(trials, bool) or not isinstance(trials, int) or trials <= 0:
        raise ValueError(f"trials must be a positive int, got {trials!r}")
    if isinstance(successes, bool) or not isinstance(successes, int):
        raise ValueError(f"successes must be an int, got {successes!r}")
    if not 0 <= successes <= trials:
        raise ValueError(f"successes must lie in [0, {trials}], got {successes}")
    return successes, trials


def two_sided_interval(
    successes: int,
    trials: int,
    confidence: float,
) -> ConfidenceInterval:
    """Return the exact two-sided Clopper-Pearson interval.

    Delegates the arithmetic to Milestone 4's
    :func:`backend.detection.statistics.exact_binomial_interval` so the project
    has one implementation of the interval, and wraps the result in the typed
    record this layer passes around.
    """
    require_counts(successes, trials)
    value = require_confidence(confidence)
    lower, upper = exact_binomial_interval(successes, trials, confidence=value)
    return ConfidenceInterval(
        successes=successes,
        trials=trials,
        lower=lower,
        upper=upper,
        confidence=value,
        method=CLOPPER_PEARSON_TWO_SIDED,
        one_sided=False,
    )


def upper_bound(
    successes: int,
    trials: int,
    confidence: float,
) -> ConfidenceInterval:
    """Return the exact one-sided upper Clopper-Pearson bound.

    The bound ``U`` satisfies ``Pr[p <= U] >= confidence`` under the binomial
    model, where ``p`` is the true per-trial probability. ``U = 1`` when every
    trial succeeded: a finite sample can never rule out a certain event.

    The record is the standard one-sided interval ``[0, U]``; the point estimate
    is available from ``successes / trials`` and is not repeated as a lower
    limit, because it is not a lower limit.
    """
    successes, trials = require_counts(successes, trials)
    value = require_confidence(confidence)
    if successes == trials:
        upper = 1.0
    else:
        upper = float(stats.beta.ppf(value, successes + 1, trials - successes))
    return ConfidenceInterval(
        successes=successes,
        trials=trials,
        lower=0.0,
        upper=min(1.0, upper),
        confidence=value,
        method=CLOPPER_PEARSON_ONE_SIDED,
        one_sided=True,
    )


def lower_bound(
    successes: int,
    trials: int,
    confidence: float,
) -> ConfidenceInterval:
    """Return the exact one-sided lower Clopper-Pearson bound.

    Provided for completeness and for the symmetry tests; the reference
    threshold derivation uses :func:`upper_bound` only. The record is the
    standard one-sided interval ``[L, 1]``.
    """
    successes, trials = require_counts(successes, trials)
    value = require_confidence(confidence)
    alpha = 1.0 - value
    if successes == 0:
        lower = 0.0
    else:
        lower = float(stats.beta.ppf(alpha, successes, trials - successes + 1))
    return ConfidenceInterval(
        successes=successes,
        trials=trials,
        lower=max(0.0, lower),
        upper=1.0,
        confidence=value,
        method=CLOPPER_PEARSON_ONE_SIDED,
        one_sided=True,
    )
