"""Exact binomial intervals and one-sided bounds.

Tolerances here are not arbitrary. Clopper-Pearson bounds are available in closed
form through the beta quantile function, so the assertions compare against that
same closed form evaluated independently in the test, at ``1e-12``. Where a
property is asserted rather than a value -- containment, monotonicity, the edge
cases at zero and full success -- the assertion is exact (``==``) because the
mathematics is exact at those points.
"""

from __future__ import annotations

import pytest
from scipy import stats

from backend.calibration.confidence import (
    CLOPPER_PEARSON_ONE_SIDED,
    CLOPPER_PEARSON_TWO_SIDED,
    lower_bound,
    two_sided_interval,
    upper_bound,
)


def _exact_lower(k: int, n: int, confidence: float) -> float:
    alpha = 1.0 - confidence
    if k == 0:
        return 0.0
    return float(stats.beta.ppf(alpha / 2.0, k, n - k + 1))


def _exact_upper(k: int, n: int, confidence: float) -> float:
    alpha = 1.0 - confidence
    if k == n:
        return 1.0
    return float(stats.beta.ppf(1.0 - alpha / 2.0, k + 1, n - k))


@pytest.mark.parametrize(
    "k,n",
    [(0, 10), (1, 10), (5, 10), (9, 10), (10, 10), (0, 1), (1, 1), (3, 1000)],
)
def test_two_sided_interval_matches_the_closed_form(k: int, n: int) -> None:
    confidence = 0.95
    record = two_sided_interval(k, n, confidence=confidence)
    assert record.lower == pytest.approx(_exact_lower(k, n, confidence), abs=1e-12)
    assert record.upper == pytest.approx(_exact_upper(k, n, confidence), abs=1e-12)
    assert record.successes == k
    assert record.trials == n
    assert record.confidence == confidence
    assert record.method == CLOPPER_PEARSON_TWO_SIDED
    assert record.one_sided is False


def test_two_sided_interval_contains_the_point_estimate() -> None:
    record = two_sided_interval(37, 200, confidence=0.9)
    assert record.lower < 37 / 200 < record.upper


def test_zero_successes_pins_the_lower_end_at_zero() -> None:
    record = two_sided_interval(0, 50, confidence=0.95)
    assert record.lower == 0.0
    assert record.upper > 0.0


def test_all_successes_pins_the_upper_end_at_one() -> None:
    record = two_sided_interval(50, 50, confidence=0.95)
    assert record.upper == 1.0
    assert record.lower < 1.0


def test_interval_narrows_as_the_sample_grows() -> None:
    wide = two_sided_interval(10, 100, confidence=0.95)
    narrow = two_sided_interval(100, 1000, confidence=0.95)
    assert narrow.width < wide.width


def test_higher_confidence_widens_the_interval() -> None:
    low = two_sided_interval(20, 200, confidence=0.90)
    high = two_sided_interval(20, 200, confidence=0.99)
    assert high.width > low.width


def test_upper_bound_record_is_a_one_sided_interval() -> None:
    record = upper_bound(4, 500, confidence=0.95)
    assert record.lower == 0.0
    assert record.upper == pytest.approx(
        float(stats.beta.ppf(0.95, 5, 496)), abs=1e-12
    )
    assert record.one_sided is True
    assert record.method == CLOPPER_PEARSON_ONE_SIDED


def test_lower_bound_record_is_a_one_sided_interval() -> None:
    record = lower_bound(4, 500, confidence=0.95)
    assert record.upper == 1.0
    assert record.lower == pytest.approx(
        float(stats.beta.ppf(0.05, 4, 497)), abs=1e-12
    )
    assert record.one_sided is True


def test_upper_bound_is_below_the_two_sided_upper_end() -> None:


    one_sided = upper_bound(4, 500, confidence=0.95)
    two_sided = two_sided_interval(4, 500, confidence=0.95)
    assert one_sided.upper < two_sided.upper


@pytest.mark.parametrize("confidence", [0.0, 1.0, -0.5, 1.5, 2])
def test_invalid_confidence_is_refused(confidence: float) -> None:
    with pytest.raises(ValueError):
        two_sided_interval(1, 10, confidence=confidence)


@pytest.mark.parametrize(
    "k,n",
    [(-1, 10), (11, 10), (5, 0), (-1, 0)],
)
def test_invalid_counts_are_refused(k: int, n: int) -> None:
    with pytest.raises(ValueError):
        two_sided_interval(k, n, confidence=0.95)


def test_zero_trials_is_refused_rather_than_guessed() -> None:



    with pytest.raises(ValueError):
        upper_bound(0, 0, confidence=0.95)
    with pytest.raises(ValueError):
        two_sided_interval(0, 0, confidence=0.95)


def test_bounds_are_monotone_in_the_success_count() -> None:
    upper_bounds = [upper_bound(k, 100, confidence=0.95).upper for k in range(0, 11)]
    assert upper_bounds == sorted(upper_bounds)
    lower_bounds = [lower_bound(k, 100, confidence=0.95).lower for k in range(0, 11)]
    assert lower_bounds == sorted(lower_bounds)
