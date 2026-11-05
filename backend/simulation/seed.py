"""Deterministic seed derivation for reproducible experiments.

Two kinds of randomness, kept apart
-----------------------------------
This project has two independent sources of randomness and they must never be
mixed:

======================================  ===================================
cryptographic protocol randomness       simulation randomness
======================================  ===================================
``session_id``, ``nonce``               channel sampling, attack sampling,
                                        measurement sampling
``backend.protocol.session``            this module
``secrets`` (OS CSPRNG)                 explicit master seed
unpredictable, *not* reproducible       reproducible on purpose
======================================  ===================================

A scenario therefore has a ``random_seed`` that controls the *simulation*, and
may separately pin ``session_id`` / ``nonce`` when a caller wants a fully
reproducible transcript. Pinning them is a simulation convenience; it is not a
statement about how a real deployment obtains its identifiers.

No global state
---------------
Nothing here touches ``numpy.random``'s global generator or the ``random``
module. Every stochastic component is handed its own
:class:`numpy.random.Generator` built from an explicitly derived sub-seed, so
two scenarios cannot influence each other's stream and reordering work cannot
change a result.
"""

from __future__ import annotations

import hashlib
from typing import Any

import numpy as np

from backend.protocol.canonical import canonical_bytes

__all__ = [
    "SEED_DOMAIN",
    "MAX_SEED",
    "validate_master_seed",
    "derive_seed",
    "generator",
]


SEED_DOMAIN = "sih26141/simulation-seed"



MAX_SEED = 2**63 - 1


def validate_master_seed(value: Any, label: str = "random_seed") -> int:
    """Return ``value`` as a non-negative integer master seed."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer, got {type(value).__name__}")
    if value < 0:
        raise ValueError(f"{label} must be non-negative, got {value}")
    return value


def derive_seed(master_seed: int, *labels: str) -> int:
    """Return a deterministic sub-seed for ``(master_seed, labels)``.

    The derivation is a SHA-256 over the canonical encoding of the master seed
    and the labels, truncated to 63 bits. It reuses the protocol layer's
    canonical encoder, which accepts integers and strings only -- so there is no
    question of a floating-point rendering drifting between platforms and
    silently changing a seed.

    Labels give each stochastic component its own stream::

        derive_seed(7, "attack", "intercept_resend")
        derive_seed(7, "measurement", "state", "3")
    """
    validate_master_seed(master_seed, "master_seed")
    if not all(isinstance(label, str) for label in labels):
        raise ValueError("seed labels must all be strings")
    payload = canonical_bytes(
        {
            "domain": SEED_DOMAIN,
            "master_seed": int(master_seed),
            "labels": list(labels),
        }
    )
    digest = hashlib.sha256(payload).digest()
    return int.from_bytes(digest[:8], "big") % (MAX_SEED + 1)


def generator(master_seed: int, *labels: str) -> np.random.Generator:
    """Return an independent generator for ``(master_seed, labels)``."""
    return np.random.default_rng(derive_seed(master_seed, *labels))
