"""Tests for canonical serialization.

The canonical encoding is the foundation of every digest in the protocol, so it
is tested against independently computed expectations rather than against
values the module itself produced.
"""

from __future__ import annotations

import hashlib
import unicodedata

import pytest

from backend.protocol.canonical import (
    CANONICAL_HASH_ALGORITHM,
    CanonicalTypeError,
    canonical_bytes,
    canonical_digest,
    canonical_json,
    hash_bytes,
    is_lowercase_hex,
    normalize_string,
)



GOLDEN_OBJECT = {"b": 2, "a": ["x", 1, True, None], "c": {"z": "\u00e9"}}
GOLDEN_JSON = '{"a":["x",1,true,null],"b":2,"c":{"z":"\u00e9"}}'
GOLDEN_DIGEST = "869b68ef7be7639e4a67501d859a919168bc8a469f98d63b38c5aebd70c2f1c3"


def test_golden_encoding_is_pinned() -> None:
    """The exact bytes of a known object are fixed by this test."""
    assert canonical_json(GOLDEN_OBJECT) == GOLDEN_JSON
    assert canonical_bytes(GOLDEN_OBJECT) == GOLDEN_JSON.encode("utf-8")


def test_golden_digest_matches_an_independent_sha256() -> None:
    """The digest must equal SHA-256 of the pinned byte string."""
    assert canonical_digest(GOLDEN_OBJECT) == GOLDEN_DIGEST
    assert (
        hashlib.sha256(GOLDEN_JSON.encode("utf-8")).hexdigest() == GOLDEN_DIGEST
    )


def test_serialization_is_stable_across_repeated_calls() -> None:
    assert canonical_json(GOLDEN_OBJECT) == canonical_json(GOLDEN_OBJECT)
    assert canonical_digest(GOLDEN_OBJECT) == canonical_digest(GOLDEN_OBJECT)


def test_key_order_is_independent_of_insertion_order() -> None:
    """Semantically equivalent objects must serialize identically."""
    first = {"alpha": 1, "beta": {"y": 2, "x": 3}}
    second = {"beta": {"x": 3, "y": 2}, "alpha": 1}
    assert canonical_json(first) == canonical_json(second)
    assert canonical_digest(first) == canonical_digest(second)


def test_unicode_is_normalised_to_nfc() -> None:
    """A composed and a decomposed spelling must produce identical bytes."""
    composed = "\u00e9"
    decomposed = "e\u0301"
    assert composed != decomposed
    assert normalize_string(composed) == normalize_string(decomposed)
    assert canonical_json({"k": composed}) == canonical_json({"k": decomposed})


def test_non_ascii_is_emitted_as_utf8_not_escaped() -> None:
    text = canonical_json({"k": "\u00e9"})
    assert "\u00e9" in text
    assert "\\u00e9" not in text
    assert text.encode("utf-8") == canonical_bytes({"k": "\u00e9"})


def test_no_insignificant_whitespace() -> None:
    text = canonical_json({"a": 1, "b": [1, 2]})
    assert " " not in text
    assert "\n" not in text


def test_booleans_are_not_serialised_as_integers() -> None:
    assert canonical_json({"v": True}) == '{"v":true}'
    assert canonical_json({"v": 1}) == '{"v":1}'
    assert canonical_json({"v": False}) == '{"v":false}'


def test_none_serialises_as_null() -> None:
    assert canonical_json({"v": None}) == '{"v":null}'


def test_nested_structures_round_trip_stably() -> None:
    value = {"outer": [{"inner": [1, 2, {"deep": "x"}]}], "flag": False}
    assert canonical_json(value) == canonical_json(value)
    assert canonical_bytes(value).decode("utf-8") == canonical_json(value)


@pytest.mark.parametrize("value", [1.0, 0.5, float("inf"), float("nan"), -2.25])
def test_floats_are_rejected(value: float) -> None:
    """The transcript must never carry floating-point values."""
    with pytest.raises(CanonicalTypeError):
        canonical_json({"v": value})


def test_bytes_are_rejected() -> None:
    with pytest.raises(CanonicalTypeError):
        canonical_json({"v": b"raw"})


def test_non_string_keys_are_rejected() -> None:
    with pytest.raises(CanonicalTypeError):
        canonical_json({1: "x"})


@pytest.mark.parametrize("value", [object(), {1, 2}, (x for x in [1])])
def test_unsupported_types_are_rejected(value: object) -> None:
    with pytest.raises(CanonicalTypeError):
        canonical_json({"v": value})


def test_lone_surrogate_is_rejected() -> None:
    with pytest.raises(CanonicalTypeError):
        canonical_json({"v": "\ud800"})


def test_nested_float_is_rejected_with_its_path() -> None:
    with pytest.raises(CanonicalTypeError) as excinfo:
        canonical_json({"outer": {"inner": [1, 2.5]}})
    assert "outer.inner[1]" in str(excinfo.value)


def test_hash_bytes_rejects_non_sha256_algorithm() -> None:
    with pytest.raises(ValueError):
        hash_bytes(b"x", algorithm="md5")


def test_hash_bytes_rejects_non_bytes() -> None:
    with pytest.raises(CanonicalTypeError):
        hash_bytes("x")  # type: ignore[arg-type]


def test_hash_bytes_matches_hashlib() -> None:
    assert hash_bytes(b"abc") == hashlib.sha256(b"abc").hexdigest()


def test_only_sha256_is_advertised() -> None:
    assert CANONICAL_HASH_ALGORITHM == "sha256"


@pytest.mark.parametrize(
    "value,expected",
    [("abc123", True), ("0" * 64, True), ("ABC", False), ("", False), ("xy", False)],
)
def test_is_lowercase_hex(value: str, expected: bool) -> None:
    assert is_lowercase_hex(value) is expected


def test_normalize_string_rejects_non_strings() -> None:
    with pytest.raises(CanonicalTypeError):
        normalize_string(5)  # type: ignore[arg-type]


def test_normalization_is_idempotent() -> None:
    text = "cafe\u0301 \u00e9t\u00e9"
    once = normalize_string(text)
    assert normalize_string(once) == once
    assert unicodedata.is_normalized("NFC", once)
