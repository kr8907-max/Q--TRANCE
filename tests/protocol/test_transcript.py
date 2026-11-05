"""Tests for transcript construction, hashing, serialization and validation."""

from __future__ import annotations

import copy
import json

import pytest

from backend.protocol import (
    STATE_ALPHABET,
    TRANSCRIPT_VERSION,
    TranscriptValidationError,
    compute_transcript_hash,
    is_transcript_hash_valid,
    transcript_from_dict,
    transcript_from_json,
    transcript_to_json,
)
from backend.protocol.transcript import TRANSCRIPT_FIELDS


MUTATIONS = {
    "transcript_version": 2,
    "protocol_version": "RQDS-TP-1.1",
    "session_id": "c" * 32,
    "nonce": "d" * 64,
    "created_at": "2026-09-12T18:30:00+00:00",
    "message_hash": "1" * 64,
    "message_binding": "2" * 64,
    "signer_id": "carol",
    "verifier_id": "dave",
    "state_count": 5,
    "state_sequence_metadata": {"derivation": "other"},
    "states": None,
    "teleportation_branches": None,
    "verification_metadata": {"basis_policy": "other"},
}


def _mutated(transcript_data: dict, field: str) -> dict:
    data = copy.deepcopy(transcript_data)
    if field == "states":
        replacement = dict(data["states"][0])
        replacement["state_identifier"] = next(
            identifier
            for identifier in STATE_ALPHABET
            if identifier != data["states"][0]["state_identifier"]
        )
        data["states"][0] = replacement
    elif field == "teleportation_branches":
        data["teleportation_branches"][0]["m0"] = (
            1 - data["teleportation_branches"][0]["m0"]
        )
    else:
        data[field] = MUTATIONS[field]
    return data







def test_transcript_has_every_documented_field(transcript_data) -> None:
    assert set(transcript_data) == set(TRANSCRIPT_FIELDS)


def test_transcript_version_is_current(transcript) -> None:
    assert transcript.transcript_version == TRANSCRIPT_VERSION


def test_hash_is_a_sha256_hex_digest(transcript) -> None:
    assert len(transcript.transcript_hash) == 64
    assert all(character in "0123456789abcdef" for character in transcript.transcript_hash)


def test_fresh_transcript_hash_is_valid(transcript) -> None:
    assert is_transcript_hash_valid(transcript)


def test_hash_is_deterministic(transcript) -> None:
    assert transcript.transcript_hash == compute_transcript_hash(transcript.payload())


def test_hash_covers_every_top_level_field(transcript, transcript_data) -> None:
    """Mutating any single field must change the transcript hash."""
    original = transcript.transcript_hash
    for field in sorted(TRANSCRIPT_FIELDS - {"transcript_hash"}):
        mutated = _mutated(transcript_data, field)
        mutated.pop("transcript_hash")
        assert compute_transcript_hash(mutated) != original, field







def test_serialization_is_stable_across_repeated_calls(transcript) -> None:
    assert transcript_to_json(transcript) == transcript_to_json(transcript)


def test_serialization_is_byte_stable(transcript) -> None:
    assert transcript_to_json(transcript).encode("utf-8") == transcript_to_json(
        transcript
    ).encode("utf-8")


def test_round_trip_preserves_the_transcript(transcript) -> None:
    restored = transcript_from_json(transcript_to_json(transcript))
    assert restored == transcript


def test_re_serialization_after_round_trip_is_identical(transcript) -> None:
    text = transcript_to_json(transcript)
    restored = transcript_from_json(text)
    assert transcript_to_json(restored) == text


def test_from_dict_round_trip(transcript, transcript_data) -> None:
    assert transcript_from_dict(copy.deepcopy(transcript_data)) == transcript


