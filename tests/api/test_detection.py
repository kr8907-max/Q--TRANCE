"""Detection endpoint, and the ground-truth separation it depends on."""

from __future__ import annotations

import pytest

from backend.api.schemas.detection import DetectionRequest


GROUND_TRUTH_FIELDS = (
    "attack_type",
    "attack_fraction",
    "noise_strength",
    "noise_type",
    "is_malicious",
    "ground_truth",
    "label",
    "scenario_id",
    "random_seed",
    "simulator_seed",
)


def _observable_payload(**overrides) -> dict:
    payload = {
        "session_id": "s-1",
        "nonce": "n-1",
        "protocol_version": "RQDS-TP-1.0",
        "signer_id": "alice",
        "verifier_id": "bob",
        "authorized_signers": ["alice"],
        "authorized_verifiers": ["bob"],
        "states": [
            {"index": i, "basis": "Z", "expected_bit": 0, "probability_expected": 1.0, "matched": True}
            for i in range(4)
        ],
        "declared_state_count": 4,
        "measurement_mode": "sampled",
        "basis_counts": {"Z": 4},
        "verification": {"available": True, "accepted": True},
    }
    payload.update(overrides)
    return payload







def test_the_request_schema_has_no_ground_truth_field() -> None:


    declared = set(DetectionRequest.model_fields)
    leaked = declared & set(GROUND_TRUTH_FIELDS)
    assert not leaked, f"the detection request exposes ground-truth fields: {sorted(leaked)}"


@pytest.mark.parametrize("field", GROUND_TRUTH_FIELDS)
def test_injecting_a_ground_truth_field_is_refused(client, field: str) -> None:
    response = client.post("/api/v1/detect", json=_observable_payload(**{field: "x"}))
    assert response.status_code == 422, field
    assert response.json()["error"]["code"] == "UNPROCESSABLE_ENTITY"


def test_the_detection_service_builds_an_input_without_labels(client) -> None:
    from backend.api.schemas.detection import DetectionRequest as Request
    from backend.api.services.detection_service import build_detection_input
    from backend.detection import ObservableDetectionInput

    built = build_detection_input(Request(**_observable_payload()))
    assert isinstance(built, ObservableDetectionInput)

    assert not (set(built.__dataclass_fields__) & set(GROUND_TRUTH_FIELDS))







def test_a_clean_observable_session_is_reported_as_clear(client) -> None:
    response = client.post("/api/v1/detect", json=_observable_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["protocol_valid"] is True
    assert body["overall_status"] in {"CLEAR", "QUANTUM_ANOMALY", "MULTIPLE_FINDINGS"}
    assert body["explanation"]
    assert isinstance(body["findings"], list)
    assert body["finding_count"] == len(body["findings"])


def test_the_response_carries_the_security_boundary(client) -> None:
    body = client.post("/api/v1/detect", json=_observable_payload()).json()
    assessment = body["security_assessment"]
    assert assessment["status"] == "evidence_only"
    assert assessment["formal_proof_present"] is False
    assert assessment["ground_truth_used"] is False
    assert any("not attribution" in item for item in assessment["limitations"])


def test_the_response_contains_no_attack_label(client) -> None:
    """No label-bearing key may appear anywhere in a detection response.

    A substring search for attack names would be wrong: the response legitimately
    says "no formal forgery bound ... is produced here". What must not appear is a
    *field* carrying the answer, so this walks the parsed body looking for keys.
    """
    body = client.post("/api/v1/detect", json=_observable_payload()).json()

    def walk(node, path=""):
        if isinstance(node, dict):
            for key, value in node.items():
                assert key not in GROUND_TRUTH_FIELDS, f"{path}.{key} exposes {key}"
                walk(value, f"{path}.{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]")

    walk(body)


def test_the_diagnostic_features_are_typed(client) -> None:
    features = client.post("/api/v1/detect", json=_observable_payload()).json()["features"]
    for key in (
        "mismatch",
        "disturbance",
        "fidelity",
        "basis",
        "measurement_counts_by_basis",
        "basis_distribution",
        "redundancies",
        "notes",
    ):
        assert key in features, key
    assert "mismatch_rate" in features["mismatch"]
    assert "disturbance_rate" in features["disturbance"]
    assert "observed_bases" in features["basis"]


def test_a_transcript_hash_mismatch_produces_an_integrity_finding(client) -> None:
    payload = _observable_payload(
        declared_transcript_hash="deadbeef",
        transcript_payload={"session_id": "s-1", "nonce": "n-1"},
        verification={"available": True, "accepted": False, "transcript_valid": False},
    )
    body = client.post("/api/v1/detect", json=payload).json()
    assert body["findings"], "a declared hash mismatch must produce evidence"
    assert body["overall_status"] != "CLEAR"


def test_a_declared_mismatch_anomaly_is_reported(client) -> None:
    payload = _observable_payload(
        states=[
            {"index": i, "basis": "Z", "expected_bit": 0, "probability_expected": 1.0, "matched": i > 2}
            for i in range(4)
        ],
        verification={
            "available": True,
            "accepted": False,
            "measurement_valid": False,
            "declared_mismatch_count": 3,
        },
    )
    body = client.post("/api/v1/detect", json=payload).json()
    assert body["overall_status"] != "CLEAR"







def test_the_api_reuses_the_m4_replay_registry(client, store) -> None:
    from backend.detection import ReplayRegistry

    assert isinstance(store.replay_registry, ReplayRegistry)


def test_consuming_a_replay_event_makes_the_second_observation_a_replay(client) -> None:
    payload = _observable_payload(consume_replay=True)
    first = client.post("/api/v1/detect", json=payload).json()
    assert not any(item["category"] == "REPLAY" for item in first["findings"])

    second = client.post("/api/v1/detect", json=payload).json()
    assert any(item["category"] == "REPLAY" for item in second["findings"])


def test_not_consuming_leaves_the_ledger_untouched(client) -> None:
    payload = _observable_payload(consume_replay=False)
    for _ in range(2):
        body = client.post("/api/v1/detect", json=payload).json()
        assert not any(item["category"] == "REPLAY" for item in body["findings"])


def test_the_ledger_is_reset_with_the_store(client, store) -> None:
    payload = _observable_payload(consume_replay=True)
    client.post("/api/v1/detect", json=payload)
    store.reset()
    body = client.post("/api/v1/detect", json=payload).json()
    assert not any(item["category"] == "REPLAY" for item in body["findings"])
