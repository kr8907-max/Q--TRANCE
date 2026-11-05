"""Tests for the rate estimation utilities.

The interval is the only statistical machinery Milestone 4 introduces, so it is
tested against an independent implementation rather than against itself.
"""

from __future__ import annotations

import pytest

from backend.detection import (
    DEFAULT_CONFIDENCE,
    RateEstimate,
    estimate_rate,
    exact_binomial_interval,
)
from tests.quantum.statutil import clopper_pearson_interval


def test_interval_matches_the_existing_project_implementation() -> None:
    """The detector's interval must agree with the project's sampled-test policy.

    ``tests/quantum/statutil.py`` already defines a Clopper-Pearson interval and
    documents it as the project's standard. Two implementations of the same
    formula must not drift, so they are compared directly instead of assumed
    equal.
    """
    for trials in (1, 5, 8, 16, 64, 1000):
        for successes in range(trials + 1):
            ours = exact_binomial_interval(successes, trials)
            theirs = clopper_pearson_interval(successes, trials)
            assert ours == pytest.approx(theirs, abs=1e-12)


def test_interval_is_exact_at_the_boundaries() -> None:
    lower, upper = exact_binomial_interval(0, 10)
    assert lower == 0.0
    assert 0.0 < upper < 1.0

    lower, upper = exact_binomial_interval(10, 10)
    assert upper == 1.0
    assert 0.0 < lower < 1.0


def test_interval_contains_the_point_estimate() -> None:
    for successes, trials in ((0, 7), (3, 7), (7, 7), (13, 16)):
        lower, upper = exact_binomial_interval(successes, trials)
        assert lower <= successes / trials <= upper


def test_interval_is_conservative_and_narrows_with_sample_size() -> None:
    """Coverage must not fall below the stated confidence, and more data helps."""

    small = exact_binomial_interval(1, 4)
    large = exact_binomial_interval(250, 1000)
    assert (large[1] - large[0]) < (small[1] - small[0])



    lower, upper = exact_binomial_interval(250, 1000, confidence=0.999)
    assert lower <= 0.25 <= upper


def test_undefined_rate_is_reported_as_undefined_not_zero() -> None:
    estimate = estimate_rate(0, 0)
    assert estimate.defined is False
    assert estimate.rate is None
    assert estimate.lower is None
    assert estimate.upper is None
    assert estimate.width is None
    assert estimate.excludes(0.5) is None


def test_defined_rate_reports_interval_and_exclusion() -> None:
    estimate = estimate_rate(0, 100)
    assert estimate.defined is True
    assert estimate.rate == 0.0
    assert estimate.successes == 0 and estimate.trials == 100
    assert estimate.confidence == DEFAULT_CONFIDENCE

    assert estimate.excludes(0.5) is True
    assert estimate.excludes(0.0) is False


    small = estimate_rate(0, 8)
    assert small.excludes(0.5) is False


def test_rate_estimate_serializes() -> None:
    payload = estimate_rate(3, 8).to_dict()
    assert payload["rate"] == pytest.approx(0.375)
    assert payload["defined"] is True
    assert set(payload) == {
        "successes",
        "trials",
        "confidence",
        "rate",
        "lower",
        "upper",
        "defined",
    }


@pytest.mark.parametrize(
    "successes, trials",
    [(1, 0), (0, -1), (True, 4), (2, True), (5, 4)],
)
def test_invalid_counts_are_rejected(successes: object, trials: object) -> None:
    with pytest.raises(ValueError):
        estimate_rate(successes, trials)  # type: ignore[arg-type]


@pytest.mark.parametrize("confidence", [0.0, 1.0, -0.1, 1.5])
def test_invalid_confidence_is_rejected(confidence: float) -> None:
    with pytest.raises(ValueError):
        exact_binomial_interval(1, 2, confidence=confidence)


def test_rate_estimate_is_frozen() -> None:
    estimate = estimate_rate(1, 2)
    assert isinstance(estimate, RateEstimate)
    with pytest.raises(Exception):
        estimate.rate = 0.9  # type: ignore[misc]
