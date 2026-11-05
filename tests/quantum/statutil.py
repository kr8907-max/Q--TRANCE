"""Statistical tolerance helpers for sampled quantum tests.

Justification
-------------
Sampled assertions must not use an arbitrary "within 5%" style band. Here the
tolerance is a **Clopper-Pearson exact binomial interval** computed from the
observed counts at a stated confidence level.

``assert_expected_probability(k, n, p, confidence)`` asserts that the
analytically expected probability ``p`` lies inside the exact interval for the
observed ``k`` successes out of ``n`` trials. Under the null hypothesis that
the true probability is ``p``, this assertion fails with probability at most
``1 - confidence``.

The default confidence is 0.999, i.e. a 1-in-1000 false-failure budget per
assertion. This is a deliberate, documented choice.
"""

from __future__ import annotations

from typing import Dict, Tuple

from scipy import stats

__all__ = [
    "DEFAULT_CONFIDENCE",
    "clopper_pearson_interval",
    "counts_to_probability",
    "assert_expected_probability",
]

DEFAULT_CONFIDENCE = 0.999


def clopper_pearson_interval(k: int, n: int, confidence: float = DEFAULT_CONFIDENCE) -> Tuple[float, float]:
    """Return the exact Clopper-Pearson interval for ``k`` successes in ``n`` trials."""
    if n <= 0:
        raise ValueError("n must be positive")
    if not 0 <= k <= n:
        raise ValueError(f"k must lie in [0, n], got k={k}, n={n}")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must lie in (0, 1)")

    alpha = 1.0 - confidence
    lower = 0.0 if k == 0 else float(stats.beta.ppf(alpha / 2.0, k, n - k + 1))
    upper = 1.0 if k == n else float(stats.beta.ppf(1.0 - alpha / 2.0, k + 1, n - k))
    return lower, upper


def counts_to_probability(counts: Dict[str, int], key: str) -> Tuple[int, int]:
    """Return ``(successes, total)`` for ``key`` in a count dictionary."""
    total = sum(int(v) for v in counts.values())
    return int(counts.get(key, 0)), total


def assert_expected_probability(
    successes: int,
    trials: int,
    expected: float,
    confidence: float = DEFAULT_CONFIDENCE,
) -> None:
    """Assert the analytic ``expected`` probability lies in the observed interval."""
    lower, upper = clopper_pearson_interval(successes, trials, confidence=confidence)
    assert lower <= expected <= upper, (
        f"expected p={expected!r} lies outside the {confidence:.3f}-confidence "
        f"Clopper-Pearson interval [{lower:.6f}, {upper:.6f}] from "
        f"{successes}/{trials} successes"
    )