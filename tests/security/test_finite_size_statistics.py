"""Direct coverage of the two public ``finite_size`` statistics helpers.

Why this file exists
--------------------
A forensic audit flagged ``observed_vs_bound_margin`` and ``prediction_interval``
as the remaining P2 test-coverage gap: both are exported in ``__all__`` and both
were entirely unexecuted. The trap is that the repository already contains tests
named ``test_prediction_interval_*`` -- but those call
``backend.security.threat_bounds.honest_prediction``, a **different**
implementation with a different signature: it takes a ``ThresholdResult``, not a
raw ``(trials, p)`` pair, and it truncates with ``int()`` rather than clamping to
``[0, trials]``. Exercising it therefore tells a reader nothing about
``finite_size.prediction_interval``.

These tests import and call the real public functions directly. Names say which
implementation is under test so they cannot be confused with the
``honest_prediction`` tests in ``test_threat_bounds.py``.

What is asserted, and why it is safe to assert
----------------------------------------------
Every expected number below was computed from the implementation (and, where the
implementation delegates to ``scipy``, checked against ``scipy`` in the test
itself rather than against a remembered constant). Nothing in the arithmetic
section changes a formula, a confidence convention, or a security interpretation.

The final section covers annotation resolution. M7.2 found that both functions
declared ``-> Dict[str, Any]`` while the module imported only ``Tuple`` from
``typing``, so ``typing.get_type_hints()`` raised for two exported symbols. M7.3
fixed the import and replaced the test that pinned the defect with one that
asserts the corrected contract.
"""

from __future__ import annotations

import pytest
from scipy import stats

from backend.security.finite_size import (
    observed_vs_bound_margin,
    prediction_interval,
)







def test_observed_vs_bound_margin_reports_rate_and_count_above_the_bound() -> None:



    result = observed_vs_bound_margin(5, 0.02, 100)

    assert result["observed_rate"] == pytest.approx(0.05)
    assert result["bound_upper"] == pytest.approx(0.02)
    assert result["margin_rate"] == pytest.approx(0.03)
    assert result["margin_count"] == pytest.approx(3.0)
    assert result["exceeds"] is True


def test_observed_vs_bound_margin_reports_a_negative_margin_below_the_bound() -> None:



    result = observed_vs_bound_margin(1, 0.02, 100)

    assert result["observed_rate"] == pytest.approx(0.01)
    assert result["margin_rate"] == pytest.approx(-0.01)
    assert result["margin_count"] == pytest.approx(-1.0)
    assert result["exceeds"] is False


def test_observed_vs_bound_margin_is_zero_and_not_exceeding_at_exact_equality() -> None:




    result = observed_vs_bound_margin(2, 0.02, 100)

    assert result["observed_rate"] == pytest.approx(0.02)
    assert result["margin_rate"] == pytest.approx(0.0)
    assert result["margin_count"] == pytest.approx(0.0)
    assert result["exceeds"] is False


def test_observed_vs_bound_margin_count_and_rate_agree_in_sign() -> None:




    for successes in (1, 2, 3, 4, 5):
        result = observed_vs_bound_margin(successes, 0.02, 100)
        assert result["margin_count"] == pytest.approx(result["margin_rate"] * 100)
        assert result["exceeds"] == (result["margin_count"] > 0)


def test_observed_vs_bound_margin_equals_the_hand_computed_difference() -> None:


    successes, bound, trials = 7, 0.0108, 500
    result = observed_vs_bound_margin(successes, bound, trials)

    assert result["observed_rate"] == pytest.approx(successes / trials)
    assert result["margin_rate"] == pytest.approx(successes / trials - bound)
    assert result["margin_count"] == pytest.approx(successes - bound * trials)







def test_observed_vs_bound_margin_with_zero_trials_is_undefined_not_zero() -> None:




    result = observed_vs_bound_margin(0, 0.02, 0)

    assert result["observed_rate"] is None
    assert result["margin_rate"] is None
    assert result["margin_count"] is None
    assert result["exceeds"] is False
    assert result["bound_upper"] == pytest.approx(0.02)
    assert "undefined" in result["note"]


def test_observed_vs_bound_margin_with_zero_successes_is_a_pure_negative_bound() -> None:


    result = observed_vs_bound_margin(0, 0.02, 100)

    assert result["observed_rate"] == pytest.approx(0.0)
    assert result["margin_rate"] == pytest.approx(-0.02)
    assert result["margin_count"] == pytest.approx(-2.0)
    assert result["exceeds"] is False


def test_observed_vs_bound_margin_at_the_maximum_rate() -> None:


    result = observed_vs_bound_margin(100, 0.02, 100)

    assert result["observed_rate"] == pytest.approx(1.0)
    assert result["margin_rate"] == pytest.approx(0.98)
    assert result["margin_count"] == pytest.approx(98.0)
    assert result["exceeds"] is True


