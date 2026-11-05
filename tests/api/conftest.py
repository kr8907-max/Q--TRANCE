"""Fixtures for the API tests.

Every test gets its own application, its own settings and its own in-memory
store, so tests cannot leak state into each other through the API's storage. The
two genuinely expensive operations -- a calibration and a benchmark run -- are
session-scoped so the suite pays for them once.
"""

from __future__ import annotations

import pathlib

import pytest
from fastapi.testclient import TestClient

from backend.api import ApiSettings, ApiStore, create_app





TEST_SETTINGS = ApiSettings(
    environment="test",
    cors_origins=("http://localhost:5173",),
)


def configured_client(**overrides) -> TestClient:
    """A client whose application was built with ``overrides`` applied.

    Used by the tests that prove a configured limit is the one actually enforced.
    Each call builds a separate application with its own store, so a limit set
    here cannot reach any other application -- which is the property those tests
    also check.
    """
    return TestClient(
        create_app(
            settings=ApiSettings(environment="test", **overrides),
            store=ApiStore(),
        ),
        raise_server_exceptions=False,
    )


SESSION_MESSAGE = "transfer 10 units to account 7"


@pytest.fixture()
def store() -> ApiStore:
    """A fresh in-memory store."""
    return ApiStore()


@pytest.fixture()
def app(store: ApiStore):
    """A fresh application wired to the fresh store."""
    return create_app(settings=TEST_SETTINGS, store=store)


@pytest.fixture()
def client(app) -> TestClient:
    """A client that lets server exceptions propagate, so bugs surface as errors."""
    return TestClient(app)


@pytest.fixture()
def lenient_client(app) -> TestClient:
    """A client that converts server exceptions into 500 responses.

    Used to prove that the unhandled-exception path returns the error envelope
    rather than a traceback.
    """
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def signed_session(client: TestClient) -> dict:
    """A created and signed session, its transcript, and the message it signed.

    The message is returned separately because the API does not echo it back:
    the session view exposes the message hash and the binding, not the message.
    """
    created = client.post(
        "/api/v1/sessions",
        json={
            "message": SESSION_MESSAGE,
            "signer_id": "alice",
            "verifier_id": "bob",
            "state_count": 8,
        },
    )
    assert created.status_code == 201, created.text
    session = created.json()

    signed = client.post(f"/api/v1/sessions/{session['session_id']}/sign")
    assert signed.status_code == 200, signed.text
    return {
        "session": session,
        "signed": signed.json(),
        "message": SESSION_MESSAGE,
        "session_id": session["session_id"],
        "transcript": signed.json()["transcript"],
    }


@pytest.fixture(scope="session")
def expensive_client() -> TestClient:
    """A session-scoped client for the two long-running operations."""
    return TestClient(create_app(settings=TEST_SETTINGS, store=ApiStore()))


@pytest.fixture(scope="session")
def calibration_run(expensive_client: TestClient) -> dict:
    """One small calibration, shared across the calibration tests."""
    response = expensive_client.post(
        "/api/v1/calibration/run",
        json={"state_count": 20, "session_count": 2, "seed_start": 0},
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture(scope="session")
def evaluation_run(expensive_client: TestClient) -> dict:
    """One smoke benchmark run, shared across the evaluation tests."""
    response = expensive_client.post(
        "/api/v1/evaluation/run", json={"profile": "smoke"}
    )
    assert response.status_code == 201, response.text
    return response.json()




NON_SOURCE_DIRS = frozenset(
    {"__pycache__", "htmlcov", "node_modules", "results", "runs", "build", "dist"}
)


SOURCE_SUFFIXES = frozenset(
    {".py", ".md", ".toml", ".txt", ".cfg", ".ini", ".json", ".yaml", ".yml", ".rst"}
)


def repository_text_files() -> list[pathlib.Path]:
    """Every text file in the repository that could carry a shipped reference.

    Used by the guards that assert a retired setting name appears nowhere. Dot
    directories are skipped wholesale -- VCS metadata, caches, the virtualenv,
    git worktrees and the agent workspace -- because none of them is shipped
    source or documentation, and a local scratch file mentioning the name must
    not be able to fail a repository guard.
    """
    root = pathlib.Path(__file__).resolve().parents[2]
    found = []
    for path in root.rglob("*"):
        if any(part.startswith(".") or part in NON_SOURCE_DIRS for part in path.parts):
            continue
        if path.is_file() and path.suffix in SOURCE_SUFFIXES:
            found.append(path)
    return found
