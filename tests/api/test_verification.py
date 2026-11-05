"""Verification endpoint."""

from __future__ import annotations


def test_a_legitimate_transcript_verifies(client, signed_session) -> None:
    transcript = signed_session["transcript"]
    response = client.post(
        "/api/v1/verify",
        json={
            "message": signed_session["message"],
            "transcript": transcript,
            "verifier_context": {"verifier_id": "bob"},
            "session_id": signed_session["session_id"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is True
    assert body["session_valid"] is True
    assert body["message_valid"] is True
    assert body["transcript_valid"] is True
    assert body["state_sequence_valid"] is True
    assert body["measurement_valid"] is True
    assert body["errors"] == []
    assert body["session_id"] == signed_session["session_id"]
    assert body["lifecycle"] == "VERIFIED"
    assert "not a security verdict" in body["note"]


def test_verifying_against_a_different_message_is_rejected(client, signed_session) -> None:
    transcript = signed_session["transcript"]
    response = client.post(
        "/api/v1/verify",
        json={
            "message": "transfer 9999 units to account 7",
            "transcript": transcript,
            "verifier_context": {"verifier_id": "bob"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is False
    assert body["message_valid"] is False
    assert body["errors"]


def test_a_malformed_transcript_is_a_structured_rejection_not_an_http_error(
    client, signed_session
) -> None:


    response = client.post(
        "/api/v1/verify",
        json={
            "message": "m",
            "transcript": {"not": "a transcript"},
            "verifier_context": {"verifier_id": "bob"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is False
    assert body["transcript_valid"] is False
    assert any("validation failed" in error for error in body["errors"])


def test_a_transcript_that_is_not_an_object_is_refused(client) -> None:
    response = client.post(
        "/api/v1/verify",
        json={
            "message": "m",
            "transcript": ["not", "an", "object"],
            "verifier_context": {"verifier_id": "bob"},
        },
    )
    assert response.status_code == 422


def test_a_wrong_protocol_version_fails_the_session_check(client, signed_session) -> None:
    transcript = signed_session["transcript"]
    response = client.post(
        "/api/v1/verify",
        json={
            "message": signed_session["message"],
            "transcript": transcript,
            "verifier_context": {
                "verifier_id": "bob",
                "expected_protocol_version": "RQDS-TP-9.9",
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is False
    assert body["session_valid"] is False


def test_verification_without_a_session_id_records_nothing(client, signed_session) -> None:
    transcript = signed_session["transcript"]
    body = client.post(
        "/api/v1/verify",
        json={
            "message": signed_session["message"],
            "transcript": transcript,
            "verifier_context": {"verifier_id": "bob"},
        },
    ).json()
    assert body["accepted"] is True
    assert body["session_id"] is None
    assert body["lifecycle"] is None


def test_an_unknown_session_id_is_not_found(client, signed_session) -> None:
    transcript = signed_session["transcript"]
    response = client.post(
        "/api/v1/verify",
        json={
            "message": signed_session["message"],
            "transcript": transcript,
            "verifier_context": {"verifier_id": "bob"},
            "session_id": "does-not-exist",
        },
    )
    assert response.status_code == 404


def test_a_rejected_verification_moves_the_session_to_rejected(client, signed_session) -> None:
    response = client.post(
        "/api/v1/verify",
        json={
            "message": "a different message",
            "transcript": signed_session["transcript"],
            "verifier_context": {"verifier_id": "bob"},
            "session_id": signed_session["session_id"],
        },
    )
    assert response.json()["lifecycle"] == "REJECTED"
    fetched = client.get(f"/api/v1/sessions/{signed_session['session_id']}").json()
    assert fetched["lifecycle"] == "REJECTED"


def test_verification_returns_the_raw_counts(client, signed_session) -> None:
    body = client.post(
        "/api/v1/verify",
        json={
            "message": signed_session["message"],
            "transcript": signed_session["transcript"],
            "verifier_context": {"verifier_id": "bob"},
        },
    ).json()
    assert body["state_count"] == 8
    assert isinstance(body["mismatch_count"], int)
    assert isinstance(body["basis_counts"], dict)
    assert isinstance(body["measurement_summary"], dict)
