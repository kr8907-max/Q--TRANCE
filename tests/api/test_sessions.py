"""Signing-session endpoints and the application lifecycle."""

from __future__ import annotations

from backend.api.store import ALLOWED_TRANSITIONS, SessionLifecycle
from backend.protocol import MAX_STATE_COUNT

CREATE = {
    "message": "transfer 10 units to account 7",
    "signer_id": "alice",
    "verifier_id": "bob",
    "state_count": 8,
}


def test_create_session_returns_public_material(client) -> None:
    response = client.post("/api/v1/sessions", json=CREATE)
    assert response.status_code == 201
    body = response.json()
    assert body["lifecycle"] == "CREATED"
    assert body["protocol_status"] == "created"
    assert body["session_id"]
    assert body["nonce"]
    assert body["message_binding"]
    assert body["message_hash"]
    assert body["state_count"] == 8
    assert body["created_at"]
    assert body["history"] == ["CREATED"]


def test_create_session_defaults_to_the_protocol_defaults(client) -> None:
    body = client.post(
        "/api/v1/sessions",
        json={"message": "m", "signer_id": "a", "verifier_id": "b"},
    ).json()
    assert body["state_count"] == 16


def test_create_session_refuses_unknown_fields(client) -> None:
    response = client.post("/api/v1/sessions", json={**CREATE, "secret": "x"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNPROCESSABLE_ENTITY"


def test_create_session_refuses_an_oversized_state_count(client) -> None:
    response = client.post(
        "/api/v1/sessions", json={**CREATE, "state_count": MAX_STATE_COUNT + 1}
    )
    assert response.status_code == 422


def test_create_session_refuses_a_zero_state_count(client) -> None:
    assert client.post("/api/v1/sessions", json={**CREATE, "state_count": 0}).status_code == 422


def test_create_session_refuses_an_empty_message(client) -> None:
    assert client.post("/api/v1/sessions", json={**CREATE, "message": ""}).status_code == 422


def test_create_session_refuses_an_oversized_message(client) -> None:

    assert (
        client.post("/api/v1/sessions", json={**CREATE, "message": "x" * 4097}).status_code
        == 422
    )


def test_sign_returns_a_transcript_and_hash(client, signed_session) -> None:
    body = signed_session["signed"]
    assert body["lifecycle"] == "SIGNED"
    assert body["protocol_status"] == "signed"
    assert body["transcript_hash"]
    assert body["transcript"]["transcript_hash"] == body["transcript_hash"]
    assert body["history"] == ["CREATED", "SIGNED"]


def test_signing_is_deterministic_for_the_same_session(client, store) -> None:
    """The API pins the signer's simulator seed, so a transcript is reproducible.

    The API refuses to sign a session twice, so determinism is verified by
    re-deriving the transcript from the stored session with the same pinned seed
    and comparing it to what the endpoint returned.
    """
    from backend.api.services.session_service import API_SIGNING_SIMULATOR_SEED
    from backend.protocol import sign_session, transcript_to_dict

    created = client.post("/api/v1/sessions", json=CREATE).json()
    signed = client.post(f"/api/v1/sessions/{created['session_id']}/sign").json()

    record = store.get_session(created["session_id"])
    again = sign_session(record.session, simulator_seed=API_SIGNING_SIMULATOR_SEED)

    assert again.transcript.transcript_hash == signed["transcript_hash"]
    assert transcript_to_dict(again.transcript) == signed["transcript"]


def test_two_sessions_with_the_same_message_differ(client) -> None:
    """Distinct sessions are genuinely distinct: the identifier feeds the binding."""
    first = client.post("/api/v1/sessions", json=CREATE).json()
    second = client.post("/api/v1/sessions", json=CREATE).json()

    a = client.post(f"/api/v1/sessions/{first['session_id']}/sign").json()
    b = client.post(f"/api/v1/sessions/{second['session_id']}/sign").json()

    assert a["transcript"]["message_binding"] != b["transcript"]["message_binding"]
    assert a["transcript_hash"] != b["transcript_hash"]


def test_signing_twice_is_refused(client, signed_session) -> None:
    session_id = signed_session["session"]["session_id"]
    response = client.post(f"/api/v1/sessions/{session_id}/sign")
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "CONFLICT"
    assert error["details"]["current"] == "SIGNED"
    assert error["details"]["requested"] == "SIGNED"


def test_signing_an_unknown_session_is_not_found(client) -> None:
    assert client.post("/api/v1/sessions/nope/sign").status_code == 404


def test_get_unknown_session_is_not_found(client) -> None:
    response = client.get("/api/v1/sessions/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_list_sessions_is_empty_initially(client) -> None:
    body = client.get("/api/v1/sessions").json()
    assert body == {"sessions": [], "total": 0}


def test_list_sessions_summarises_created_sessions(client, signed_session) -> None:
    body = client.get("/api/v1/sessions").json()
    assert body["total"] == 1
    entry = body["sessions"][0]
    assert entry["session_id"] == signed_session["session"]["session_id"]
    assert entry["lifecycle"] == "SIGNED"
    assert entry["has_transcript"] is True
    assert entry["transcript_hash"]


def test_expire_moves_a_session_to_expired(client, signed_session) -> None:
    session_id = signed_session["session"]["session_id"]
    body = client.post(f"/api/v1/sessions/{session_id}/expire").json()
    assert body["lifecycle"] == "EXPIRED"
    assert body["history"] == ["CREATED", "SIGNED", "EXPIRED"]


def test_expiring_twice_is_refused(client, signed_session) -> None:
    session_id = signed_session["session"]["session_id"]
    assert client.post(f"/api/v1/sessions/{session_id}/expire").status_code == 200
    response = client.post(f"/api/v1/sessions/{session_id}/expire")
    assert response.status_code == 409
    assert response.json()["error"]["details"]["allowed"] == []


def test_signing_an_expired_session_is_refused(client, signed_session) -> None:
    session_id = signed_session["session"]["session_id"]
    client.post(f"/api/v1/sessions/{session_id}/expire")
    assert client.post(f"/api/v1/sessions/{session_id}/sign").status_code == 409


def test_the_lifecycle_transition_table_is_consistent() -> None:


    assert set(ALLOWED_TRANSITIONS) == set(SessionLifecycle)
    for source, targets in ALLOWED_TRANSITIONS.items():
        assert targets <= set(SessionLifecycle), source
    assert ALLOWED_TRANSITIONS[SessionLifecycle.EXPIRED] == frozenset()


def test_a_session_cannot_be_verified_before_it_is_signed(client) -> None:
    session = client.post("/api/v1/sessions", json=CREATE).json()


    other = client.post("/api/v1/sessions", json=CREATE).json()
    transcript = client.post(f"/api/v1/sessions/{other['session_id']}/sign").json()[
        "transcript"
    ]
    response = client.post(
        "/api/v1/verify",
        json={
            "message": CREATE["message"],
            "transcript": transcript,
            "verifier_context": {"verifier_id": "bob"},
            "session_id": session["session_id"],
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["details"]["current"] == "CREATED"












def _ttl_client(seconds):
    from fastapi.testclient import TestClient

    from backend.api import ApiSettings, ApiStore, create_app

    return TestClient(
        create_app(
            settings=ApiSettings(environment="test", session_ttl_seconds=seconds),
            store=ApiStore(),
        )
    )


def test_automatic_expiry_is_disabled_by_default(client) -> None:
    session = client.post("/api/v1/sessions", json=CREATE).json()
    body = client.get(f"/api/v1/sessions/{session['session_id']}").json()
    assert body["lifecycle"] == "CREATED"
    assert body["history"] == ["CREATED"]


def test_a_session_expires_once_its_ttl_has_passed() -> None:
    ttl_client = _ttl_client(0)
    session = ttl_client.post("/api/v1/sessions", json=CREATE).json()

    body = ttl_client.get(f"/api/v1/sessions/{session['session_id']}").json()
    assert body["lifecycle"] == "EXPIRED"
    assert body["history"] == ["CREATED", "EXPIRED"]


def test_an_expired_session_cannot_be_signed() -> None:
    ttl_client = _ttl_client(0)
    session = ttl_client.post("/api/v1/sessions", json=CREATE).json()

    response = ttl_client.post(f"/api/v1/sessions/{session['session_id']}/sign")
    assert response.status_code == 409
    assert response.json()["error"]["details"]["current"] == "EXPIRED"


def test_expiry_is_reflected_in_the_listing() -> None:
    ttl_client = _ttl_client(0)
    session = ttl_client.post("/api/v1/sessions", json=CREATE).json()

    listing = ttl_client.get("/api/v1/sessions").json()
    assert listing["total"] == 1


    assert listing["sessions"][0]["session_id"] == session["session_id"]
    assert ttl_client.get(f"/api/v1/sessions/{session['session_id']}").json()[
        "lifecycle"
    ] == "EXPIRED"


def test_a_verified_session_can_still_expire() -> None:
    """VERIFIED is not terminal; only EXPIRED is."""
    from fastapi.testclient import TestClient

    from backend.api import ApiSettings, ApiStore, create_app

    settings = ApiSettings(environment="test", session_ttl_seconds=None)
    store = ApiStore()
    client = TestClient(create_app(settings=settings, store=store))

    session_id = client.post("/api/v1/sessions", json=CREATE).json()["session_id"]
    signed = client.post(f"/api/v1/sessions/{session_id}/sign").json()
    verified = client.post(
        "/api/v1/verify",
        json={
            "message": CREATE["message"],
            "transcript": signed["transcript"],
            "verifier_context": {"verifier_id": "bob"},
            "session_id": session_id,
        },
    ).json()
    assert verified["lifecycle"] == "VERIFIED"

    expired = client.post(f"/api/v1/sessions/{session_id}/expire").json()
    assert expired["lifecycle"] == "EXPIRED"
    assert expired["history"] == ["CREATED", "SIGNED", "VERIFIED", "EXPIRED"]
