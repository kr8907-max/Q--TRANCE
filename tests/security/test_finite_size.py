"""Finite-sample bounds, and the category error they must not be read into.

The milestone is explicit that a finite-sample statistical bound must **not** be
called a cryptographic security parameter, and that the four quantities
(confidence interval, classification threshold, empirical acceptance rate,
formal cryptographic security bound) must be kept apart. These tests pin the
arithmetic, the citations, the stated assumptions, and -- most importantly --
that the type system refuses to let a finite-sample bound claim to be a
cryptographic one.
"""

from __future__ import annotations

import math

import pytest
from scipy.stats import beta as beta_dist

from backend.security.finite_size import (
    CLOPPER_PEARSON_ASSUMPTIONS,
    CLOPPER_PEARSON_CITATION,
    HOEFFDING_ASSUMPTIONS,
    HOEFFDING_CITATION,
    clopper_pearson_bound,
    compare_bounds,
    hoeffding_bound,
    hoeffding_radius,
    required_sample_size,
)
from backend.security.models import BoundKind, BoundSidedness







def test_the_primary_citations_are_present_and_verifiable() -> None:


    assert "Hoeffding" in HOEFFDING_CITATION
    assert "1963" in HOEFFDING_CITATION
    assert "10.1080/01621459.1963.10500830" in HOEFFDING_CITATION
    assert "Clopper" in CLOPPER_PEARSON_CITATION
    assert "Pearson" in CLOPPER_PEARSON_CITATION
    assert "1934" in CLOPPER_PEARSON_CITATION
    assert "10.1093/biomet/26.4.404" in CLOPPER_PEARSON_CITATION


def test_no_citation_is_left_as_a_placeholder() -> None:
    for citation in (HOEFFDING_CITATION, CLOPPER_PEARSON_CITATION):
        assert "should be added" not in citation
        assert "TODO" not in citation
        assert "TBD" not in citation


def test_the_assumptions_behind_each_bound_are_stated() -> None:
    assert CLOPPER_PEARSON_ASSUMPTIONS
    assert HOEFFDING_ASSUMPTIONS

    assert any("bounded" in item for item in HOEFFDING_ASSUMPTIONS)







def test_a_finite_sample_bound_cannot_claim_to_be_a_cryptographic_bound() -> None:
    bound = clopper_pearson_bound(3, 100)
    assert bound.is_cryptographic_security_bound is False
    assert bound.kind is BoundKind.EXACT_CLOPPER_PEARSON


def test_constructing_a_bound_as_a_cryptographic_bound_raises() -> None:
    from backend.security.models import FiniteSizeBound

    with pytest.raises(ValueError, match="cryptographic"):
        FiniteSizeBound(
            kind=BoundKind.EXACT_CLOPPER_PEARSON,
            sidedness=BoundSidedness.UPPER,
            statistic="mismatch_rate",
            sample_size=100,
            successes=3,
            confidence=0.95,
            lower=None,
            upper=0.09,
            point_estimate=0.03,
            method="clopper-pearson",
            citation=CLOPPER_PEARSON_CITATION,
            assumptions=CLOPPER_PEARSON_ASSUMPTIONS,
            is_cryptographic_security_bound=True,
        )


def test_a_bound_reports_which_statistic_it_is_about() -> None:
    assert clopper_pearson_bound(3, 100).statistic == "mismatch_rate"
    assert hoeffding_bound(3, 100).statistic == "mismatch_rate"







def test_the_upper_bound_is_the_one_sided_quantile() -> None:



    bound = clopper_pearson_bound(3, 100, confidence=0.95, sidedness=BoundSidedness.UPPER)
    assert bound.sidedness is BoundSidedness.UPPER
    assert bound.lower == 0.0
    assert bound.upper == pytest.approx(beta_dist.ppf(0.95, 4, 97), abs=1e-12)
    assert bound.point_estimate == pytest.approx(0.03)


def test_the_lower_bound_is_the_mirror_of_the_upper() -> None:
    lower = clopper_pearson_bound(
        3, 100, confidence=0.95, sidedness=BoundSidedness.LOWER
    )



    assert lower.upper == 1.0
    assert lower.lower == pytest.approx(beta_dist.ppf(0.05, 3, 98), abs=1e-12)


    mirrored = clopper_pearson_bound(
        97, 100, confidence=0.95, sidedness=BoundSidedness.UPPER
    )
    assert lower.lower == pytest.approx(1.0 - mirrored.upper, abs=1e-12)


def test_the_two_sided_bound_is_the_two_tailed_construction() -> None:
    bound = clopper_pearson_bound(
        3, 100, confidence=0.95, sidedness=BoundSidedness.TWO_SIDED
    )
    assert bound.lower == pytest.approx(beta_dist.ppf(0.025, 3, 98), abs=1e-12)
    assert bound.upper == pytest.approx(beta_dist.ppf(0.975, 4, 97), abs=1e-12)


def test_the_two_sided_bound_brackets_the_point_estimate() -> None:
    bound = clopper_pearson_bound(
        30, 100, confidence=0.95, sidedness=BoundSidedness.TWO_SIDED
    )
    assert bound.lower is not None and bound.upper is not None
    assert bound.lower < bound.point_estimate < bound.upper
    assert bound.lower == pytest.approx(0.2125, abs=5e-4)
    assert bound.upper == pytest.approx(0.3998, abs=5e-4)


