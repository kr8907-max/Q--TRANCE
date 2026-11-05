"""Threat-observability matrix.

The matrix is derived from structural code evidence and the committed M5
benchmark. These tests verify that the classification is consistent with both
sources and that the four protocol-layer attacks are never falsely claimed to
produce quantum disturbance.

The measured rates are read out of ``benchmarks/m5-reference.json`` rather than
written into this file, so the tests fail if the matrix and the artifact drift
apart in either direction.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from backend.security.observability import (
    REFERENCE_OBSERVABILITY_MATRIX,
    ThreatObservability,
    matrix_summary,
    render_matrix_table,
    threat_observability,
)

BENCHMARK_PATH = (
    pathlib.Path(__file__).resolve().parent.parent.parent
    / "benchmarks"
    / "m5-reference.json"
)


def _benchmark_attack_rows() -> dict:
    """Return the per-attack rows of the committed M5 benchmark."""
    payload = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
    return payload["attack_evaluation"]["by_attack_type"]







def test_all_six_threats_have_a_row() -> None:
    names = {row.threat for row in REFERENCE_OBSERVABILITY_MATRIX}
    assert names == {
        "forgery",
        "impersonation",
        "unauthorized_verification",
        "replay",
        "intercept_resend",
        "channel_tampering",
    }


def test_the_four_protocol_attacks_produce_no_quantum_disturbance() -> None:
    for row in REFERENCE_OBSERVABILITY_MATRIX:
        if row.threat in ("forgery", "impersonation", "unauthorized_verification", "replay"):
            assert row.quantum_disturbance is False, row.threat
            assert row.detector_visible_quantum is False, row.threat


def test_the_two_channel_attacks_produce_quantum_disturbance() -> None:
    for row in REFERENCE_OBSERVABILITY_MATRIX:
        if row.threat in ("intercept_resend", "channel_tampering"):
            assert row.quantum_disturbance is True, row.threat
            assert row.detector_visible_quantum is True, row.threat


def test_protocol_attacks_require_classical_controls() -> None:
    for row in REFERENCE_OBSERVABILITY_MATRIX:
        if row.threat in ("forgery", "impersonation", "unauthorized_verification", "replay"):
            assert row.requires_classical_control is True, row.threat

            assert row.detector_visible_quantum is False, row.threat


def test_channel_attacks_do_not_require_classical_controls() -> None:
    for row in REFERENCE_OBSERVABILITY_MATRIX:
        if row.threat in ("intercept_resend", "channel_tampering"):
            assert row.requires_classical_control is False, row.threat







def test_m5_measured_detection_rates_match_committed_benchmark() -> None:




    rows = _benchmark_attack_rows()
    assert set(rows) == {row.threat for row in REFERENCE_OBSERVABILITY_MATRIX}
    for row in REFERENCE_OBSERVABILITY_MATRIX:
        measured = rows[row.threat]
        assert row.m5_detection_rate == pytest.approx(
            measured["detection_rate"]
        ), row.threat
        assert row.m5_far == pytest.approx(measured["far"]), row.threat
        assert row.empirically_evaluated is True


def test_the_matrix_notes_quote_the_artifact_trial_counts() -> None:



    for attack, measured in _benchmark_attack_rows().items():
        total = measured["matrix"]["total"]
        assert total > 0, attack
        notes = " ".join(threat_observability(attack).notes)
        assert f"/{total} trials" in notes, (attack, total, notes)







def test_threat_observability_lookup() -> None:
    row = threat_observability("replay")
    assert row.threat == "replay"
    assert row.quantum_disturbance is False


def test_threat_observability_raises_for_unknown() -> None:
    with pytest.raises(KeyError, match="no observability row"):
        threat_observability("adaptive_spoofing")


def test_render_matrix_table_is_markdown() -> None:
    table = render_matrix_table()
    assert "| Threat |" in table
    for row in REFERENCE_OBSERVABILITY_MATRIX:
        assert row.threat in table


def test_matrix_summary_is_json_ready() -> None:
    summary = matrix_summary()
    assert summary["empirically_evaluated_count"] == 6
    assert summary["covered_count"] == 6
    assert "quantum_visible" in summary
    assert "classical_only" in summary
    assert len(summary["quantum_visible"]) == 2
    assert len(summary["classical_only"]) == 4







def test_every_row_serialises() -> None:
    for row in REFERENCE_OBSERVABILITY_MATRIX:
        payload = row.to_dict()
        assert payload["threat"] == row.threat
        assert isinstance(payload["notes"], list)
