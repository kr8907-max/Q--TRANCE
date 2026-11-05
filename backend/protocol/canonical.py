"""Deterministic canonical serialization for the reference QDS protocol.

Every integrity property of this protocol is a statement about **bytes**: the
message binding, the state-sequence derivation and the transcript hash are all
digests of byte strings. Those byte strings therefore have to be reproducible
across runs, machines, locales and Python builds. This module defines exactly
one canonical encoding and nothing else, so there is a single place to audit.

Normative encoding
------------------
``canonical_json(obj)`` produces a ``str`` by:

1. Recursively normalising every ``str`` to Unicode **NFC** and rejecting
   strings containing lone surrogates or anything that will not encode as
   UTF-8. Two visually identical strings with different composition sequences
   therefore produce identical bytes.
2. Accepting only ``None``, ``bool``, ``int``, ``str``, ``list``/``tuple`` and
   ``dict`` with ``str`` keys. Every other type is rejected.
   ``float`` is rejected **on purpose**: the transcript must never carry
   floating-point amplitudes or tolerances, so there is no question of float
   formatting drifting between platforms.
3. Serialising with ``json.dumps(..., sort_keys=True,
   separators=(",", ":"), ensure_ascii=False, allow_nan=False)``.

``sort_keys=True`` orders object keys by Unicode code point, which is
locale-independent and stable. The compact separators remove every byte of
insignificant whitespace. ``ensure_ascii=False`` emits non-ASCII characters as
UTF-8 rather than ``\\uXXXX`` escapes; together with NFC normalisation that
makes the byte stream stable.

``canonical_bytes(obj)`` is ``canonical_json(obj).encode("utf-8")`` and
``canonical_digest(obj)`` is the lowercase hex SHA-256 of those bytes.

Nothing in this module hashes ``repr()`` output, uses ``pickle``, or evaluates
data as code.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from typing import Any, Dict

__all__ = [
    "CANONICAL_HASH_ALGORITHM",
    "CanonicalTypeError",
    "normalize_string",
    "canonical_json",
    "canonical_bytes",
    "canonical_digest",
    "hash_bytes",
    "is_lowercase_hex",
]


CANONICAL_HASH_ALGORITHM = "sha256"

_HEX_DIGITS = frozenset("0123456789abcdef")


class CanonicalTypeError(TypeError):
    """Raised when a value cannot be given a canonical representation."""


def normalize_string(value: str) -> str:
    """Return ``value`` in NFC form, rejecting lone surrogates.

    NFC is the canonical composition form: it guarantees that two textually
    equivalent inputs (for example ``"é"`` written as one code point versus
    ``"e" + U+0301``) normalise to the same byte sequence.
    """
    if not isinstance(value, str):
        raise CanonicalTypeError(f"expected str, got {type(value).__name__}")
    normalized = unicodedata.normalize("NFC", value)
    try:
        normalized.encode("utf-8")
    except UnicodeEncodeError as exc:  # pragma: no cover - defensive
        raise CanonicalTypeError(f"string is not UTF-8 encodable: {value!r}") from exc
    return normalized


def _normalize(value: Any, path: str) -> Any:
    if value is None:
        return None

    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return normalize_string(value)
    if isinstance(value, (list, tuple)):
        return [_normalize(item, f"{path}[{index}]") for index, item in enumerate(value)]
    if isinstance(value, dict):
        result: Dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalTypeError(
                    f"canonical object keys must be str, got "
                    f"{type(key).__name__} at {path}"
                )
            normalized_key = normalize_string(key)
            if normalized_key in result:
                raise CanonicalTypeError(
                    f"duplicate key {normalized_key!r} after NFC normalisation at {path}"
                )
            result[normalized_key] = _normalize(item, f"{path}.{normalized_key}")
        return result
    if isinstance(value, float):
        raise CanonicalTypeError(
            f"float is not canonically serialisable at {path}: the transcript "
            f"must carry integers and strings only (see "
            f"docs/protocol/reference-qds.md)"
        )
    if isinstance(value, (bytes, bytearray)):
        raise CanonicalTypeError(
            f"bytes are not canonically serialisable at {path}: use a lowercase "
            f"hex string instead"
        )
    raise CanonicalTypeError(
        f"unsupported canonical type {type(value).__name__} at {path}"
    )


def canonical_json(obj: Any) -> str:
    """Return the canonical JSON text for ``obj``."""
    return json.dumps(
        _normalize(obj, "$"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def canonical_bytes(obj: Any) -> bytes:
    """Return the canonical UTF-8 byte encoding of ``obj``."""
    return canonical_json(obj).encode("utf-8")


def hash_bytes(data: bytes, algorithm: str = CANONICAL_HASH_ALGORITHM) -> str:
    """Return the lowercase hex digest of ``data``.

    The exact bytes hashed are always supplied by the caller, so every digest
    in this package can be traced to an explicit preimage.
    """
    if algorithm != CANONICAL_HASH_ALGORITHM:
        raise ValueError(
            f"unsupported hash algorithm {algorithm!r}; "
            f"this protocol layer uses {CANONICAL_HASH_ALGORITHM!r}"
        )
    if not isinstance(data, (bytes, bytearray)):
        raise CanonicalTypeError(
            f"hash_bytes expects bytes, got {type(data).__name__}"
        )
    return hashlib.new(algorithm, bytes(data)).hexdigest()


def canonical_digest(obj: Any, algorithm: str = CANONICAL_HASH_ALGORITHM) -> str:
    """Return the lowercase hex digest of ``canonical_bytes(obj)``."""
    return hash_bytes(canonical_bytes(obj), algorithm=algorithm)


def is_lowercase_hex(value: str) -> bool:
    """Return ``True`` when ``value`` is a non-empty lowercase hex string."""
    return bool(value) and all(character in _HEX_DIGITS for character in value)
