"""Shared fixtures for the M2 protocol tests.

Signing runs the M1 teleportation engine once per state, which is
transpile-dominated at roughly 0.15 s per state. The fixtures below therefore
sign **once per session** at a small state count and let tests deep-copy the
transcript data when they need to tamper with it. A separate test exercises the
full default configuration.
"""

from __future__ import annotations

import copy
from typing import Any, Dict

import pytest

from backend.protocol import (
    SigningResult,
    Transcript,
    create_session,
    sign,
    transcript_to_dict,
)

MESSAGE = "transfer 100 units to account 7"
OTHER_MESSAGE = "transfer 999 units to account 7"
SIGNER_ID = "alice"
VERIFIER_ID = "bob"
SESSION_ID = "a" * 32
NONCE = "b" * 64
CREATED_AT = "2026-09-12T17:00:00+00:00"
STATE_COUNT = 4


@pytest.fixture(scope="session")
def message() -> str:
    return MESSAGE


@pytest.fixture(scope="session")
def session():
    """A deterministic session: identifiers and clock are injected."""
    return create_session(
        MESSAGE,
        signer_id=SIGNER_ID,
        verifier_id=VERIFIER_ID,
        state_count=STATE_COUNT,
        session_id_factory=lambda: SESSION_ID,
        nonce_factory=lambda: NONCE,
        clock=lambda: CREATED_AT,
    )


@pytest.fixture(scope="session")
def signed(session) -> SigningResult:
    return sign(
        MESSAGE,
        signer_id=SIGNER_ID,
        verifier_id=VERIFIER_ID,
        state_count=STATE_COUNT,
        session=session,
    )


@pytest.fixture(scope="session")
def transcript(signed) -> Transcript:
    return signed.transcript


@pytest.fixture(scope="session")
def transcript_data(transcript) -> Dict[str, Any]:
    """The transcript as plain data. Callers must copy before mutating."""
    return transcript_to_dict(transcript)


@pytest.fixture
def mutable_transcript(transcript_data) -> Dict[str, Any]:
    """A fresh deep copy of the transcript data, safe to mutate."""
    return copy.deepcopy(transcript_data)
