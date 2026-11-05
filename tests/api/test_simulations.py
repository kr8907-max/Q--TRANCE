"""Simulation endpoints, and the observable/evaluation separation."""

from __future__ import annotations

BASE = {
    "state_count": 8,
    "shot_count": 1,
    "random_seed": 11,
    "measurement_mode": "sampled",
    "noise": {"noise_type": "depolarizing", "noise_strength": 0.02},
    "attack": {"attack_type": "channel_tampering", "fraction": 0.5, "seed": 3},
}


def test_a_valid_scenario_returns_observable_output(client) -> None:
    response = client.post("/api/v1/simulations", json=BASE)
    assert response.status_code == 200
    body = response.json()
    assert body["scenario_id"] == "api-scenario"
    assert body["state_count"] == 8
    assert body["measurement_mode"] == "sampled"
    assert len(body["states"]) == 8
    assert body["mismatch_count"] >= 0
    assert 0.0 <= body["mismatch_proportion"] <= 1.0
    assert set(body["basis_counts"])
    assert "accepted" in body["verification"]
    assert "signer_authorized" in body["authorization"]


def test_the_operational_response_has_no_ground_truth_field(client) -> None:
    body = client.post("/api/v1/simulations", json=BASE).json()

    assert "ground_truth" not in body
    assert body["observable_only"] is True


def test_the_operational_response_leaks_no_attack_label(client) -> None:
    body = client.post("/api/v1/simulations", json=BASE).json()
    rendered = str(body)
    assert "channel_tampering" not in rendered
    assert "is_malicious" not in rendered
    assert "attacker_knowledge" not in rendered


def test_the_evaluation_endpoint_returns_ground_truth(client) -> None:
    body = client.post("/api/v1/simulations/evaluation", json=BASE).json()
    truth = body["ground_truth"]
    assert body["observable_only"] is False
    assert truth["is_malicious"] is True
    assert truth["attack"]["attack_type"] == "channel_tampering"
    assert "evaluation ground truth" in truth["label"]


def test_an_honest_evaluation_run_reports_no_attack(client) -> None:
    body = client.post(
        "/api/v1/simulations/evaluation",
        json={**BASE, "attack": {"attack_type": "none", "fraction": 0.0}},
    ).json()
    assert body["ground_truth"]["is_malicious"] is False


def test_the_same_seed_reproduces_the_same_observable_output(client) -> None:
    first = client.post("/api/v1/simulations", json=BASE).json()
    second = client.post("/api/v1/simulations", json=BASE).json()
    assert first["states"] == second["states"]
    assert first["mismatch_count"] == second["mismatch_count"]
    assert first["simulator_seed"] == second["simulator_seed"]


def test_a_different_seed_changes_the_run(client) -> None:
    first = client.post("/api/v1/simulations", json=BASE).json()
    other = client.post("/api/v1/simulations", json={**BASE, "random_seed": 12}).json()
    assert first["simulator_seed"] != other["simulator_seed"]


def test_an_unknown_noise_type_is_refused_by_schema(client) -> None:
    response = client.post(
        "/api/v1/simulations", json={**BASE, "noise": {"noise_type": "nonsense"}}
    )
    assert response.status_code == 422


def test_an_unknown_attack_type_is_refused_by_schema(client) -> None:
    response = client.post(
        "/api/v1/simulations", json={**BASE, "attack": {"attack_type": "nonsense"}}
    )
    assert response.status_code == 422


def test_a_fraction_on_a_non_fractional_attack_is_refused(client) -> None:

    response = client.post(
        "/api/v1/simulations",
        json={**BASE, "attack": {"attack_type": "forgery", "fraction": 0.5}},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BAD_REQUEST"


def test_an_out_of_range_noise_strength_is_refused(client) -> None:
    response = client.post(
        "/api/v1/simulations",
        json={**BASE, "noise": {"noise_type": "depolarizing", "noise_strength": 5.0}},
    )
    assert response.status_code == 422


def test_an_oversized_state_count_is_refused(client) -> None:
    assert (
        client.post("/api/v1/simulations", json={**BASE, "state_count": 100000}).status_code
        == 422
    )


def test_an_unknown_measurement_mode_is_refused(client) -> None:
    response = client.post(
        "/api/v1/simulations", json={**BASE, "measurement_mode": "made-up"}
    )
    assert response.status_code == 422
