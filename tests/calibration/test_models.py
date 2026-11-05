"""The typed records of the calibration layer.

Two things are being pinned here.

The first is validation: every invariant the layer relies on is checked at the
boundary, so a malformed record cannot travel silently into a threshold.

The second is the *terminology separation* the milestone insists on. A
confidence interval, a classification threshold, an empirical acceptance rate
and a cryptographic security bound are four different objects. In this module
they are four different types, and the tests below assert that none of them
carries a field or a label that would let it masquerade as another.
"""

from __future__ import annotations

import json

import pytest

from backend.calibration.models import (
    STATISTIC_MISMATCH_RATE,
    SUPPORTED_STATISTICS,
    CalibrationConfig,
    CalibrationObservation,
    ConfidenceInterval,
    DatasetRole,
    HomogeneityDiagnostic,
    ThresholdConfig,
    ThresholdResult,
    VerificationDecision,
)







def test_exactly_one_statistic_may_be_tested() -> None:
    assert SUPPORTED_STATISTICS == (STATISTIC_MISMATCH_RATE,)
    assert STATISTIC_MISMATCH_RATE == "mismatch_rate"







def test_a_confidence_interval_reports_its_width_and_construction() -> None:
    interval = ConfidenceInterval(
        successes=3,
        trials=100,
        lower=0.006,
        upper=0.086,
        confidence=0.95,
        method="clopper-pearson",
        one_sided=False,
    )
    assert interval.width == pytest.approx(0.080)
    payload = interval.to_dict()
    assert payload["method"] == "clopper-pearson"
    assert payload["width"] == pytest.approx(0.080)


def test_a_confidence_interval_has_no_decision_field() -> None:


    names = set(ConfidenceInterval.__dataclass_fields__)
    assert "rejected" not in names
    assert "critical_count" not in names
    assert "threshold_rate" not in names







def _config(**overrides) -> CalibrationConfig:
    base = dict(
        config_id="models-test",
        protocol_version="RQDS-TP-1.0",
        noise_type="depolarizing",
        noise_strength=0.02,
        state_count=200,
        measurement_mode="sampled",
        shot_count=1,
        statistic=STATISTIC_MISMATCH_RATE,
        confidence=0.95,
        seed_start=0,
        session_count=10,
        dataset_role=DatasetRole.CALIBRATION,
    )
    base.update(overrides)
    return CalibrationConfig(**base)


def test_a_valid_configuration_validates() -> None:
    config = _config().validate()
    assert config.seed_range() == (0, 9)


def test_the_seed_range_is_inclusive_of_both_ends() -> None:
    assert _config(seed_start=100, session_count=1).seed_range() == (100, 100)
    assert _config(seed_start=0, session_count=5).seed_range() == (0, 4)


@pytest.mark.parametrize("statistic", ["fidelity", "disturbance_rate", ""])
def test_an_unsupported_statistic_is_refused(statistic: str) -> None:
    with pytest.raises(ValueError, match="statistic must be one of"):
        _config(statistic=statistic).validate()


@pytest.mark.parametrize("confidence", [0.0, 1.0, -0.1, 1.5])
def test_an_invalid_confidence_is_refused(confidence: float) -> None:
    with pytest.raises(ValueError, match="confidence"):
        _config(confidence=confidence).validate()


@pytest.mark.parametrize("session_count", [0, -1])
def test_a_non_positive_session_count_is_refused(session_count: int) -> None:
    with pytest.raises(ValueError, match="session_count"):
        _config(session_count=session_count).validate()


@pytest.mark.parametrize("state_count", [0, -5])
def test_a_non_positive_state_count_is_refused(state_count: int) -> None:
    with pytest.raises(ValueError, match="state_count"):
        _config(state_count=state_count).validate()


def test_a_negative_seed_start_is_refused() -> None:
    with pytest.raises(ValueError, match="seed_start"):
        _config(seed_start=-1).validate()


@pytest.mark.parametrize(
    "role",
    [DatasetRole.VALIDATION, DatasetRole.FINAL_EVALUATION],
)
def test_a_calibration_config_must_carry_the_calibration_role(role) -> None:


    with pytest.raises(ValueError, match="CALIBRATION"):
        _config(dataset_role=role).validate()


def test_the_fingerprint_is_stable_and_sensitive() -> None:
    a = _config().fingerprint()
    b = _config().fingerprint()
    c = _config(noise_strength=0.021).fingerprint()
    assert a == b
    assert a != c
    assert len(a) == 64


def test_the_config_round_trips_through_json() -> None:
    config = _config()
    payload = json.loads(json.dumps(config.to_dict()))
    assert payload["dataset_role"] == "CALIBRATION"
    assert payload["statistic"] == STATISTIC_MISMATCH_RATE


def test_the_config_carries_no_derived_quantity() -> None:


    names = set(CalibrationConfig.__dataclass_fields__)
    for derived in ("pooled_rate", "mismatch_rate", "threshold", "critical_count"):
        assert derived not in names







def _observation(**overrides) -> CalibrationObservation:
    base = dict(
        experiment_id="cal-000",
        random_seed=0,
        state_count=200,
        n_valid=200,
        n_mismatch=4,
        mismatch_rate=0.02,
        dataset_role=DatasetRole.CALIBRATION,
    )
    base.update(overrides)
    return CalibrationObservation(**base)


def test_a_valid_observation_validates() -> None:
    assert _observation().validate().n_mismatch == 4


def test_the_mismatch_rate_must_equal_the_count_over_the_sample_size() -> None:
    with pytest.raises(ValueError, match="mismatch_rate must equal"):
        _observation(mismatch_rate=0.5).validate()


def test_a_rounded_mismatch_rate_is_refused() -> None:


    with pytest.raises(ValueError, match="mismatch_rate must equal"):
        _observation(n_valid=3, n_mismatch=1, mismatch_rate=0.33).validate()


