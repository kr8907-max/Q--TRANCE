"""Tests for the reference state-sequence derivation.

Two properties matter most: the mapping is *deterministic* (same binding always
gives the same sequence) and *unbiased* (each of the six states is equally
likely, which a naive ``byte mod 6`` would not achieve).
"""

from __future__ import annotations

import hashlib

import pytest

from backend.protocol import (
    ALPHABET_SIZE,
    STATE_ALPHABET,
    STREAM_DOMAIN,
    ProtocolValidationError,
    SignatureState,
    derive_alphabet_indices,
    derive_state_sequence,
    sequence_metadata,
    state_for_identifier,
)
from backend.protocol.encoding import (
    NIBBLE_ACCEPT_LIMIT,
    nibble_stream,
)
from backend.quantum.states import EIGENSTATE_LABELS, get_eigenstate

from tests.quantum.statutil import assert_expected_probability

BINDING_A = "0" * 64
BINDING_B = "f" * 64
BINDING_C = "0123456789abcdef" * 4


def test_alphabet_matches_the_verified_quantum_core() -> None:
    """The alphabet must be exactly the six M1 Pauli eigenstates."""
    assert ALPHABET_SIZE == 6
    assert len(set(STATE_ALPHABET)) == 6
    for label in EIGENSTATE_LABELS:
        state = get_eigenstate(label)
        expected = f"{state.basis}{'+' if state.eigenvalue > 0 else '-'}"
        assert expected in STATE_ALPHABET
    assert set(STATE_ALPHABET) == {"Z+", "Z-", "X+", "X-", "Y+", "Y-"}


def test_alphabet_order_is_the_core_order() -> None:
    assert STATE_ALPHABET == ("Z+", "Z-", "X+", "X-", "Y+", "Y-")


@pytest.mark.parametrize("identifier", STATE_ALPHABET)
def test_state_for_identifier_is_consistent(identifier: str) -> None:
    state = state_for_identifier(identifier)
    core = get_eigenstate(state.label)
    assert state.basis == core.basis
    assert state.eigenvalue == int(core.eigenvalue)
    assert identifier == f"{core.basis}{'+' if core.eigenvalue > 0 else '-'}"


@pytest.mark.parametrize("bad", ["", "Q+", "Z0", "z+", "Z+ ", "ZZ"])
def test_unknown_identifier_is_rejected(bad: str) -> None:
    with pytest.raises(ProtocolValidationError):
        state_for_identifier(bad)


def test_derivation_is_deterministic() -> None:
    first = derive_state_sequence(BINDING_C, 40)
    second = derive_state_sequence(BINDING_C, 40)
    assert first == second
    assert derive_alphabet_indices(BINDING_C, 40) == derive_alphabet_indices(
        BINDING_C, 40
    )


def test_derivation_has_the_requested_length() -> None:
    for count in (1, 2, 7, 16, 33):
        assert len(derive_state_sequence(BINDING_C, count)) == count


def test_indices_are_sequential_and_identifiers_valid() -> None:
    sequence = derive_state_sequence(BINDING_C, 32)
    for position, state in enumerate(sequence):
        assert state.index == position
        assert state.state_identifier in STATE_ALPHABET
        assert state.label in EIGENSTATE_LABELS
        assert state.eigenvalue in (1, -1)


def test_different_bindings_give_different_sequences() -> None:
    """Not a proof of randomness, but the three fixed bindings must diverge."""
    a = derive_alphabet_indices(BINDING_A, 24)
    b = derive_alphabet_indices(BINDING_B, 24)
    c = derive_alphabet_indices(BINDING_C, 24)
    assert len({a, b, c}) == 3


def test_prefix_of_a_longer_sequence_is_stable() -> None:
    """Deriving fewer states must give the same prefix."""
    long_sequence = derive_alphabet_indices(BINDING_C, 40)
    short_sequence = derive_alphabet_indices(BINDING_C, 10)
    assert long_sequence[:10] == short_sequence


