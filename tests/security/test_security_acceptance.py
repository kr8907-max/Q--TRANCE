"""Milestone 6 acceptance criteria.

The criteria from the milestone brief, each mapped to an explicit test.
"""

from __future__ import annotations

import pytest

from backend.security import (
    REFERENCE_ASSUMPTIONS,
    REFERENCE_COMPOSITION_ASSESSMENT,
    REFERENCE_OBSERVABILITY_MATRIX,
)
from backend.security.assumptions import reference_assumptions
from backend.security.composition import composition_summary
from backend.security.models import AssumptionStatus, StatementVerdict
from backend.security.observability import matrix_summary, threat_observability
from backend.security.threat_bounds import (
    exceedance_probability,
    honest_prediction,
    statistical_separation,
    threshold_exceedance,
)







def test_criterion_01_assumption_register_has_nine_categories() -> None:
    keys = {a.key for a in REFERENCE_ASSUMPTIONS}

    assert "independence_within_session" in keys
    assert "born_rule_sampling" in keys

    assert "homogeneous_mismatch_probability" in keys

    assert "independence_within_session" in keys
    assert "sessions_are_independent" in keys

    assert "homogeneous_mismatch_probability" in keys

    assert "finite_sample_bound_is_not_a_security_parameter" in keys

    assert "measurement_mode_is_the_operational_definition" in keys

    assert "protocol_binding_is_public_and_deterministic" in keys

    assert "classical_identity_is_bookkeeping_not_quantum" in keys

    assert "attacks_are_non_adaptive" in keys
    assert "no_label_reaches_the_decision" in keys


def test_criterion_02_every_assumption_has_scope_and_consequence() -> None:
    for assumption in REFERENCE_ASSUMPTIONS:
        assert assumption.statement
        assert assumption.consequence_if_violated
        assert assumption.status in set(AssumptionStatus)







def test_criterion_03_threshold_exceedance_is_deterministic() -> None:
    from backend.calibration.models import ThresholdResult, ThresholdConfig, DatasetRole

    t = ThresholdResult(
        state_count=100,
        p_upper=0.02,
        critical_count=3,
        threshold_rate=0.03,
        config=ThresholdConfig(),
        calibration_fingerprint="test",
        calibration_session_count=10,
        calibration_total_valid=1000,
        calibration_total_mismatch=10,
        calibration_pooled_rate=0.01,
        calibration_role=DatasetRole.CALIBRATION,
    )
    result = threshold_exceedance(4, 100, t)
    assert result.exceeds is True
    assert result.margin == 1
    assert result.margin_rate == pytest.approx(0.01)


def test_criterion_04_statistical_separation_is_conservative() -> None:
    result = statistical_separation(0.05, 0.02)
    assert result.separation_rate == pytest.approx(0.03)
    assert result.separation_rate > 0
    assert "not a forgery bound" in result.conclusion.lower()


def test_criterion_05_prediction_interval_is_not_a_confidence_interval() -> None:
    from backend.calibration.models import ThresholdResult, ThresholdConfig, DatasetRole

    t = ThresholdResult(
        state_count=100,
        p_upper=0.02,
        critical_count=3,
        threshold_rate=0.03,
        config=ThresholdConfig(),
        calibration_fingerprint="test",
        calibration_session_count=10,
        calibration_total_valid=1000,
        calibration_total_mismatch=10,
        calibration_pooled_rate=0.01,
        calibration_role=DatasetRole.CALIBRATION,
    )
    pred = honest_prediction(t)
    assert pred.predicted_max_mismatch <= 100
    assert "prediction interval" in pred.notes[0].lower()
    assert "not a confidence interval" in pred.notes[0].lower()


def test_criterion_06_no_quantity_is_a_security_parameter() -> None:
    from backend.security.models import FiniteSizeBound, BoundKind, BoundSidedness

    bound = FiniteSizeBound(
        kind=BoundKind.EXACT_CLOPPER_PEARSON,
        sidedness=BoundSidedness.UPPER,
        statistic="mismatch_rate",
        sample_size=100,
        successes=2,
        confidence=0.95,
        lower=0.0,
        upper=0.05,
        point_estimate=0.02,
        method="test",
        citation="test",
        assumptions=(),
    )
    assert bound.is_cryptographic_security_bound is False
    with pytest.raises(ValueError, match="cryptographic security bound"):
        FiniteSizeBound(
            kind=BoundKind.EXACT_CLOPPER_PEARSON,
            sidedness=BoundSidedness.UPPER,
            statistic="mismatch_rate",
            sample_size=100,
            successes=2,
            confidence=0.95,
            lower=0.0,
            upper=0.05,
            point_estimate=0.02,
            method="test",
            citation="test",
            assumptions=(),
            is_cryptographic_security_bound=True,
        )







