"""The input bounds documented in api-reference section 7, at their edges.

The other API tests check that an out-of-range value is refused. That verifies
half of a bound: a bound set one too low would still refuse everything above it
while wrongly rejecting a legal request. These tests pin both sides of each
documented limit, so the table in the reference is exact rather than merely
strict.

Expensive paths are exercised through the cheapest endpoint that shares the same
schema bound, so the suite stays fast without testing a different rule.
"""

from __future__ import annotations

from backend.protocol import MAX_STATE_COUNT
from backend.simulation import MAX_SEED

SESSION = {
    "message": "transfer 10 units to account 7",
    "signer_id": "alice",
    "verifier_id": "bob",
    "state_count": 8,
}


def _create_session(client, **overrides) -> int:
    """Post a session and return the status code."""
    return client.post("/api/v1/sessions", json={**SESSION, **overrides}).status_code


def _run_scenario(client, **overrides) -> int:
    """Post a small scenario and return the status code."""
    payload = {"state_count": 4, **overrides}
    return client.post("/api/v1/simulations", json=payload).status_code







def test_a_message_at_the_maximum_is_accepted(client) -> None:
    assert _create_session(client, message="x" * 4096) == 201


def test_a_message_one_over_the_maximum_is_refused(client) -> None:
    assert _create_session(client, message="x" * 4097) == 422


def test_an_empty_message_is_refused(client) -> None:
    assert _create_session(client, message="") == 422













def test_an_identity_at_the_maximum_is_accepted(client) -> None:
    assert _create_session(client, signer_id="s" * 128, verifier_id="v" * 128) == 201


def test_an_identity_one_over_the_maximum_is_refused(client) -> None:
    assert _create_session(client, signer_id="s" * 129) == 422


def test_an_identity_at_the_api_former_limit_is_refused(client) -> None:


    assert _create_session(client, signer_id="s" * 256) == 422


def test_an_empty_identity_is_refused(client) -> None:
    assert _create_session(client, verifier_id="") == 422


def test_an_identity_that_does_not_start_alphanumerically_is_refused(client) -> None:
    assert _create_session(client, signer_id="-leading-dash") == 422


def test_an_identity_containing_a_space_is_refused(client) -> None:
    assert _create_session(client, signer_id="has space") == 422


def test_the_allowed_identity_punctuation_is_accepted(client) -> None:
    assert _create_session(client, signer_id="a.b_c:d@e-f") == 201


def test_a_malformed_protocol_version_is_refused(client) -> None:
    assert _create_session(client, protocol_version="nonsense") == 422


def test_a_well_formed_protocol_version_is_accepted(client) -> None:
    assert _create_session(client, protocol_version="RQDS-TP-1.0") == 201


def test_a_malformed_verifier_identity_is_refused(client) -> None:
    response = client.post(
        "/api/v1/verify",
        json={
            "message": "m",
            "transcript": {},
            "verifier_context": {"verifier_id": "not a valid identity"},
        },
    )
    assert response.status_code == 422


def test_a_malformed_simulation_identity_is_refused(client) -> None:
    assert _run_scenario(client, signer_id="s" * 129) == 422







def test_the_minimum_state_count_is_accepted(client) -> None:
    assert _create_session(client, state_count=1) == 201


def test_the_maximum_state_count_is_accepted(client) -> None:


    assert _create_session(client, state_count=MAX_STATE_COUNT) == 201


def test_one_over_the_maximum_state_count_is_refused(client) -> None:
    assert _create_session(client, state_count=MAX_STATE_COUNT + 1) == 422


def test_a_zero_state_count_is_refused(client) -> None:
    assert _create_session(client, state_count=0) == 422







def test_a_single_shot_is_accepted(client) -> None:
    assert _run_scenario(client, shot_count=1) == 200


def test_one_shot_over_the_maximum_is_refused(client) -> None:
    assert _run_scenario(client, shot_count=1025) == 422


def test_a_zero_shot_count_is_refused(client) -> None:
    assert _run_scenario(client, shot_count=0) == 422


def test_both_ends_of_the_attack_fraction_are_accepted(client) -> None:
    for fraction in (0.0, 1.0):
        status = _run_scenario(
            client, attack={"attack_type": "channel_tampering", "fraction": fraction}
        )
        assert status == 200, fraction


def test_a_fraction_above_one_is_refused(client) -> None:
    status = _run_scenario(
        client, attack={"attack_type": "channel_tampering", "fraction": 1.5}
    )
    assert status == 422


def test_both_ends_of_the_noise_strength_are_accepted(client) -> None:
    for strength in (0.0, 1.0):
        status = _run_scenario(
            client, noise={"noise_type": "depolarizing", "noise_strength": strength}
        )
        assert status == 200, strength


def test_a_noise_strength_above_one_is_refused(client) -> None:
    status = _run_scenario(
        client, noise={"noise_type": "depolarizing", "noise_strength": 1.5}
    )
    assert status == 422







def test_both_ends_of_the_seed_range_are_accepted(client) -> None:
    for seed in (0, MAX_SEED):
        assert _run_scenario(client, random_seed=seed) == 200, seed


def test_a_seed_above_the_maximum_is_refused(client) -> None:
    assert _run_scenario(client, random_seed=MAX_SEED + 1) == 422


def test_a_negative_seed_is_refused(client) -> None:
    assert _run_scenario(client, random_seed=-1) == 422







def test_a_single_calibration_session_is_accepted(client) -> None:
    response = client.post(
        "/api/v1/calibration/run", json={"state_count": 20, "session_count": 1}
    )
    assert response.status_code == 201


def test_a_zero_session_calibration_is_refused(client) -> None:
    assert (
        client.post("/api/v1/calibration/run", json={"session_count": 0}).status_code == 422
    )


def test_one_calibration_session_over_the_maximum_is_refused(client) -> None:
    assert (
        client.post("/api/v1/calibration/run", json={"session_count": 65}).status_code == 422
    )


def test_the_confidence_interval_is_open_at_both_ends(client) -> None:
    for confidence in (0.0, 1.0):
        response = client.post("/api/v1/calibration/run", json={"confidence": confidence})
        assert response.status_code == 422, confidence







def test_an_empty_statement_list_is_accepted(client) -> None:
    assert client.post("/api/v1/security/analyze", json={"statements": []}).status_code == 200


def test_fifty_statements_are_accepted(client) -> None:
    response = client.post(
        "/api/v1/security/analyze", json={"statements": ["an honest sentence"] * 50}
    )
    assert response.status_code == 200
    assert len(response.json()["checks"]) == 50


def test_fifty_one_statements_are_refused(client) -> None:
    response = client.post("/api/v1/security/analyze", json={"statements": ["x"] * 51})
    assert response.status_code == 422