def test_nibble_stream_matches_an_independent_sha256() -> None:
    """The stream is counter-mode SHA-256 with a domain tag; recomputed here."""
    seed = bytes.fromhex(BINDING_C)
    first_block = hashlib.sha256(
        seed + STREAM_DOMAIN.encode("utf-8") + (0).to_bytes(4, "big")
    ).digest()
    second_block = hashlib.sha256(
        seed + STREAM_DOMAIN.encode("utf-8") + (1).to_bytes(4, "big")
    ).digest()

    def nibbles(block: bytes) -> list[int]:
        out = []
        for byte in block:
            out.append(byte >> 4)
            out.append(byte & 0x0F)
        return out

    stream = nibble_stream(seed)
    produced = [next(stream) for _ in range(128)]
    assert produced == nibbles(first_block) + nibbles(second_block)


def test_rejection_limit_is_two_full_alphabet_cycles() -> None:
    """``NIBBLE_ACCEPT_LIMIT == 2 * 6`` is what makes the mapping unbiased."""
    assert NIBBLE_ACCEPT_LIMIT == 2 * ALPHABET_SIZE == 12
    assert 16 % ALPHABET_SIZE == 4


def test_accepted_nibbles_cover_each_state_exactly_twice() -> None:
    counts = [0] * ALPHABET_SIZE
    for nibble in range(NIBBLE_ACCEPT_LIMIT):
        counts[nibble % ALPHABET_SIZE] += 1
    assert counts == [2] * ALPHABET_SIZE


def test_long_sequence_is_statistically_consistent_with_uniform() -> None:
    """Each of the six states must appear with probability 1/6.

    Uses M1's exact Clopper-Pearson helper, so the tolerance is justified
    rather than an arbitrary band.
    """
    count = 6000
    indices = derive_alphabet_indices(BINDING_C, count)
    assert len(indices) == count
    for index in range(ALPHABET_SIZE):
        successes = sum(1 for value in indices if value == index)
        assert_expected_probability(successes, count, 1.0 / ALPHABET_SIZE)


def test_derivation_has_no_hidden_global_state() -> None:
    """Interleaving derivations must not affect each other."""
    expected_a = derive_alphabet_indices(BINDING_A, 12)
    expected_b = derive_alphabet_indices(BINDING_B, 12)
    _ = derive_alphabet_indices(BINDING_C, 50)
    assert derive_alphabet_indices(BINDING_A, 12) == expected_a
    assert derive_alphabet_indices(BINDING_B, 12) == expected_b


@pytest.mark.parametrize(
    "bad_binding",
    ["", "0" * 63, "0" * 65, "A" * 64, "z" * 64, 5, None],
)
def test_malformed_binding_is_rejected(bad_binding) -> None:
    with pytest.raises(ProtocolValidationError):
        derive_alphabet_indices(bad_binding, 4)


@pytest.mark.parametrize("bad_count", [0, -1, True, 1.5, "4"])
def test_malformed_count_is_rejected(bad_count) -> None:
    with pytest.raises(ProtocolValidationError):
        derive_alphabet_indices(BINDING_C, bad_count)


def test_nibble_stream_rejects_non_bytes() -> None:
    with pytest.raises(ProtocolValidationError):
        next(nibble_stream("not bytes"))  # type: ignore[arg-type]


def test_sequence_metadata_describes_but_does_not_contain_the_sequence() -> None:
    metadata = sequence_metadata(16, binding=BINDING_C)
    assert metadata["derivation"] == "sha256-counter-mode-nibble-rejection"
    assert metadata["stream_domain"] == STREAM_DOMAIN
    assert metadata["alphabet"] == list(STATE_ALPHABET)
    assert metadata["alphabet_size"] == ALPHABET_SIZE
    assert metadata["nibble_accept_limit"] == NIBBLE_ACCEPT_LIMIT
    assert metadata["state_count"] == 16
    assert metadata["binding_digest_length"] == 64

    assert "states" not in metadata
    assert "indices" not in metadata


def test_sequence_is_a_tuple_of_signature_states() -> None:
    sequence = derive_state_sequence(BINDING_C, 3)
    assert isinstance(sequence, tuple)
    assert all(isinstance(state, SignatureState) for state in sequence)
