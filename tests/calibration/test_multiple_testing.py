"""The multiple-comparison policy.

The requirement this module enforces is negative and specific: the project must
not run several statistics each at ``alpha = 0.05`` and describe the result as a
5% error rate. The tests here pin both halves of that -- that the reference
policy really is a single test, and that a multi-test policy cannot be
constructed without naming a correction.
"""

from __future__ import annotations

import pytest

from backend.calibration.multiple_testing import (
    DIAGNOSTIC_METRICS,
    REFERENCE_PRIMARY_TEST,
    MultipleComparisonPolicy,
    MultipleTestingPolicy,
    bonferroni_alpha,
    describe_diagnostics,
    family_wise_error_rate,
    holm_bonferroni,
    reference_policy,
    reject_multiple_primary_tests,
)







def test_the_reference_policy_performs_exactly_one_test() -> None:
    policy = reference_policy()
    assert policy.policy is MultipleTestingPolicy.SINGLE_PRIMARY_WITH_DIAGNOSTICS
    assert policy.primary_test == REFERENCE_PRIMARY_TEST

    assert policy.correction is None
    assert policy.family_wise_alpha is None


def test_only_the_primary_test_is_part_of_the_decision() -> None:
    policy = reference_policy()
    assert policy.is_part_of_decision(REFERENCE_PRIMARY_TEST) is True
    for metric in policy.diagnostic_metrics:
        assert policy.is_part_of_decision(metric) is False


def test_the_primary_test_is_not_also_listed_as_a_diagnostic() -> None:
    policy = reference_policy()
    assert REFERENCE_PRIMARY_TEST not in policy.diagnostic_metrics


def test_the_diagnostic_set_covers_the_other_milestone_four_statistics() -> None:




    for expected in (

        "verification_state_disturbance_rate",
        "per_basis_mismatch_rates",
        "per_basis_disturbance_rates",

        "projective_match_probability",
        "reconstruction_fidelity",
        "minimum_fidelity",

        "measurement_counts_by_basis",
        "basis_distribution",

        "state_count_consistency",
        "transcript_validity",
        "session_consistency",
        "signer_authorization_validity",
        "verifier_authorization_validity",
    ):
        assert expected in DIAGNOSTIC_METRICS, expected


def test_the_diagnostic_set_is_non_empty_and_free_of_duplicates() -> None:
    assert DIAGNOSTIC_METRICS
    assert len(set(DIAGNOSTIC_METRICS)) == len(DIAGNOSTIC_METRICS)


def test_describe_diagnostics_marks_everything_as_reported_not_adjudicated() -> None:
    policy = reference_policy()
    described = describe_diagnostics(
        {name: "observed" for name in policy.diagnostic_metrics}, policy
    )
    assert described
    assert set(described) == set(policy.diagnostic_metrics)
    for name, entry in described.items():


        assert entry["part_of_decision"] is False, name
        assert entry["value"] == "observed"


def test_describe_diagnostics_marks_the_primary_test_as_part_of_the_decision() -> None:



    described = describe_diagnostics({REFERENCE_PRIMARY_TEST: 7}, reference_policy())
    assert described[REFERENCE_PRIMARY_TEST]["part_of_decision"] is True







def test_a_multi_test_policy_without_a_correction_is_refused() -> None:
    with pytest.raises(ValueError):
        MultipleComparisonPolicy(
            policy=MultipleTestingPolicy.CORRECTED_FAMILY,
            primary_test="metric_a",
        ).validate()


def test_a_multi_test_policy_without_a_budget_is_refused() -> None:
    with pytest.raises(ValueError):
        MultipleComparisonPolicy(
            policy=MultipleTestingPolicy.CORRECTED_FAMILY,
            primary_test="metric_a",
            correction="holm-bonferroni",
        ).validate()


def test_a_single_test_policy_may_not_carry_a_family_budget() -> None:
    with pytest.raises(ValueError):
        MultipleComparisonPolicy(
            policy=MultipleTestingPolicy.SINGLE_PRIMARY_WITH_DIAGNOSTICS,
            primary_test="metric_a",
            family_wise_alpha=0.05,
        ).validate()


