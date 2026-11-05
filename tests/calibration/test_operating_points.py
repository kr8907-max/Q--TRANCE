"""The single reference operating point.

The operating point is the one place where a threshold, the conditions it
belongs to and the honest false-rejection rate it actually achieved are bundled
together. These tests pin three properties the milestone requires of it:

* it is *derived*, not configured -- every field is read from the calibration
  record, so it cannot describe conditions its threshold was not fitted under;
* the false-rejection rate it reports is the *observed* one on the calibration
  data, and is labelled as fitted rather than independent;
* no claim of optimality is made anywhere, because no optimisation was done.
"""

from __future__ import annotations

import pytest

from backend.calibration.models import (
    STATISTIC_MISMATCH_RATE,
    CalibrationConfig,
    CalibrationObservation,
    CalibrationResult,
    DatasetRole,
    OperatingPoint,
    ThresholdConfig,
)
from backend.calibration.operating_points import (
    REFERENCE_ALPHA,
    REFERENCE_OPERATING_POINT_NAME,
    REFERENCE_THRESHOLD_CONFIG,
    build_operating_point,
    build_reference_operating_point,
    describe_operating_point,
    evaluate_operating_point,
    observed_rejection_rate,
)
from backend.calibration.baseline import estimate_baseline







def _config(**overrides) -> CalibrationConfig:
    base = dict(
        config_id="op-test",
        protocol_version="RQDS-TP-1.0",
        noise_type="depolarizing",
        noise_strength=0.02,
        state_count=200,
        measurement_mode="sampled",
        shot_count=1,
        statistic=STATISTIC_MISMATCH_RATE,
        confidence=0.95,
        seed_start=1000,
        session_count=24,
        dataset_role=DatasetRole.CALIBRATION,
    )
    base.update(overrides)
    return CalibrationConfig(**base).validate()


def _observations(config: CalibrationConfig, *, n_mismatch: int = 2, q: float = 0.99):
    n_valid = config.state_count
    return tuple(
        CalibrationObservation(
            experiment_id=f"cal-{index:03d}",
            random_seed=config.seed_start + index,
            state_count=config.state_count,
            n_valid=n_valid,
            n_mismatch=n_mismatch,
            mismatch_rate=n_mismatch / n_valid,
            dataset_role=DatasetRole.CALIBRATION,
            analytic_match_probabilities=(q,) * config.state_count,
        )
        for index in range(config.session_count)
    )


def _calibration(**overrides) -> CalibrationResult:
    config = _config(**overrides)
    return estimate_baseline(config, _observations(config))







def test_no_sessions_is_reported_as_unknown_not_as_zero() -> None:


    calibration = _calibration()
    point = build_reference_operating_point(calibration)
    assert observed_rejection_rate(point.threshold, (), calibration.config.state_count) is None


def test_a_session_above_the_critical_count_is_rejected() -> None:
    calibration = _calibration()
    point = build_reference_operating_point(calibration)
    threshold = point.threshold
    size = threshold.state_count

    assert (
        observed_rejection_rate(threshold, (threshold.critical_count,), size) == 0.0
    )
    assert (
        observed_rejection_rate(threshold, (threshold.critical_count + 1,), size) == 1.0
    )


def test_observed_rejection_rate_is_a_fraction_of_sessions() -> None:
    calibration = _calibration()
    threshold = build_reference_operating_point(calibration).threshold
    size = threshold.state_count
    counts = (0, 0, threshold.critical_count + 1, threshold.critical_count + 5)
    assert observed_rejection_rate(threshold, counts, size) == pytest.approx(0.5)







def test_the_operating_point_reads_its_conditions_from_the_calibration() -> None:
    calibration = _calibration(noise_type="depolarizing", noise_strength=0.03)
    point = build_reference_operating_point(calibration)

    assert point.protocol_version == calibration.config.protocol_version
    assert point.noise_type == calibration.config.noise_type
    assert point.noise_strength == calibration.config.noise_strength
    assert point.state_count == calibration.config.state_count
    assert point.measurement_mode == calibration.config.measurement_mode
    assert point.shot_count == calibration.config.shot_count


def test_the_operating_point_records_the_calibration_seed_range() -> None:
    calibration = _calibration(seed_start=500, session_count=10)
    point = build_reference_operating_point(calibration)
    assert point.calibration_seed_start == 500
    assert point.calibration_seed_end == 509


