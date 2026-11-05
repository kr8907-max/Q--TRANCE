"""Concurrency and thread-safety of the API's shared state.

The store is shared between requests and uvicorn runs synchronous endpoints in a
thread pool, so these tests drive real concurrent requests rather than asserting
that a lock exists.

Two properties matter:

* **No torn reads.** A session's transcript and its hash are published together,
  so a reader must never see one without the other.
* **No lost or duplicated transitions.** A lifecycle move that two requests race
  for must be won by exactly one; the other must be refused.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

CREATE = {
    "message": "transfer 10 units to account 7",
    "signer_id": "alice",
    "verifier_id": "bob",
    "state_count": 8,
}


def test_concurrent_reads_never_see_a_torn_session(client) -> None:
    """A reader must never observe half of a signature.

    ``lifecycle`` and ``protocol_status`` are two views of the same event, and
    the listing reports ``has_transcript`` alongside ``transcript_hash``. Both
    pairs are published in one critical section, so a reader must never see one
    member of a pair updated without the other.
    """
    session_id = client.post("/api/v1/sessions", json=CREATE).json()["session_id"]

    stop = threading.Event()
    torn: list[tuple] = []
    lock = threading.Lock()

    def reader() -> None:
        while not stop.is_set():
            view = client.get(f"/api/v1/sessions/{session_id}").json()
            listing = client.get("/api/v1/sessions").json()["sessions"][0]
            with lock:
                if view["lifecycle"] == "SIGNED" and view["protocol_status"] != "signed":
                    torn.append(("lifecycle", view["lifecycle"], view["protocol_status"]))
                if listing["has_transcript"] and not listing["transcript_hash"]:
                    torn.append(("listing", listing["has_transcript"], listing["transcript_hash"]))

    with ThreadPoolExecutor(max_workers=4) as pool:
        readers = [pool.submit(reader) for _ in range(4)]
        try:
            signed = client.post(f"/api/v1/sessions/{session_id}/sign")
            assert signed.status_code == 200, signed.text
        finally:
            stop.set()
        for future in readers:
            future.result()

    assert not torn, torn
    view = client.get(f"/api/v1/sessions/{session_id}").json()
    assert view["lifecycle"] == "SIGNED"
    assert view["protocol_status"] == "signed"
    listing = client.get("/api/v1/sessions").json()["sessions"][0]
    assert listing["transcript_hash"] == signed.json()["transcript_hash"]


def test_signing_a_session_concurrently_succeeds_exactly_once(client) -> None:
    session = client.post("/api/v1/sessions", json=CREATE).json()
    session_id = session["session_id"]

    def sign() -> int:
        return client.post(f"/api/v1/sessions/{session_id}/sign").status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        codes = list(pool.map(lambda _: sign(), range(8)))

    assert codes.count(200) == 1, codes
    assert codes.count(409) == 7, codes
    assert client.get(f"/api/v1/sessions/{session_id}").json()["lifecycle"] == "SIGNED"


def test_concurrent_creation_allocates_distinct_sessions(client) -> None:
    def create(_: int) -> str:
        response = client.post("/api/v1/sessions", json=CREATE)
        assert response.status_code == 201, response.text
        return response.json()["session_id"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(create, range(24)))

    assert len(set(ids)) == 24
    assert client.get("/api/v1/sessions").json()["total"] == 24


def test_the_replay_ledger_is_shared_across_requests(client) -> None:
    """The ledger is one object, so a consume in one request is visible in the next."""
    payload = {"nonce": "shared-nonce", "session_id": "shared-session", "consume_replay": True}
    first = client.post("/api/v1/detect", json=payload).json()
    second = client.post("/api/v1/detect", json=payload).json()
    assert not any(item["category"] == "REPLAY" for item in first["findings"])
    assert any(item["category"] == "REPLAY" for item in second["findings"])


def test_reset_clears_the_ledger_in_place(client, store) -> None:
    """reset() must clear the ledger, not swap in a new object.

    Swapping would let one request keep using the old ledger while another used
    the new one.
    """
    registry_before = store.replay_registry
    payload = {"nonce": "n", "session_id": "s", "consume_replay": True}
    client.post("/api/v1/detect", json=payload)
    store.reset()
    assert store.replay_registry is registry_before
    body = client.post("/api/v1/detect", json=payload).json()
    assert not any(item["category"] == "REPLAY" for item in body["findings"])


def test_concurrent_health_checks_do_not_disturb_state(client) -> None:
    def health(_: int) -> int:
        return client.get("/health").status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        codes = list(pool.map(health, range(32)))
    assert set(codes) == {200}


def test_a_slow_handler_does_not_block_other_requests(client, monkeypatch) -> None:
    """A long handler must not stall the process.

    Handlers are synchronous, so FastAPI runs them in a thread pool and the event
    loop stays free. This proves it behaviourally rather than by inspecting
    ``def`` versus ``async def``: while a one-second request is in flight,
    ``/health`` must still answer promptly.
    """
    import time

    import backend.api.services.session_service as session_service

    real_create = session_service.create
    started = threading.Event()

    def _slow(store, request):
        started.set()
        time.sleep(1.0)
        return real_create(store, request)

    monkeypatch.setattr(session_service, "create", _slow)

    with ThreadPoolExecutor(max_workers=2) as pool:
        slow = pool.submit(client.post, "/api/v1/sessions", json=CREATE)
        assert started.wait(timeout=10), "the slow handler never started"

        began = time.perf_counter()
        health = client.get("/health")
        waited = time.perf_counter() - began

        assert health.status_code == 200
        assert waited < 0.5, f"/health waited {waited:.2f}s behind a slow request"
        assert slow.result().status_code == 201


def test_a_slow_handler_does_not_block_a_read_of_its_own_resource(
    client, monkeypatch
) -> None:
    """The same property for a request that touches the shared store."""
    import time

    import backend.api.services.session_service as session_service

    session_id = client.post("/api/v1/sessions", json=CREATE).json()["session_id"]
    real_sign = session_service.sign
    started = threading.Event()

    def _slow(store, requested_id, settings):
        started.set()
        time.sleep(1.0)
        return real_sign(store, requested_id, settings)

    monkeypatch.setattr(session_service, "sign", _slow)

    with ThreadPoolExecutor(max_workers=2) as pool:
        slow = pool.submit(client.post, f"/api/v1/sessions/{session_id}/sign")
        assert started.wait(timeout=10), "the slow handler never started"

        began = time.perf_counter()
        listing = client.get("/api/v1/sessions")
        waited = time.perf_counter() - began

        assert listing.status_code == 200
        assert waited < 0.5, f"the listing waited {waited:.2f}s on the signing lock"
        assert slow.result().status_code == 200


def test_logging_setup_is_idempotent_under_concurrency() -> None:
    """Building applications concurrently must not stack log handlers.

    Without the lock, several threads can pass the "no structured handler yet"
    check and each add one, so every log line is emitted more than once.
    """
    import logging

    from backend.api.middleware import JsonLogFormatter, configure_logging

    api_logger = logging.getLogger("sih26141.api")
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: configure_logging(), range(16)))

    structured = [
        handler
        for handler in api_logger.handlers
        if isinstance(handler.formatter, JsonLogFormatter)
    ]
    assert len(structured) == 1, len(structured)