def test_serialized_transcript_contains_no_floats(transcript) -> None:
    """The transcript schema admits integers and strings only."""

    def assert_no_floats(value, path="$"):
        assert not isinstance(value, float), path
        if isinstance(value, dict):
            for key, item in value.items():
                assert_no_floats(item, f"{path}.{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                assert_no_floats(item, f"{path}[{index}]")

    assert_no_floats(json.loads(transcript_to_json(transcript)))


def test_serialization_does_not_embed_amplitudes(transcript) -> None:
    """States are symbolic identifiers, never amplitude vectors."""
    text = transcript_to_json(transcript)
    assert "state_identifier" in text
    assert "0.7071" not in text
    assert "amplitude" not in text
    assert "vector" not in text


def test_unknown_field_is_rejected(transcript_data) -> None:
    data = copy.deepcopy(transcript_data)
    data["extra_field"] = 1
    with pytest.raises(TranscriptValidationError):
        transcript_from_dict(data)


@pytest.mark.parametrize("field", sorted(TRANSCRIPT_FIELDS))
def test_missing_field_is_rejected(transcript_data, field: str) -> None:
    data = copy.deepcopy(transcript_data)
    del data[field]
    with pytest.raises(TranscriptValidationError):
        transcript_from_dict(data)


def test_non_object_is_rejected() -> None:
    for bad in ([], "text", 5, None):
        with pytest.raises(TranscriptValidationError):
            transcript_from_dict(bad)


def test_invalid_json_is_rejected() -> None:
    with pytest.raises(TranscriptValidationError):
        transcript_from_json("{not json")


def test_non_string_json_is_rejected() -> None:
    with pytest.raises(TranscriptValidationError):
        transcript_from_json({"already": "parsed"})  # type: ignore[arg-type]


def test_json_scalar_is_rejected() -> None:
    with pytest.raises(TranscriptValidationError):
        transcript_from_json("42")







@pytest.mark.parametrize("bad_version", [0, 99, -1, "1", None, True])
def test_unsupported_transcript_version_is_rejected(transcript_data, bad_version) -> None:
    data = copy.deepcopy(transcript_data)
    data["transcript_version"] = bad_version
    with pytest.raises(TranscriptValidationError):
        transcript_from_dict(data)


@pytest.mark.parametrize("bad", ["", "1.0", "RQDS-TP-1", 5])
def test_malformed_protocol_version_is_rejected(transcript_data, bad) -> None:
    data = copy.deepcopy(transcript_data)
    data["protocol_version"] = bad
    with pytest.raises(TranscriptValidationError):
        transcript_from_dict(data)


@pytest.mark.parametrize("field", ["session_id", "nonce", "message_hash", "message_binding", "transcript_hash"])
@pytest.mark.parametrize("bad", ["", "zz", "A" * 64, "0" * 10, 5, None])
def test_malformed_hex_fields_are_rejected(transcript_data, field: str, bad) -> None:
    data = copy.deepcopy(transcript_data)
    data[field] = bad
    with pytest.raises(TranscriptValidationError):
        transcript_from_dict(data)


@pytest.mark.parametrize("bad", ["", "with space", "!!", "a" * 129])
def test_malformed_identifiers_are_rejected(transcript_data, bad: str) -> None:
    for field in ("signer_id", "verifier_id"):
        data = copy.deepcopy(transcript_data)
        data[field] = bad
        with pytest.raises(TranscriptValidationError):
            transcript_from_dict(data)


@pytest.mark.parametrize("bad", ["2026-01-02 03:04:05", "2026-01-02T03:04:05", "now", 5])
def test_malformed_created_at_is_rejected(transcript_data, bad) -> None:
    data = copy.deepcopy(transcript_data)
    data["created_at"] = bad
    with pytest.raises(TranscriptValidationError):
        transcript_from_dict(data)


@pytest.mark.parametrize("bad", [0, -1, True, 1.5, "4", 10_000])
def test_malformed_state_count_is_rejected(transcript_data, bad) -> None:
    data = copy.deepcopy(transcript_data)
    data["state_count"] = bad
    with pytest.raises(TranscriptValidationError):
        transcript_from_dict(data)


def test_state_count_must_match_the_state_list(transcript_data) -> None:
    data = copy.deepcopy(transcript_data)
    data["state_count"] = len(data["states"]) + 1
    with pytest.raises(TranscriptValidationError):
        transcript_from_dict(data)


def test_sequence_metadata_must_match_state_count(transcript_data) -> None:
    data = copy.deepcopy(transcript_data)
    data["state_sequence_metadata"] = {
        **data["state_sequence_metadata"],
        "state_count": 99,
    }
    with pytest.raises(TranscriptValidationError):
        transcript_from_dict(data)


def test_sequence_metadata_alphabet_is_pinned(transcript_data) -> None:
    data = copy.deepcopy(transcript_data)
    data["state_sequence_metadata"] = {
        **data["state_sequence_metadata"],
        "alphabet": ["A"],
    }
    with pytest.raises(TranscriptValidationError):
        transcript_from_dict(data)


def test_sequence_metadata_unknown_field_is_rejected(transcript_data) -> None:
    data = copy.deepcopy(transcript_data)
    data["state_sequence_metadata"] = {
        **data["state_sequence_metadata"],
        "extra": 1,
    }
    with pytest.raises(TranscriptValidationError):
        transcript_from_dict(data)


def test_verification_metadata_type_is_validated(transcript_data) -> None:
    data = copy.deepcopy(transcript_data)
    data["verification_metadata"] = {"x": [1, 2]}
    with pytest.raises(TranscriptValidationError):
        transcript_from_dict(data)


def test_states_must_be_a_list(transcript_data) -> None:
    data = copy.deepcopy(transcript_data)
    data["states"] = "x"
    with pytest.raises(TranscriptValidationError):
        transcript_from_dict(data)


def test_states_length_must_match(transcript_data) -> None:
    data = copy.deepcopy(transcript_data)
    data["states"] = data["states"][:-1]
    with pytest.raises(TranscriptValidationError):
        transcript_from_dict(data)


def test_state_index_must_match_position(transcript_data) -> None:
    data = copy.deepcopy(transcript_data)
    data["states"][1] = {**data["states"][1], "index": 7}
    with pytest.raises(TranscriptValidationError):
        transcript_from_dict(data)


def test_state_identifier_must_be_known(transcript_data) -> None:
    data = copy.deepcopy(transcript_data)
    data["states"][0] = {**data["states"][0], "state_identifier": "Q+"}
    with pytest.raises(TranscriptValidationError):
        transcript_from_dict(data)


def test_state_basis_must_be_known(transcript_data) -> None:
    data = copy.deepcopy(transcript_data)
    data["states"][0] = {**data["states"][0], "basis": "W"}
    with pytest.raises(TranscriptValidationError):
        transcript_from_dict(data)


def test_state_eigenvalue_must_be_a_sign(transcript_data) -> None:
    data = copy.deepcopy(transcript_data)
    data["states"][0] = {**data["states"][0], "eigenvalue": 0}
    with pytest.raises(TranscriptValidationError):
        transcript_from_dict(data)


def test_state_label_must_be_known(transcript_data) -> None:
    data = copy.deepcopy(transcript_data)
    data["states"][0] = {**data["states"][0], "label": "|x>"}
    with pytest.raises(TranscriptValidationError):
        transcript_from_dict(data)


def test_state_fields_must_be_mutually_consistent(transcript_data) -> None:
    """A valid identifier that contradicts the label is still rejected.

    Every field is individually well formed here, so only the mutual
    consistency rule can catch it.
    """
    data = copy.deepcopy(transcript_data)
    current = data["states"][0]["state_identifier"]
    data["states"][0] = {
        **data["states"][0],
        "state_identifier": next(
            identifier for identifier in STATE_ALPHABET if identifier != current
        ),
    }
    with pytest.raises(TranscriptValidationError):
        transcript_from_dict(data)


def test_state_unknown_field_is_rejected(transcript_data) -> None:
    data = copy.deepcopy(transcript_data)
    data["states"][0] = {**data["states"][0], "extra": 1}
    with pytest.raises(TranscriptValidationError):
        transcript_from_dict(data)


def test_branches_must_be_a_list(transcript_data) -> None:
    data = copy.deepcopy(transcript_data)
    data["teleportation_branches"] = "x"
    with pytest.raises(TranscriptValidationError):
        transcript_from_dict(data)


def test_branches_length_must_match(transcript_data) -> None:
    data = copy.deepcopy(transcript_data)
    data["teleportation_branches"] = data["teleportation_branches"][:-1]
    with pytest.raises(TranscriptValidationError):
        transcript_from_dict(data)


@pytest.mark.parametrize("bad", [2, -1, True, 0.5, "1"])
def test_branch_bits_must_be_binary(transcript_data, bad) -> None:
    data = copy.deepcopy(transcript_data)
    data["teleportation_branches"][0]["m0"] = bad
    with pytest.raises(TranscriptValidationError):
        transcript_from_dict(data)


def test_branch_index_must_match_position(transcript_data) -> None:
    data = copy.deepcopy(transcript_data)
    data["teleportation_branches"][2]["index"] = 9
    with pytest.raises(TranscriptValidationError):
        transcript_from_dict(data)