def test_a_corrected_family_policy_can_be_built() -> None:
    policy = MultipleComparisonPolicy(
        policy=MultipleTestingPolicy.CORRECTED_FAMILY,
        primary_test="metric_a",
        correction="holm-bonferroni",
        family_wise_alpha=0.05,
    ).validate()
    assert policy.family_wise_alpha == 0.05
    assert policy.correction == "holm-bonferroni"


def test_a_primary_test_cannot_also_be_a_diagnostic() -> None:


    with pytest.raises(ValueError, match="both"):
        MultipleComparisonPolicy(
            policy=MultipleTestingPolicy.SINGLE_PRIMARY_WITH_DIAGNOSTICS,
            primary_test="reconstruction_fidelity",
        ).validate()


def test_a_primary_test_outside_the_diagnostic_set_is_accepted() -> None:


    policy = reference_policy()
    assert policy.primary_test not in policy.diagnostic_metrics
    assert policy.validate() is policy


def test_an_unnamed_primary_test_is_refused() -> None:
    with pytest.raises(ValueError, match="primary_test"):
        MultipleComparisonPolicy(
            policy=MultipleTestingPolicy.SINGLE_PRIMARY_WITH_DIAGNOSTICS,
            primary_test="",
        ).validate()







def test_family_wise_error_rate_matches_the_independence_formula() -> None:
    assert family_wise_error_rate(0.05, 10) == pytest.approx(
        1.0 - 0.95**10, abs=1e-15
    )
    assert family_wise_error_rate(0.05, 10) == pytest.approx(0.4013, abs=5e-5)


def test_family_wise_error_rate_grows_with_the_number_of_tests() -> None:
    rates = [family_wise_error_rate(0.05, k) for k in (1, 2, 5, 10, 20)]
    assert rates == sorted(rates)
    assert family_wise_error_rate(0.05, 1) == pytest.approx(0.05, abs=1e-15)


def test_bonferroni_alpha_divides_the_budget() -> None:
    assert bonferroni_alpha(0.05, 10) == pytest.approx(0.005, abs=1e-15)


@pytest.mark.parametrize("alpha", [0.0, 1.0, -0.1, 1.5])
def test_invalid_alpha_is_refused(alpha: float) -> None:
    with pytest.raises(ValueError):
        family_wise_error_rate(alpha, 3)
    with pytest.raises(ValueError):
        bonferroni_alpha(alpha, 3)


@pytest.mark.parametrize("tests", [0, -1, True, 1.5])
def test_invalid_test_counts_are_refused(tests) -> None:
    with pytest.raises(ValueError):
        bonferroni_alpha(0.05, tests)
    with pytest.raises(ValueError):
        family_wise_error_rate(0.05, tests)







def test_holm_bonferroni_rejects_the_smallest_p_values_first() -> None:
    decisions = holm_bonferroni([0.001, 0.02, 0.6], 0.05)
    assert decisions == (True, True, False)


def test_holm_bonferroni_stops_at_the_first_failure() -> None:


    decisions = holm_bonferroni([0.03, 0.04], 0.05)
    assert decisions == (False, False)


def test_holm_bonferroni_on_an_empty_family_returns_nothing() -> None:
    assert holm_bonferroni([], 0.05) == ()


def test_holm_bonferroni_is_less_conservative_than_bonferroni() -> None:



    values = [0.01, 0.03, 0.9]
    holm = holm_bonferroni(values, 0.05)
    bonferroni = tuple(value <= bonferroni_alpha(0.05, 3) for value in values)
    assert sum(holm) >= sum(bonferroni)


@pytest.mark.parametrize("bad", [-0.1, 1.1])
def test_holm_bonferroni_refuses_invalid_p_values(bad: float) -> None:
    with pytest.raises(ValueError):
        holm_bonferroni([0.5, bad], 0.05)







def test_a_single_primary_test_is_accepted() -> None:
    reject_multiple_primary_tests([REFERENCE_PRIMARY_TEST])


def test_declaring_several_primary_tests_is_refused() -> None:
    with pytest.raises(ValueError, match="one primary"):
        reject_multiple_primary_tests(["metric_a", "metric_b"])


def test_declaring_no_primary_test_is_refused() -> None:
    with pytest.raises(ValueError):
        reject_multiple_primary_tests([])