def test_an_exact_third_is_accepted() -> None:
    observation = _observation(n_valid=3, n_mismatch=1, mismatch_rate=1 / 3)
    assert observation.validate().mismatch_rate == 1 / 3


@pytest.mark.parametrize(
    "n_valid,n_mismatch",
    [(-1, 0), (200, -1), (200, 201)],
)
def test_impossible_counts_are_refused(n_valid: int, n_mismatch: int) -> None:
    with pytest.raises(ValueError):
        _observation(
            n_valid=n_valid,
            n_mismatch=n_mismatch,
            mismatch_rate=None if n_valid <= 0 else n_mismatch / n_valid,
        ).validate()


def test_an_observation_with_no_usable_states_needs_no_rate() -> None:
    observation = _observation(n_valid=0, n_mismatch=0, mismatch_rate=None)
    assert observation.validate().mismatch_rate is None


def test_a_non_calibration_observation_is_refused() -> None:
    with pytest.raises(ValueError, match="CALIBRATION"):
        _observation(dataset_role=DatasetRole.FINAL_EVALUATION).validate()


def test_an_observation_cannot_carry_an_attack_label() -> None:



    names = set(CalibrationObservation.__dataclass_fields__)
    for forbidden in (
        "attack",
        "attack_type",
        "attack_fraction",
        "is_malicious",
        "malicious",
        "ground_truth",
        "label",
        "forgery",
    ):
        assert forbidden not in names, forbidden


def test_an_observation_round_trips_through_json() -> None:
    payload = json.loads(json.dumps(_observation().to_dict()))
    assert payload["dataset_role"] == "CALIBRATION"
    assert payload["n_mismatch"] == 4







def test_the_budget_splits_into_two_halves_that_sum_to_alpha() -> None:
    config = ThresholdConfig(alpha=0.05, calibration_alpha_fraction=0.3)
    assert config.calibration_alpha == pytest.approx(0.015)
    assert config.evaluation_alpha == pytest.approx(0.035)
    assert config.calibration_alpha + config.evaluation_alpha == pytest.approx(0.05)


@pytest.mark.parametrize("alpha", [0.0, 1.0, -0.1, 2.0])
def test_an_invalid_budget_is_refused(alpha: float) -> None:
    with pytest.raises(ValueError, match="alpha"):
        ThresholdConfig(alpha=alpha).validate()


@pytest.mark.parametrize("fraction", [0.0, 1.0, -0.2, 1.2])
def test_an_invalid_split_is_refused(fraction: float) -> None:
    with pytest.raises(ValueError, match="calibration_alpha_fraction"):
        ThresholdConfig(calibration_alpha_fraction=fraction).validate()


def test_the_threshold_config_reports_its_method() -> None:
    payload = ThresholdConfig().to_dict()
    assert payload["method"] == "honest-null-quantile-with-upper-confidence-bound"
    assert payload["calibration_alpha"] == pytest.approx(0.025)







def _threshold(**overrides) -> ThresholdResult:
    base = dict(
        state_count=200,
        p_upper=0.02,
        critical_count=10,
        threshold_rate=0.05,
        config=ThresholdConfig(),
        calibration_fingerprint="0" * 64,
        calibration_session_count=10,
        calibration_total_valid=2000,
        calibration_total_mismatch=40,
        calibration_pooled_rate=0.02,
        calibration_role=DatasetRole.CALIBRATION,
    )
    base.update(overrides)
    return ThresholdResult(**base)


def test_the_rule_rejects_strictly_above_the_critical_count() -> None:
    threshold = _threshold()
    assert threshold.rejects(10, 200) is False
    assert threshold.rejects(11, 200) is True


def test_the_rule_is_undefined_for_another_sample_size() -> None:


    with pytest.raises(ValueError, match="not defined for"):
        _threshold().rejects(0, 201)


def test_the_threshold_is_traceable_to_its_calibration() -> None:
    payload = _threshold().to_dict()
    for key in (
        "calibration_fingerprint",
        "calibration_session_count",
        "calibration_total_valid",
        "calibration_total_mismatch",
        "calibration_pooled_rate",
        "calibration_role",
        "p_upper",
        "critical_count",
        "config",
    ):
        assert key in payload
    assert payload["calibration_role"] == "CALIBRATION"


def test_the_threshold_carries_no_security_claim() -> None:

    blob = json.dumps(_threshold().to_dict()).lower()
    for word in ("secure", "security", "forgery", "information-theoretic"):
        assert word not in blob, word







def test_a_decision_records_the_evidence_it_used() -> None:
    decision = VerificationDecision(
        rejected=False,
        statistic=STATISTIC_MISMATCH_RATE,
        observed_rate=0.01,
        observed_count=2,
        sample_size=200,
        threshold_rate=0.05,
        critical_count=10,
        operating_point="m5-reference",
        explanation="within the calibrated threshold",
        decision_basis=("mismatch_rate > 10 (critical count for n=200)",),
    )
    payload = decision.to_dict()
    assert payload["observed_count"] == 2
    assert payload["sample_size"] == 200
    assert payload["diagnostics"] == {}







def test_the_homogeneity_diagnostic_reports_a_spread() -> None:
    diagnostic = HomogeneityDiagnostic(
        state_count=3,
        predicted_probabilities=(0.01, 0.01, 0.02),
        minimum=0.01,
        maximum=0.02,
        mean=0.013333333333333334,
        spread=0.01,
        homogeneous=False,
        tolerance=1e-9,
    )
    payload = diagnostic.to_dict()
    assert payload["spread"] == pytest.approx(0.01)
    assert payload["homogeneous"] is False
    assert payload["state_count"] == 3