def test_observed_vs_bound_margin_with_a_bound_of_zero_exceeds_on_any_mismatch() -> None:


    exceeds = observed_vs_bound_margin(1, 0.0, 100)
    at_bound = observed_vs_bound_margin(0, 0.0, 100)

    assert exceeds["margin_rate"] == pytest.approx(0.01)
    assert exceeds["exceeds"] is True
    assert at_bound["margin_rate"] == pytest.approx(0.0)
    assert at_bound["exceeds"] is False


def test_observed_vs_bound_margin_with_a_bound_of_one_never_exceeds() -> None:


    result = observed_vs_bound_margin(100, 1.0, 100)

    assert result["margin_rate"] == pytest.approx(0.0)
    assert result["exceeds"] is False


def test_observed_vs_bound_margin_does_not_claim_to_be_a_forgery_bound() -> None:



    result = observed_vs_bound_margin(5, 0.02, 100)

    assert "not a forgery bound" in result["note"]
    assert "evidence of inconsistency" in result["note"]







@pytest.mark.parametrize(
    "successes,trials",
    [(-1, 100), (101, 100), (5, -1)],
)
def test_observed_vs_bound_margin_refuses_impossible_counts(
    successes: int, trials: int
) -> None:

    with pytest.raises(ValueError):
        observed_vs_bound_margin(successes, 0.02, trials)


def test_observed_vs_bound_margin_negative_successes_names_the_offending_field() -> None:


    with pytest.raises(ValueError, match="successes must be non-negative"):
        observed_vs_bound_margin(-1, 0.02, 100)


def test_observed_vs_bound_margin_more_successes_than_trials_names_both() -> None:
    with pytest.raises(ValueError, match=r"successes \(101\) cannot exceed trials \(100\)"):
        observed_vs_bound_margin(101, 0.02, 100)







def test_prediction_interval_matches_the_scipy_binomial_quantiles() -> None:



    trials, p, confidence = 100, 0.02, 0.95
    alpha = 1.0 - confidence
    result = prediction_interval(trials, p, confidence=confidence)

    assert result["sample_size"] == trials
    assert result["p"] == pytest.approx(p)
    assert result["confidence"] == pytest.approx(confidence)
    assert result["predicted_min"] == int(stats.binom.ppf(alpha / 2.0, trials, p))
    assert result["predicted_max"] == int(stats.binom.ppf(1.0 - alpha / 2.0, trials, p))


def test_prediction_interval_matches_the_thresholds_reference_configuration() -> None:





    result = prediction_interval(500, 0.0108, confidence=0.95)

    assert result["predicted_max"] == 10
    assert result["predicted_min"] == 1


def test_prediction_interval_brackets_the_mean() -> None:


    trials, p = 100, 0.02
    result = prediction_interval(trials, p)

    assert result["predicted_min"] <= p * trials <= result["predicted_max"]


def test_prediction_interval_min_never_exceeds_max() -> None:




    for trials in (1, 10, 100, 500, 1000):
        for p in (0.0, 0.001, 0.02, 0.5, 0.98, 0.999, 1.0):
            result = prediction_interval(trials, p)
            assert result["predicted_min"] <= result["predicted_max"]


def test_prediction_interval_stays_within_the_sample_range() -> None:
















    for trials in (0, 1, 10, 100, 500):
        for p in (0.0, 0.02, 0.5, 0.98, 1.0):
            result = prediction_interval(trials, p)
            assert 0 <= result["predicted_min"] <= trials
            assert 0 <= result["predicted_max"] <= trials


def test_prediction_interval_widens_as_confidence_rises() -> None:


    loose = prediction_interval(500, 0.02, confidence=0.80)
    tight = prediction_interval(500, 0.02, confidence=0.99)

    loose_width = loose["predicted_max"] - loose["predicted_min"]
    tight_width = tight["predicted_max"] - tight["predicted_min"]
    assert tight_width >= loose_width


def test_prediction_interval_is_not_a_confidence_interval_for_p() -> None:



    result = prediction_interval(100, 0.02)

    assert "prediction interval for a future observation" in result["note"]
    assert "not a confidence interval for the parameter p" in result["note"]







def test_prediction_interval_with_zero_trials_is_the_degenerate_zero_interval() -> None:


    result = prediction_interval(0, 0.02)

    assert result["sample_size"] == 0
    assert result["predicted_min"] == 0
    assert result["predicted_max"] == 0


def test_prediction_interval_at_p_zero_is_the_degenerate_zero_interval() -> None:


    result = prediction_interval(100, 0.0)

    assert result["p"] == pytest.approx(0.0)
    assert result["predicted_min"] == 0
    assert result["predicted_max"] == 0


def test_prediction_interval_at_p_one_is_the_degenerate_full_interval() -> None:



    result = prediction_interval(100, 1.0)

    assert result["p"] == pytest.approx(1.0)
    assert result["predicted_min"] == 100
    assert result["predicted_max"] == 100


def test_prediction_interval_with_a_single_trial() -> None:


    result = prediction_interval(1, 0.5)

    assert result["predicted_min"] == 0
    assert result["predicted_max"] == 1


def test_prediction_interval_narrows_as_the_sample_grows_at_fixed_rate() -> None:




    small = prediction_interval(100, 0.02)
    large = prediction_interval(10_000, 0.02)

    small_span = (small["predicted_max"] - small["predicted_min"]) / 100
    large_span = (large["predicted_max"] - large["predicted_min"]) / 10_000
    assert large_span < small_span