def test_more_evidence_narrows_the_interval() -> None:
    narrow = clopper_pearson_bound(30, 1000)
    wide = clopper_pearson_bound(3, 100)
    assert (narrow.upper - narrow.lower) < (wide.upper - wide.lower)


def test_the_interval_widens_as_confidence_rises() -> None:
    loose = clopper_pearson_bound(30, 100, confidence=0.80)
    tight = clopper_pearson_bound(30, 100, confidence=0.99)
    assert tight.upper > loose.upper


def test_zero_trials_yields_the_whole_unit_interval() -> None:



    bound = clopper_pearson_bound(0, 0)
    assert (bound.lower, bound.upper) == (0.0, 1.0)
    assert bound.point_estimate is None


def test_zero_successes_still_admits_a_positive_upper_bound() -> None:


    bound = clopper_pearson_bound(0, 100)
    assert bound.upper == pytest.approx(0.0295, abs=5e-4)
    assert bound.upper > 0.0


def test_all_successes_still_admits_a_sub_unit_lower_bound() -> None:
    bound = clopper_pearson_bound(
        100, 100, confidence=0.95, sidedness=BoundSidedness.LOWER
    )


    assert bound.lower == pytest.approx(0.05 ** (1 / 100), abs=1e-12)
    assert bound.lower < 1.0


@pytest.mark.parametrize(
    "successes,trials",
    [(-1, 10), (11, 10), (5, 0)],
)
def test_impossible_counts_are_refused(successes: int, trials: int) -> None:
    with pytest.raises(ValueError):
        clopper_pearson_bound(successes, trials)







def test_the_hoeffding_radius_is_the_stated_formula() -> None:

    n, alpha = 400, 0.05
    assert hoeffding_radius(
        n, confidence=1 - alpha, sidedness=BoundSidedness.UPPER
    ) == pytest.approx(math.sqrt(math.log(1 / alpha) / (2 * n)), abs=1e-15)

    assert hoeffding_radius(
        n, confidence=1 - alpha, sidedness=BoundSidedness.TWO_SIDED
    ) == pytest.approx(math.sqrt(math.log(2 / alpha) / (2 * n)), abs=1e-15)


def test_the_two_sided_radius_is_the_larger() -> None:
    assert hoeffding_radius(
        500, sidedness=BoundSidedness.TWO_SIDED
    ) > hoeffding_radius(500, sidedness=BoundSidedness.UPPER)


def test_the_hoeffding_radius_shrinks_with_the_square_root_of_n() -> None:
    small = hoeffding_radius(100)
    large = hoeffding_radius(400)
    assert small / large == pytest.approx(2.0, abs=1e-12)


def test_the_hoeffding_bound_adds_the_radius_to_the_estimate() -> None:
    bound = hoeffding_bound(20, 400, confidence=0.95)
    assert bound.kind is BoundKind.HOEFFDING
    assert bound.upper == pytest.approx(
        0.05 + hoeffding_radius(400, confidence=0.95, sidedness=BoundSidedness.UPPER)
    )


def test_the_hoeffding_bound_is_never_tighter_than_clopper_pearson() -> None:


    exact, concentration = compare_bounds(30, 400)
    assert exact.kind is BoundKind.EXACT_CLOPPER_PEARSON
    assert concentration.kind is BoundKind.HOEFFDING
    assert concentration.upper >= exact.upper


def test_the_hoeffding_upper_bound_is_capped_at_one() -> None:
    bound = hoeffding_bound(90, 100, confidence=0.99)
    assert bound.upper <= 1.0







def test_the_required_sample_size_matches_the_closed_form() -> None:

    two_sided = math.ceil(math.log(2 / 0.05) / (2 * 0.005**2))
    one_sided = math.ceil(math.log(1 / 0.05) / (2 * 0.005**2))
    assert required_sample_size(
        0.005, confidence=0.95, sidedness=BoundSidedness.TWO_SIDED
    ) == two_sided
    assert required_sample_size(
        0.005, confidence=0.95, sidedness=BoundSidedness.UPPER
    ) == one_sided
    assert two_sided == 73778
    assert one_sided == 59915


def test_a_tighter_radius_needs_more_samples() -> None:
    assert required_sample_size(0.001) > required_sample_size(0.01)


def test_a_higher_confidence_needs_more_samples() -> None:
    assert required_sample_size(0.01, confidence=0.99) > required_sample_size(
        0.01, confidence=0.90
    )


@pytest.mark.parametrize("radius", [0.0, -0.1, 1.5])
def test_an_invalid_radius_is_refused(radius: float) -> None:
    with pytest.raises(ValueError):
        required_sample_size(radius)


def test_a_radius_of_one_is_the_loosest_valid_precision() -> None:


    assert required_sample_size(1.0) == math.ceil(math.log(2 / 0.05) / 2)
    assert required_sample_size(1.0) == 2


def test_the_bound_records_the_confidence_it_was_built_at() -> None:
    assert clopper_pearson_bound(3, 100, confidence=0.99).confidence == pytest.approx(0.99)
    assert hoeffding_bound(3, 100, confidence=0.90).confidence == pytest.approx(0.90)
