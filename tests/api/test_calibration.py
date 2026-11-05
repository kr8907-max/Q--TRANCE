"""Calibration endpoints."""

from __future__ import annotations


def test_calibration_run_returns_a_threshold(calibration_run, expensive_client) -> None:
    body = calibration_run
    assert body["calibration_id"].startswith("cal-")
    assert body["total_valid"] > 0
    threshold = body["threshold"]
    assert threshold["state_count"] == 20
    assert threshold["method"] == "honest-null-quantile-with-upper-confidence-bound"
    assert 0.0 <= threshold["p_upper"] <= 1.0
    assert 0 <= threshold["critical_count"] <= threshold["state_count"]
    assert threshold["calibration_role"] == "CALIBRATION"


def test_calibration_run_reports_the_configuration_it_used(calibration_run) -> None:
    config = calibration_run["config"]
    assert config["noise_type"] == "depolarizing"
    assert config["measurement_mode"] == "sampled"
    assert config["statistic"] == "mismatch_rate"
    assert config["dataset_role"] == "CALIBRATION"
    assert config["session_count"] == 2


def test_calibration_run_reports_an_exact_interval(calibration_run) -> None:
    interval = calibration_run["interval"]
    assert interval is not None
    assert interval["method"].startswith("clopper-pearson")
    assert interval["lower"] <= interval["upper"]
    assert interval["successes"] <= interval["trials"]
    upper = calibration_run["upper_bound"]
    assert upper["one_sided"] is True


def test_calibration_run_omits_the_per_state_probability_vector(calibration_run) -> None:
    homogeneity = calibration_run["homogeneity"]


    assert "predicted_probabilities" not in homogeneity
    assert "omitted" in homogeneity
    assert homogeneity["state_count"] > 0


def test_calibration_run_states_its_boundary(calibration_run) -> None:
    assessment = calibration_run["security_assessment"]
    assert assessment["status"] == "assumption_conditioned"
    assert assessment["formal_proof_present"] is False
    assert assessment["limitations"]


def test_calibration_can_be_retrieved(calibration_run, expensive_client) -> None:
    retrieved = expensive_client.get(
        f"/api/v1/calibration/{calibration_run['calibration_id']}"
    )
    assert retrieved.status_code == 200
    assert retrieved.json()["calibration_id"] == calibration_run["calibration_id"]


def test_an_unknown_calibration_is_not_found(expensive_client) -> None:
    assert expensive_client.get("/api/v1/calibration/nope").status_code == 404


def test_reference_calibration_reports_the_methodology(expensive_client) -> None:
    response = expensive_client.get("/api/v1/calibration/reference")
    assert response.status_code == 200
    body = response.json()
    assert body["methodology"] == "honest-null-quantile-with-upper-confidence-bound"
    assert body["operating_point_name"] == "m5-reference"
    assert body["alpha"] == 0.05

    assert body["calibration_alpha"] + body["evaluation_alpha"] == body["alpha"]


def test_reference_calibration_reports_the_recorded_operating_point(expensive_client) -> None:
    body = expensive_client.get("/api/v1/calibration/reference").json()
    recorded = body["recorded_operating_point"]
    if recorded is None:  # pragma: no cover - the artifact is committed
        raise AssertionError("the committed benchmark artifact should be present")
    assert recorded["state_count"] == 500
    assert recorded["critical_count"] == 10
    assert recorded["noise_type"] == "depolarizing"
    assert recorded["measurement_mode"] == "sampled"
    assert body["provenance"]["available"] is True
    assert "m5-reference.json" in body["provenance"]["artifact"]


def test_reference_calibration_states_its_boundary(expensive_client) -> None:
    assessment = expensive_client.get("/api/v1/calibration/reference").json()[
        "security_assessment"
    ]
    assert assessment["formal_proof_present"] is False
    assert any("not a" in item and "security parameter" in item for item in assessment["limitations"])


def test_an_oversized_session_count_is_refused(client) -> None:

    response = client.post(
        "/api/v1/calibration/run", json={"state_count": 20, "session_count": 99}
    )
    assert response.status_code == 422


def test_a_bad_confidence_is_refused(client) -> None:
    assert (
        client.post("/api/v1/calibration/run", json={"confidence": 1.5}).status_code == 422
    )


def test_a_bad_noise_type_is_refused(client) -> None:
    response = client.post("/api/v1/calibration/run", json={"noise_type": "nonsense"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BAD_REQUEST"