def test_the_operating_point_carries_the_threshold_it_derived() -> None:
    calibration = _calibration()
    point = build_reference_operating_point(calibration)
    threshold = point.threshold

    assert threshold.calibration_fingerprint == calibration.config.fingerprint()
    assert threshold.calibration_session_count == calibration.session_count
    assert threshold.calibration_total_valid == calibration.total_valid
    assert threshold.calibration_total_mismatch == calibration.total_mismatch
    assert threshold.calibration_pooled_rate == calibration.pooled_rate
    assert threshold.calibration_role is DatasetRole.CALIBRATION


def test_the_operating_point_may_be_derived_for_another_sample_size() -> None:



    calibration = _calibration()
    small = build_operating_point(calibration, state_count=50)
    large = build_operating_point(calibration, state_count=500)
    assert small.threshold.state_count == 50
    assert large.threshold.state_count == 500
    assert large.threshold.critical_count > small.threshold.critical_count


def test_an_operating_point_cannot_be_built_from_a_non_calibration_dataset() -> None:



    config = _config()
    rogue = CalibrationConfig(
        **{**config.to_dict(), "dataset_role": DatasetRole.VALIDATION}
    )


    observations = _observations(config)
    result = CalibrationResult(
        config=rogue,
        observations=observations,
        total_valid=sum(o.n_valid for o in observations),
        total_mismatch=sum(o.n_mismatch for o in observations),
        pooled_rate=0.01,
        interval=None,
        upper_bound=None,
        per_session_rates=tuple(o.mismatch_rate for o in observations),
        homogeneity=estimate_baseline(config, observations).homogeneity,
    )
    with pytest.raises(ValueError, match="calibration-role"):
        build_operating_point(result)


def test_the_observed_calibration_rate_is_labelled_as_fitted() -> None:



    point = build_reference_operating_point(_calibration())
    assert any("fitted" in note for note in point.notes)


