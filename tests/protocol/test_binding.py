"""Tests for the message/session binding.

The decisive property here is that the binding is computed over a *canonically
structured* encoding rather than a concatenation of field values. The
``test_field_boundaries_are_unambiguous`` case is the one that fails for a naive
``version + session_id + nonce + message`` implementation.
"""

from __future__ import annotations

import hashlib

import pytest

from backend.protocol import (
    BINDING_DOMAIN,
    compute_message_binding,
    compute_message_hash,
)
from backend.protocol.binding import binding_preimage

VERSION = "RQDS-TP-1.0"
SESSION_ID = "a" * 32
NONCE = "b" * 64
MESSAGE = "transfer 100 units to account 7"


def _binding(**overrides) -> str:
    kwargs = {
        "protocol_version": VERSION,
        "session_id": SESSION_ID,
        "nonce": NONCE,
        "message": MESSAGE,
    }
    kwargs.update(overrides)
    return compute_message_binding(**kwargs)


def test_binding_is_a_sha256_hex_digest() -> None:
    binding = _binding()
    assert len(binding) == 64
    assert all(character in "0123456789abcdef" for character in binding)


def test_binding_is_deterministic() -> None:
    assert _binding() == _binding()


def test_message_hash_is_sha256_of_the_utf8_message() -> None:
    """Independently recomputed with hashlib, not with the module under test."""
    assert compute_message_hash(MESSAGE) == hashlib.sha256(
        MESSAGE.encode("utf-8")
    ).hexdigest()


def test_binding_differs_from_the_message_hash() -> None:
    assert _binding() != compute_message_hash(MESSAGE)


def test_changing_the_message_changes_the_binding() -> None:
    assert _binding() != _binding(message=MESSAGE + "!")


def test_changing_the_nonce_changes_the_binding() -> None:
    assert _binding() != _binding(nonce="c" * 64)


def test_changing_the_session_id_changes_the_binding() -> None:
    assert _binding() != _binding(session_id="d" * 32)


def test_changing_the_protocol_version_changes_the_binding() -> None:
    assert _binding() != _binding(protocol_version="RQDS-TP-1.1")


def test_field_boundaries_are_unambiguous() -> None:
    """A concatenation implementation would collide on this pair.

    ``("ab", "cd")`` and ``("abc", "d")`` concatenate to the same characters.
    A canonical structured encoding keeps them distinct because every field is
    named and bounded.
    """
    left = _binding(session_id="ab", nonce="cd")
    right = _binding(session_id="abc", nonce="d")
    assert left != right


    left = _binding(nonce="cd", message="ef")
    right = _binding(nonce="cde", message="f")
    assert left != right


def test_binding_preimage_is_canonical_and_self_describing() -> None:
    preimage = binding_preimage(
        protocol_version=VERSION,
        session_id=SESSION_ID,
        nonce=NONCE,
        message=MESSAGE,
    )
    text = preimage.decode("utf-8")
    for field in ("domain", "protocol_version", "session_id", "nonce", "message"):
        assert f'"{field}":' in text
    assert BINDING_DOMAIN in text


    assert '": ' not in text
    assert ', "' not in text
    assert "\n" not in text
    assert text.startswith('{"domain":')


def test_binding_preimage_is_deterministic() -> None:
    first = binding_preimage(
        protocol_version=VERSION, session_id=SESSION_ID, nonce=NONCE, message=MESSAGE
    )
    second = binding_preimage(
        protocol_version=VERSION, session_id=SESSION_ID, nonce=NONCE, message=MESSAGE
    )
    assert first == second


def test_binding_is_domain_separated() -> None:
    """Dropping the domain tag must change the digest."""
    import json

    without_domain = json.dumps(
        {
            "protocol_version": VERSION,
            "session_id": SESSION_ID,
            "nonce": NONCE,
            "message": MESSAGE,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    assert hashlib.sha256(without_domain).hexdigest() != _binding()


def test_message_is_normalised_before_hashing() -> None:
    composed = compute_message_hash("caf\u00e9")
    decomposed = compute_message_hash("cafe\u0301")
    assert composed == decomposed


def test_binding_is_positional_argument_safe() -> None:
    """Every field is keyword-only, so identifiers cannot be silently swapped."""
    with pytest.raises(TypeError):
        compute_message_binding(VERSION, SESSION_ID, NONCE, MESSAGE)  # type: ignore[misc]