def test_prediction_interval_at_the_lowest_valid_confidence() -> None:



    result = prediction_interval(100, 0.02, confidence=1e-9)

    assert result["predicted_min"] <= result["predicted_max"]
    assert 0 <= result["predicted_min"] <= 100







def test_prediction_interval_refuses_negative_trials() -> None:
    with pytest.raises(ValueError, match="trials must be non-negative"):
        prediction_interval(-1, 0.02)


@pytest.mark.parametrize("p", [-0.1, 1.1, -1.0, 2.0])
def test_prediction_interval_refuses_an_out_of_range_rate(p: float) -> None:


    with pytest.raises(ValueError, match=r"p must lie in \[0, 1\]"):
        prediction_interval(100, p)


@pytest.mark.parametrize("confidence", [0.0, 1.0, -0.5, 1.5])
def test_prediction_interval_refuses_an_out_of_range_confidence(
    confidence: float,
) -> None:



    with pytest.raises(ValueError, match=r"confidence must lie in \(0, 1\)"):
        prediction_interval(100, 0.02, confidence=confidence)


def test_prediction_interval_refuses_invalid_input_before_touching_scipy() -> None:



    with pytest.raises(ValueError):
        prediction_interval(-5, 5.0, confidence=42.0)







def test_both_statistics_helpers_are_deterministic() -> None:


    for _ in range(3):
        assert observed_vs_bound_margin(5, 0.02, 100) == observed_vs_bound_margin(
            5, 0.02, 100
        )
        assert prediction_interval(500, 0.0108) == prediction_interval(500, 0.0108)


def test_both_statistics_helpers_return_fresh_objects() -> None:


    first = observed_vs_bound_margin(5, 0.02, 100)
    first["margin_rate"] = -999.0
    second = observed_vs_bound_margin(5, 0.02, 100)
    assert second["margin_rate"] == pytest.approx(0.03)







@pytest.mark.parametrize(
    "function_name",
    ["observed_vs_bound_margin", "prediction_interval"],
)
def test_public_statistics_annotations_resolve_to_dict_str_any(
    function_name: str,
) -> None:
    """Both public functions must expose an introspectable ``Dict[str, Any]``.

    M7.2 found that these two declared ``-> Dict[str, Any]`` while the module
    imported only ``Tuple`` from ``typing``. Under ``from __future__ import
    annotations`` that is invisible at call time -- the annotations are never
    evaluated, so the functions worked and the module imported cleanly -- but
    ``typing.get_type_hints()`` evaluates them and raised
    ``NameError: name 'Dict' is not defined``. Real introspection therefore
    failed for two exported symbols.

    This asserts the *fixed* state. Three things are checked, in increasing
    strength:

    1. the hints resolve at all (the regression this pins),
    2. the return annotation is specifically ``Dict[str, Any]`` -- not merely
       "something", and not a bare ``dict``, since the declared public contract
       is the parameterised form, and
    3. the parameter annotations are unchanged, so the fix really did add the
       missing names rather than rewrite the signatures.

    Note this is deliberately *not* written as ``assert no exception``: a test
    that only proves "no NameError" would pass if the annotation were silently
    changed to something wrong.
    """
    import typing

    from backend.security.finite_size import (
        observed_vs_bound_margin,
        prediction_interval,
    )

    expected_parameters = {
        "observed_vs_bound_margin": {
            "observed_successes": int,
            "bound_upper": float,
            "trials": int,
        },
        "prediction_interval": {
            "trials": int,
            "p": float,
            "confidence": float,
        },
    }

    function = {
        "observed_vs_bound_margin": observed_vs_bound_margin,
        "prediction_interval": prediction_interval,
    }[function_name]

    hints = typing.get_type_hints(function)



    assert hints["return"] == typing.Dict[str, typing.Any]
    assert typing.get_origin(hints["return"]) is dict
    assert typing.get_args(hints["return"]) == (str, typing.Any)



    for parameter, expected in expected_parameters[function_name].items():
        assert hints[parameter] is expected


def test_every_callable_exported_by_finite_size_has_resolvable_annotations() -> None:
    """No public function in the module may carry an unresolvable annotation.

    The M7.2 defect was a missing import that only showed up on two of the seven
    exported callables. Checking all of them -- rather than the two that happened
    to break -- is what keeps a future annotation from reintroducing the same
    class of failure somewhere else in the module.
    """
    import typing

    from backend.security import finite_size

    unresolvable: list[str] = []
    checked = 0
    for name in finite_size.__all__:
        member = getattr(finite_size, name)
        if not callable(member):
            continue
        checked += 1
        try:
            typing.get_type_hints(member)
        except Exception as exc:  # pragma: no cover - the failure this guards
            unresolvable.append(f"{name}: {type(exc).__name__}: {exc}")


    assert checked == 7, f"expected 7 public callables, inspected {checked}"
    assert unresolvable == [], f"unresolvable annotations: {unresolvable}"