def test_an_inhomogeneous_null_adds_a_note_about_the_binomial_approximation() -> None:
    config = _config(noise_type="bit_flip", state_count=200)



    observations = tuple(
        CalibrationObservation(
            experiment_id=f"cal-{index}",
            random_seed=config.seed_start + index,
            state_count=config.state_count,
            n_valid=config.state_count,
            n_mismatch=2,
            mismatch_rate=2 / config.state_count,
            dataset_role=DatasetRole.CALIBRATION,
            analytic_match_probabilities=tuple(
                [0.99] * (config.state_count // 2)
                + [0.90] * (config.state_count - config.state_count // 2)
            ),
        )
        for index in range(config.session_count)
    )
    result = estimate_baseline(config, observations)
    assert result.homogeneity.homogeneous is False
    point = build_reference_operating_point(result)
    assert any("approximation" in note for note in point.notes)







def test_the_reference_point_uses_the_documented_name_and_budget() -> None:
    point = build_reference_operating_point(_calibration())
    assert point.name == REFERENCE_OPERATING_POINT_NAME
    assert point.threshold.config.alpha == REFERENCE_ALPHA
    assert point.threshold.config == REFERENCE_THRESHOLD_CONFIG


def test_the_reference_budget_is_split_evenly_by_default() -> None:
    assert REFERENCE_THRESHOLD_CONFIG.calibration_alpha_fraction == 0.5
    assert REFERENCE_THRESHOLD_CONFIG.calibration_alpha == pytest.approx(
        REFERENCE_ALPHA / 2
    )
    assert REFERENCE_THRESHOLD_CONFIG.evaluation_alpha == pytest.approx(
        REFERENCE_ALPHA / 2
    )


def test_no_claim_of_optimality_is_made() -> None:


    point = build_reference_operating_point(_calibration())
    blob = repr(point.to_dict()).lower() + " ".join(point.notes).lower()
    assert "optimal" not in blob
    assert "optimum" not in blob
    assert "best" not in blob


def test_the_operating_point_is_json_serializable() -> None:
    import json

    point = build_reference_operating_point(_calibration())
    payload = json.dumps(point.to_dict())
    assert json.loads(payload)["name"] == REFERENCE_OPERATING_POINT_NAME







def test_describe_operating_point_exposes_the_traceable_fields() -> None:
    point = build_reference_operating_point(_calibration())
    described = describe_operating_point(point)
    for key in (
        "name",
        "statistic",
        "state_count",
        "measurement_mode",
        "shot_count",
        "honest_channel",
        "threshold_rate",
        "critical_count",
        "p_upper",
        "alpha",
        "calibration_sessions",
        "calibration_seed_range",
        "observed_calibration_frr",
    ):
        assert key in described
    assert described["statistic"] == STATISTIC_MISMATCH_RATE
    assert described["alpha"] == REFERENCE_ALPHA
    assert described["calibration_seed_range"] == [
        point.calibration_seed_start,
        point.calibration_seed_end,
    ]


def test_evaluate_operating_point_returns_counts_not_a_verdict() -> None:
    point = build_reference_operating_point(_calibration())
    size = point.threshold.state_count
    sessions = [
        (0, size),
        (point.threshold.critical_count, size),
        (point.threshold.critical_count + 1, size),
    ]
    summary = evaluate_operating_point(point, sessions)
    assert summary["sessions"] == 3
    assert summary["rejected"] == 1
    assert summary["rejection_rate"] == pytest.approx(1 / 3)
    assert summary["operating_point"] == REFERENCE_OPERATING_POINT_NAME


def test_evaluate_operating_point_on_no_sessions_reports_none() -> None:
    point = build_reference_operating_point(_calibration())
    summary = evaluate_operating_point(point, [])
    assert summary["rejected"] == 0
    assert summary["rejection_rate"] is None







def test_decide_rejects_only_above_the_critical_count() -> None:
    point = build_reference_operating_point(_calibration())
    size = point.threshold.state_count
    critical = point.threshold.critical_count

    at = point.decide(n_mismatch=critical, n_valid=size)
    above = point.decide(n_mismatch=critical + 1, n_valid=size)
    assert at.rejected is False
    assert above.rejected is True


def test_decide_explains_which_way_the_decision_went() -> None:
    point = build_reference_operating_point(_calibration())
    size = point.threshold.state_count
    accepted = point.decide(n_mismatch=0, n_valid=size)
    rejected = point.decide(
        n_mismatch=point.threshold.critical_count + 1, n_valid=size
    )
    assert "within" in accepted.explanation
    assert "exceeds" in rejected.explanation


def test_decide_records_that_only_one_statistic_moved_the_decision() -> None:
    point = build_reference_operating_point(_calibration())
    decision = point.decide(n_mismatch=0, n_valid=point.threshold.state_count)
    basis = " ".join(decision.decision_basis)
    assert STATISTIC_MISMATCH_RATE in basis
    assert "no other statistic enters the decision" in basis

    assert "not a proof of security" in basis


def test_decide_carries_diagnostics_without_letting_them_vote() -> None:
    point = build_reference_operating_point(_calibration())
    size = point.threshold.state_count
    diagnostics = {"reconstruction_fidelity": 0.999}
    decision = point.decide(n_mismatch=0, n_valid=size, diagnostics=diagnostics)
    assert decision.diagnostics == diagnostics

    other = point.decide(
        n_mismatch=0, n_valid=size, diagnostics={"reconstruction_fidelity": 0.0}
    )
    assert other.rejected == decision.rejected


def test_decide_is_undefined_for_a_different_sample_size() -> None:
    point = build_reference_operating_point(_calibration())
    with pytest.raises(ValueError, match="not defined for"):
        point.decide(n_mismatch=0, n_valid=point.threshold.state_count + 1)


def test_the_statistic_property_is_the_single_primary_statistic() -> None:
    point = build_reference_operating_point(_calibration())
    assert point.statistic == STATISTIC_MISMATCH_RATE


def test_operating_point_is_frozen() -> None:
    point = build_reference_operating_point(_calibration())
    assert isinstance(point, OperatingPoint)
    with pytest.raises(Exception):
        point.name = "renamed"  # type: ignore[misc]


def test_an_explicit_threshold_config_is_honoured() -> None:
    calibration = _calibration()
    config = ThresholdConfig(alpha=0.01, calibration_alpha_fraction=0.5)
    point = build_operating_point(calibration, threshold_config=config)
    assert point.threshold.config.alpha == 0.01
    assert point.threshold.config is config


def test_a_smaller_error_budget_gives_a_stricter_threshold() -> None:





    calibration = _calibration()
    alphas = (0.01, 0.02, 0.05, 0.10, 0.20)
    counts = [
        build_operating_point(
            calibration, threshold_config=ThresholdConfig(alpha=alpha)
        ).threshold.critical_count
        for alpha in alphas
    ]
    assert counts == sorted(counts, reverse=True), list(zip(alphas, counts))
    assert counts[0] > counts[-1]
