"""Mathematically justified rate estimation for the detection engine.

Why this module exists
----------------------
The detection engine reports *sampled* rates -- a mismatch rate over ``n``
observed states, a disturbance rate over ``n`` verification states. A bare
proportion hides how much information the sample carries: ``1/8`` and
``1000/8000`` are the same number and very different evidence.

Every rate the engine reports is therefore accompanied by an **exact
Clopper-Pearson binomial interval** at a stated confidence level. That is the
only statistical machinery in Milestone 4, and it exists so that:

* the evidence carries its own sample-size context;
* no arbitrary "within 5%" band is ever needed;
* Milestone 5 has a principled input for threshold calibration.

What this module deliberately does not do
-----------------------------------------
It performs **no hypothesis test** and computes **no p-value**. In particular it
does not implement "five independent tests at alpha = 0.05", which the
architecture review identified as a defect. Milestone 4 computes diagnostic
statistics and states their mathematical relationships; choosing a primary
verification statistic and handling multiple comparisons jointly belongs to
Milestone 5.

The interval is used to describe a sample, never to declare a threat.

Definition
----------
For ``k`` successes in ``n`` trials the Clopper-Pearson interval at confidence
``c`` is the exact interval ``[L, U]`` with::

    L = 0                          if k = 0
    L = Beta^{-1}(alpha/2;   k,     n - k + 1)   otherwise
    U = 1                          if k = n
    U = Beta^{-1}(1-alpha/2; k + 1, n - k)       otherwise

where ``alpha = 1 - c``. It is *conservative*: the true coverage is at least
``c``, so a false "the reference lies outside the interval" conclusion happens
with probability at most ``1 - c``.

The default confidence is 0.999 -- a 1-in-1000 description error budget,
matching the project's existing sampled-test policy
(``tests/quantum/statutil.py``). The two implementations are cross-checked
against each other in the test suite rather than assumed to agree.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from scipy import stats

__all__ = [
    "DEFAULT_CONFIDENCE",
    "RateEstimate",
    "exact_binomial_interval",
    "estimate_rate",
]


DEFAULT_CONFIDENCE = 0.999


def exact_binomial_interval(
    successes: int,
    trials: int,
    confidence: float = DEFAULT_CONFIDENCE,
) -> Tuple[float, float]:
    """Return the exact Clopper-Pearson interval for ``successes``/``trials``.

    Raises
    ------
    ValueError
        If ``trials`` is not positive, if ``successes`` lies outside
        ``[0, trials]``, or if ``confidence`` is not strictly between 0 and 1.
        These are programming errors: the analysis layer never produces such
        counts, because it validates observations before counting them.
    """
    if isinstance(trials, bool) or not isinstance(trials, int) or trials <= 0:
        raise ValueError(f"trials must be a positive int, got {trials!r}")
    if isinstance(successes, bool) or not isinstance(successes, int):
        raise ValueError(f"successes must be an int, got {successes!r}")
    if not 0 <= successes <= trials:
        raise ValueError(
            f"successes must lie in [0, {trials}], got {successes}"
        )
    if not 0.0 < confidence < 1.0:
        raise ValueError(f"confidence must lie in (0, 1), got {confidence!r}")

    alpha = 1.0 - confidence
    lower = (
        0.0
        if successes == 0
        else float(stats.beta.ppf(alpha / 2.0, successes, trials - successes + 1))
    )
    upper = (
        1.0
        if successes == trials
        else float(stats.beta.ppf(1.0 - alpha / 2.0, successes + 1, trials - successes))
    )
    return lower, upper


@dataclass(frozen=True)
class RateEstimate:
    """A sampled proportion together with its exact interval.

    ``defined`` is ``False`` when the denominator is zero -- the documented
    failure behaviour for every rate in this engine. An undefined rate is
    reported as ``None`` rather than as ``0.0``, because "no observations" and
    "no observed occurrences" are different statements.

    ``rate`` is the raw point estimate ``successes / trials``. It is a
    measurement, not a judgement: nothing in Milestone 4 compares it against a
    threshold to produce a verdict.
    """

    successes: int
    trials: int
    confidence: float
    rate: float | None
    lower: float | None
    upper: float | None
    defined: bool

    @property
    def width(self) -> float | None:
        """Return ``upper - lower``, or ``None`` when the rate is undefined."""
        if self.lower is None or self.upper is None:
            return None
        return self.upper - self.lower

    def excludes(self, reference: float) -> bool | None:
        """Return whether ``reference`` lies outside the interval.

        ``None`` when the estimate is undefined. This is a *description* of the
        sample, not a test decision: the caller decides what, if anything, to
        do with it, and Milestone 4 uses it only to label the strength of an
        already-reported anomaly.
        """
        if self.lower is None or self.upper is None:
            return None
        return reference < self.lower or reference > self.upper

    def to_dict(self) -> dict:
        return {
            "successes": self.successes,
            "trials": self.trials,
            "confidence": self.confidence,
            "rate": self.rate,
            "lower": self.lower,
            "upper": self.upper,
            "defined": self.defined,
        }


def estimate_rate(
    successes: int,
    trials: int,
    confidence: float = DEFAULT_CONFIDENCE,
) -> RateEstimate:
    """Return a :class:`RateEstimate` for ``successes`` out of ``trials``.

    A zero denominator yields an explicitly undefined estimate rather than a
    division error or a fabricated zero.
    """
    if isinstance(trials, bool) or not isinstance(trials, int) or trials < 0:
        raise ValueError(f"trials must be a non-negative int, got {trials!r}")
    if isinstance(successes, bool) or not isinstance(successes, int):
        raise ValueError(f"successes must be an int, got {successes!r}")
    if trials == 0:
        if successes != 0:
            raise ValueError("successes must be 0 when trials is 0")
        return RateEstimate(
            successes=0,
            trials=0,
            confidence=confidence,
            rate=None,
            lower=None,
            upper=None,
            defined=False,
        )
    lower, upper = exact_binomial_interval(successes, trials, confidence=confidence)
    return RateEstimate(
        successes=successes,
        trials=trials,
        confidence=confidence,
        rate=successes / trials,
        lower=lower,
        upper=upper,
        defined=True,
    )
