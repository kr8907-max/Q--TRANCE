"""Message/session binding for the reference QDS protocol.

What is hashed
--------------
``compute_message_hash(message)`` is the SHA-256 of the UTF-8 encoding of the
NFC-normalised message text, and nothing else::

    message_hash = SHA256( utf8( NFC(message) ) )

``compute_message_binding(...)`` commits to the protocol version, the session
identifier, the nonce and the raw message. The preimage is the *canonical
structured encoding* of a keyed object, not a concatenation::

    message_binding = SHA256( canonical_bytes({
        "domain"           : "rqds-tp-1.0/message-binding",
        "protocol_version" : <protocol_version>,
        "session_id"       : <session_id>,
        "nonce"            : <nonce>,
        "message"          : <message>,
    }) )

Why not concatenate
-------------------
Plain concatenation of ``str(protocol_version) + str(session_id) + nonce +
message`` is ambiguous: different tuples can produce the same byte string, so
an attacker could move characters between fields without changing the binding.
The canonical object encoding gives every field an explicit name and an
explicit boundary (JSON quoting plus the compact ``key:value`` framing), and
``sort_keys=True`` fixes the field order.

The ``domain`` field is a domain-separation tag. It ensures that a binding
digest can never collide with a digest computed for a different purpose from
the same field values.

Determinism
-----------
The binding is a pure function of its arguments: no clock, no randomness, no
global state. Equal inputs always give equal bindings.
"""

from __future__ import annotations

from backend.protocol.canonical import canonical_bytes, hash_bytes, normalize_string

__all__ = [
    "BINDING_DOMAIN",
    "compute_message_hash",
    "binding_preimage",
    "compute_message_binding",
]


BINDING_DOMAIN = "rqds-tp-1.0/message-binding"


def compute_message_hash(message: str) -> str:
    """Return the SHA-256 of the UTF-8 bytes of the NFC-normalised message."""
    return hash_bytes(normalize_string(message).encode("utf-8"))


def binding_preimage(
    *,
    protocol_version: str,
    session_id: str,
    nonce: str,
    message: str,
) -> bytes:
    """Return the exact byte string that :func:`compute_message_binding` hashes."""
    return canonical_bytes(
        {
            "domain": BINDING_DOMAIN,
            "protocol_version": protocol_version,
            "session_id": session_id,
            "nonce": nonce,
            "message": message,
        }
    )


def compute_message_binding(
    *,
    protocol_version: str,
    session_id: str,
    nonce: str,
    message: str,
) -> str:
    """Return the lowercase hex SHA-256 message binding.

    Every field is keyword-only, so a caller cannot silently swap the
    ``session_id`` and ``nonce`` arguments.
    """
    return hash_bytes(
        binding_preimage(
            protocol_version=protocol_version,
            session_id=session_id,
            nonce=nonce,
            message=message,
        )
    )
