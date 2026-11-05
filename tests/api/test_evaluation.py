"""Evaluation endpoints, and the explicit use of ground truth."""

from __future__ import annotations


def test_evaluation_run_returns_a_summary(evaluation_run) -> None:
    body = evaluation_run
    assert body["evaluation_id"].startswith("eval-")
    assert body["profile"] == "m5-smoke"
    assert body["dataset_role"] == "FINAL_EVALUATION"
    assert body["by_attack_type"]
    assert body["curve_names"]


def test_evaluation_reports_per_attack_metrics(evaluation_run) -> None:
    for attack, metrics in evaluation_run["by_attack_type"].items():
        assert "confusion" in metrics, attack
        matrix = metrics["confusion"]
        for key in ("tp", "tn", "fp", "fn"):
            assert isinstance(matrix[key], int), (attack, key)
        assert metrics["detection_rate"] is not None, attack
        assert metrics["far"] is not None, attack


def test_evaluation_reports_the_honest_side(evaluation_run) -> None:


    assert evaluation_run["honest_frr_by_noise"]
    assert all(
        value is None or 0.0 <= value <= 1.0
        for value in evaluation_run["honest_frr_by_noise"].values()
    )


def test_evaluation_reports_its_configuration(evaluation_run) -> None:
    config = evaluation_run["configuration"]
    assert config["profile"] == "m5-smoke"
    assert config["state_count"] == 20
    assert config["measurement_mode"] == "sampled"
    assert isinstance(config["seed_base"], int)
    assert config["attack_types"]


def test_there_is_no_pooled_overall_matrix(evaluation_run) -> None:
    """Honest and malicious populations are not pooled.

    The per-attack rows contain no honest trials, so a pooled matrix would report
    an FRR computed from zero sessions. The response must not offer one.
    """
    assert "overall" not in evaluation_run
    assert evaluation_run["by_attack_type"], "per-attack metrics are the FRR-safe view"
    for attack, metrics in evaluation_run["by_attack_type"].items():
        assert metrics["confusion"]["honest"] == 0, attack


def test_evaluation_declares_that_it_used_ground_truth(evaluation_run) -> None:
    assert evaluation_run["ground_truth_used"] is True
    assessment = evaluation_run["security_assessment"]
    assert assessment["ground_truth_used"] is True
    assert assessment["status"] == "empirical_measurement"
    assert assessment["formal_proof_present"] is False
    assert any("not cryptographic bounds" in item for item in assessment["limitations"])


def test_the_operating_point_is_reported(evaluation_run) -> None:
    point = evaluation_run["operating_point"]
    assert point is not None
    assert point["name"] == "m5-reference"
    assert point["critical_count"] > 0


def test_evaluation_can_be_retrieved(evaluation_run, expensive_client) -> None:
    response = expensive_client.get(f"/api/v1/evaluation/{evaluation_run['evaluation_id']}")
    assert response.status_code == 200
    assert response.json()["evaluation_id"] == evaluation_run["evaluation_id"]


def test_the_full_artifact_is_available_separately(evaluation_run, expensive_client) -> None:
    response = expensive_client.get(
        f"/api/v1/evaluation/{evaluation_run['evaluation_id']}/artifact"
    )
    assert response.status_code == 200
    body = response.json()
    assert "report" not in body["artifact"]
    assert body["artifact"]["milestone"] == "M5"
    assert body["artifact"]["limitations"]
    assert body["markdown"]
    assert "megabytes" in body["size_warning"]


def test_an_unknown_evaluation_is_not_found(expensive_client) -> None:
    assert expensive_client.get("/api/v1/evaluation/nope").status_code == 404
    assert (
        expensive_client.get("/api/v1/evaluation/nope/artifact").status_code == 404
    )


def test_an_unknown_profile_is_refused(client) -> None:
    response = client.post("/api/v1/evaluation/run", json={"profile": "everything"})
    assert response.status_code == 422


def test_evaluation_is_a_separate_endpoint_from_detection(client) -> None:


    assert client.post("/api/v1/detect", json={"attack_type": "forgery"}).status_code == 422
    assert (
        client.post("/api/v1/evaluation/run", json={"attack_type": "forgery"}).status_code
        == 422
    )