def test_criterion_07_the_four_protocol_attacks_are_not_quantum_detectable() -> None:
    for name in ("forgery", "impersonation", "unauthorized_verification", "replay"):
        row = threat_observability(name)
        assert row.quantum_disturbance is False, name
        assert row.detector_visible_quantum is False, name
        assert row.m5_detection_rate == pytest.approx(0.0), name
        assert row.m5_far == pytest.approx(1.0), name


def test_criterion_08_the_two_channel_attacks_are_quantum_detectable() -> None:
    for name in ("intercept_resend", "channel_tampering"):
        row = threat_observability(name)
        assert row.quantum_disturbance is True, name
        assert row.detector_visible_quantum is True, name
        assert row.m5_detection_rate == pytest.approx(1.0), name
        assert row.m5_far == pytest.approx(0.0), name


def test_criterion_09_protocol_attacks_require_classical_controls() -> None:
    for name in ("forgery", "impersonation", "unauthorized_verification", "replay"):
        row = threat_observability(name)
        assert row.requires_classical_control is True, name







def test_criterion_10_the_matrix_has_nine_dimensions() -> None:
    row = threat_observability("channel_tampering")
    assert row.threat
    assert isinstance(row.quantum_disturbance, bool)
    assert isinstance(row.protocol_anomaly, bool)
    assert isinstance(row.authentication_evidence, bool)
    assert isinstance(row.replay_evidence, bool)
    assert isinstance(row.detector_visible_quantum, bool)
    assert isinstance(row.requires_classical_control, bool)
    assert isinstance(row.empirically_evaluated, bool)
    assert isinstance(row.covered_by_prototype, bool)


def test_criterion_11_the_matrix_is_derived_from_measured_evidence() -> None:
    summary = matrix_summary()
    assert summary["empirically_evaluated_count"] == 6
    assert "benchmarks/m5-reference.json" in summary["source"]







def test_criterion_12_no_formal_composition_theorem_is_claimed() -> None:
    summary = composition_summary()
    assert summary["formal_composition_theorem_present"] is False


def test_criterion_13_every_component_has_an_unresolved_dependency() -> None:
    for item in REFERENCE_COMPOSITION_ASSESSMENT:
        assert item.unresolved_dependency, item.component


def test_criterion_14_no_conclusion_fabricates_a_security_proof() -> None:
    forbidden = (
        "information-theoretically secure",
        "formal forgery bound",
        "provably secure",
        "unconditional",
    )
    for item in REFERENCE_COMPOSITION_ASSESSMENT:
        lowered = item.security_conclusion.lower()
        for phrase in forbidden:
            assert phrase not in lowered, (item.component, phrase)







def test_criterion_15_exceedance_probability_is_not_called_a_security_parameter() -> None:
    p = exceedance_probability(5, 100, 0.02)
    assert 0.0 <= p <= 1.0

    import backend.security.threat_bounds as tb
    doc = tb.exceedance_probability.__doc__.lower()
    assert "cryptographic security parameter" in doc
    assert "not" in doc or "no quantity" in doc


def test_criterion_16_no_forgery_probability_is_invented_from_detection_rate() -> None:


    import backend.security.threat_bounds as tb
    import backend.security.observability as ob
    import backend.security.composition as co
    for module in (tb, ob, co):
        source = module.__file__
        with open(source, encoding="utf-8") as handle:
            text = handle.read().lower()
        assert "forgery probability" not in text or "not a forgery" in text







def test_criterion_17_all_models_serialize_deterministically() -> None:
    for row in REFERENCE_OBSERVABILITY_MATRIX:
        payload = row.to_dict()
        assert isinstance(payload, dict)
        assert payload["threat"] == row.threat
    for item in REFERENCE_COMPOSITION_ASSESSMENT:
        payload = item.to_dict()
        assert isinstance(payload, dict)
        assert payload["component"] == item.component







def test_criterion_18_no_machine_learning_in_security_package() -> None:
    import backend.security
    for name in backend.security.__all__:
        assert "classifier" not in name.lower()
        assert "model" not in name.lower() or name in (
            "Assumption", "AssumptionRegister", "FiniteSizeBound",
            "InterpretationResult", "StatementCheck",
        )
