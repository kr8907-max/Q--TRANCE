"""Transcript and session integrity: protocol-structure evidence.

Scope
-----
These checks are **protocol integrity findings**, not quantum findings. An
invalid transcript hash, a broken message binding, an unexpected protocol
version, a state count that disagrees with the declared state list, or a
declared state sequence that the verifier's own derivation contradicts -- all of
these are properties of the artifact and of the protocol, and none of them is
evidence about a qubit. They are never reported as a quantum attack.

The detector recomputes everything it can
-----------------------------------------
It does not trust ``transcript_hash``: it recomputes the canonical digest from
the declared payload and compares. It does not trust ``message_binding``: it
recomputes it from ``protocol_version``, ``session_id``, ``nonce`` and the
message the verifier holds. It does not trust the declared state sequence: it
derives the sequence itself from the binding it recomputed, exactly as the
Milestone 2 verifier does.

This mirrors the verifier deliberately. Where the verifier *rejects*, the
detector *explains*, and the two must not disagree about the facts.

Safety under malformed input
----------------------------
Every parse step is guarded. A payload that is not an object, a binding that is
not a hex digest, a state list of the wrong shape -- each produces a recorded
violation or an "unavailable" result. This module never raises on untrusted
data, because malformed evidence is a finding to be reported, not an exception
to be thrown at the caller.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Tuple

from backend.detection.models import DEFAULT_PROTOCOL_VERSIONS, ObservableDetectionInput

__all__ = ["ConsistencyReport", "analyse_consistency"]


@dataclass(frozen=True)
class ConsistencyReport:
    """The protocol-integrity facts the detector established for one session."""

    transcript_supplied: bool
    transcript_parse_ok: bool
    parse_error: str | None

    transcript_hash_valid: bool | None
    declared_transcript_hash: str | None
    recomputed_transcript_hash: str | None

    message_binding_valid: bool | None
    declared_message_binding: str | None
    recomputed_message_binding: str | None

    protocol_version_valid: bool | None
    observed_protocol_version: str | None
    expected_protocol_versions: Tuple[str, ...]

    session_addressing_valid: bool | None
    transcript_verifier_id: str | None
    verifier_context_id: str | None

    state_count_declared: int | None
    state_count_declared_matches_list: bool | None
    state_count_declared_matches_observed: bool | None

    state_sequence_metadata_consistent: bool | None
    declared_state_sequence_matches_derivation: bool | None

    violations: Tuple[str, ...] = ()
    notes: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def protocol_valid(self) -> bool:
        """Return whether every blocking protocol-integrity check passed.

        A check that could not be performed (``None``) does not by itself make
        the session invalid; it is reported as unavailable. Only a definite
        failure counts.
        """
        return not self.violations

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transcript_supplied": self.transcript_supplied,
            "transcript_parse_ok": self.transcript_parse_ok,
            "parse_error": self.parse_error,
            "transcript_hash_valid": self.transcript_hash_valid,
            "declared_transcript_hash": self.declared_transcript_hash,
            "recomputed_transcript_hash": self.recomputed_transcript_hash,
            "message_binding_valid": self.message_binding_valid,
            "declared_message_binding": self.declared_message_binding,
            "recomputed_message_binding": self.recomputed_message_binding,
            "protocol_version_valid": self.protocol_version_valid,
            "observed_protocol_version": self.observed_protocol_version,
            "expected_protocol_versions": list(self.expected_protocol_versions),
            "session_addressing_valid": self.session_addressing_valid,
            "transcript_verifier_id": self.transcript_verifier_id,
            "verifier_context_id": self.verifier_context_id,
            "state_count_declared": self.state_count_declared,
            "state_count_declared_matches_list": (
                self.state_count_declared_matches_list
            ),
            "state_count_declared_matches_observed": (
                self.state_count_declared_matches_observed
            ),
            "state_sequence_metadata_consistent": (
                self.state_sequence_metadata_consistent
            ),
            "declared_state_sequence_matches_derivation": (
                self.declared_state_sequence_matches_derivation
            ),
            "protocol_valid": self.protocol_valid,
            "violations": list(self.violations),
            "notes": list(self.notes),
        }


def analyse_consistency(
    detection_input: ObservableDetectionInput,
    *,
    expected_protocol_versions: Tuple[str, ...] = DEFAULT_PROTOCOL_VERSIONS,
) -> ConsistencyReport:
    """Return the protocol-integrity report for ``detection_input``.

    ``expected_protocol_versions`` is the set of versions the detector is
    willing to speak; it defaults to the reference protocol version. Passing an
    empty tuple disables the version check, which a caller should do only when
    it genuinely has no expectation.
    """
    payload = detection_input.transcript_payload
    parse_error = detection_input.transcript_parse_error
    violations: list[str] = []
    notes: list[str] = []

    transcript_supplied = detection_input.transcript_supplied
    if not transcript_supplied:
        notes.append(
            "no transcript was supplied, so transcript-integrity checks were not "
            "performed"
        )
        return ConsistencyReport(
            transcript_supplied=False,
            transcript_parse_ok=False,
            parse_error=None,
            transcript_hash_valid=None,
            declared_transcript_hash=None,
            recomputed_transcript_hash=None,
            message_binding_valid=None,
            declared_message_binding=None,
            recomputed_message_binding=None,
            protocol_version_valid=None,
            observed_protocol_version=detection_input.protocol_version,
            expected_protocol_versions=tuple(expected_protocol_versions),
            session_addressing_valid=None,
            transcript_verifier_id=None,
            verifier_context_id=detection_input.verifier_context_id,
            state_count_declared=None,
            state_count_declared_matches_list=None,
            state_count_declared_matches_observed=None,
            state_sequence_metadata_consistent=None,
            declared_state_sequence_matches_derivation=None,
            violations=(),
            notes=tuple(notes),
        )

    if payload is None:

        violations.append(
            f"transcript could not be parsed: {parse_error or 'unknown parse failure'}"
        )
        return ConsistencyReport(
            transcript_supplied=True,
            transcript_parse_ok=False,
            parse_error=parse_error,
            transcript_hash_valid=False,
            declared_transcript_hash=detection_input.declared_transcript_hash,
            recomputed_transcript_hash=None,
            message_binding_valid=False,
            declared_message_binding=detection_input.message_binding,
            recomputed_message_binding=None,
            protocol_version_valid=None,
            observed_protocol_version=detection_input.protocol_version,
            expected_protocol_versions=tuple(expected_protocol_versions),
            session_addressing_valid=None,
            transcript_verifier_id=detection_input.verifier_id,
            verifier_context_id=detection_input.verifier_context_id,
            state_count_declared=detection_input.declared_state_count,
            state_count_declared_matches_list=None,
            state_count_declared_matches_observed=None,
            state_sequence_metadata_consistent=None,
            declared_state_sequence_matches_derivation=None,
            violations=tuple(violations),
            notes=tuple(notes),
        )


    declared_hash = detection_input.declared_transcript_hash
    recomputed_hash: str | None = None
    hash_valid: bool | None = None
    try:
        from backend.protocol.transcript import compute_transcript_hash

        hashed_payload = {key: value for key, value in payload.items() if key != "transcript_hash"}
        recomputed_hash = compute_transcript_hash(hashed_payload)
        hash_valid = recomputed_hash == declared_hash
        if not hash_valid:
            violations.append(
                "transcript_hash does not match the canonical digest recomputed "
                "from the declared transcript content"
            )
    except Exception as exc:
        hash_valid = None
        notes.append(
            f"transcript hash could not be recomputed "
            f"({type(exc).__name__}); the transcript content is not canonically "
            f"encodable"
        )
        violations.append(
            "transcript content is not canonically encodable, so its integrity "
            "cannot be established"
        )


    declared_binding = detection_input.message_binding
    recomputed_binding: str | None = None
    binding_valid: bool | None = None
    if detection_input.message is None:
        notes.append(
            "the message was not supplied, so the message binding could not be "
            "recomputed"
        )
    else:
        try:
            from backend.protocol.binding import compute_message_binding

            recomputed_binding = compute_message_binding(
                protocol_version=str(detection_input.protocol_version),
                session_id=str(detection_input.session_id),
                nonce=str(detection_input.nonce),
                message=detection_input.message,
            )
            binding_valid = recomputed_binding == declared_binding
            if not binding_valid:
                violations.append(
                    "message_binding does not match the binding recomputed from "
                    "protocol_version, session_id, nonce and the supplied message"
                )
        except Exception as exc:
            binding_valid = None
            notes.append(
                f"the message binding could not be recomputed "
                f"({type(exc).__name__}); protocol identity fields are malformed"
            )
            violations.append(
                "protocol identity fields are malformed, so the message binding "
                "cannot be established"
            )


    observed_version = detection_input.protocol_version
    version_valid: bool | None = None
    if not expected_protocol_versions:
        notes.append("no expected protocol versions were configured")
    elif observed_version is None:
        version_valid = False
        violations.append(
            "the transcript declares no protocol version, so the version check "
            "fails"
        )
    else:
        version_valid = observed_version in expected_protocol_versions
        if not version_valid:
            violations.append(
                f"protocol_version {observed_version!r} is not one this detector "
                f"speaks {list(expected_protocol_versions)}"
            )


    transcript_verifier = detection_input.verifier_id
    context_verifier = detection_input.verifier_context_id
    addressing_valid: bool | None = None
    if context_verifier is None:
        notes.append(
            "no verifier context was supplied, so the addressing check was not "
            "performed"
        )
    else:
        addressing_valid = transcript_verifier == context_verifier
        if not addressing_valid:
            violations.append(
                f"the transcript is addressed to verifier {transcript_verifier!r}, "
                f"but this verifier is {context_verifier!r}"
            )


    declared_count = detection_input.declared_state_count
    declared_list = payload.get("states")
    declared_list_len = len(declared_list) if isinstance(declared_list, list) else None
    count_matches_list: bool | None = None
    if declared_count is None or declared_list_len is None:
        notes.append(
            "the declared state count or the declared state list is missing, so "
            "the count consistency check was not performed"
        )
    else:
        count_matches_list = declared_count == declared_list_len
        if not count_matches_list:
            violations.append(
                f"state_count {declared_count} does not match the {declared_list_len} "
                f"declared states"
            )

    observed_count = detection_input.observed_state_count
    count_matches_observed: bool | None = None
    if declared_count is None:
        notes.append(
            "the declared state count is missing, so it cannot be compared with "
            "the number of observations"
        )
    else:
        count_matches_observed = declared_count == observed_count
        if not count_matches_observed:
            violations.append(
                f"state_count {declared_count} does not match the {observed_count} "
                f"observations supplied"
            )


    metadata_consistent: bool | None = None
    sequence_matches: bool | None = None
    if declared_count is None or recomputed_binding is None:
        notes.append(
            "the declared state sequence could not be checked against an "
            "independent derivation"
        )
    else:
        try:
            from backend.protocol.encoding import (
                derive_state_sequence,
                sequence_metadata,
            )

            expected_metadata = sequence_metadata(
                declared_count, binding=recomputed_binding
            )
            declared_metadata = payload.get("state_sequence_metadata")
            metadata_consistent = declared_metadata == expected_metadata
            if not metadata_consistent:
                violations.append(
                    "declared state_sequence_metadata does not match the metadata "
                    "the detector derived from the binding it recomputed"
                )

            derived = derive_state_sequence(recomputed_binding, declared_count)
            declared_identifiers = _declared_state_identifiers(declared_list)
            if declared_identifiers is None:
                notes.append(
                    "the declared state list is malformed, so the sequence "
                    "comparison was not performed"
                )
            else:
                expected_identifiers = tuple(
                    state.state_identifier for state in derived
                )
                sequence_matches = declared_identifiers == expected_identifiers
                if not sequence_matches:
                    violations.append(
                        "declared states do not match the state sequence the "
                        "detector derived from the message binding"
                    )
        except Exception as exc:
            notes.append(
                f"the state sequence could not be derived "
                f"({type(exc).__name__})"
            )

    return ConsistencyReport(
        transcript_supplied=True,
        transcript_parse_ok=True,
        parse_error=None,
        transcript_hash_valid=hash_valid,
        declared_transcript_hash=declared_hash,
        recomputed_transcript_hash=recomputed_hash,
        message_binding_valid=binding_valid,
        declared_message_binding=declared_binding,
        recomputed_message_binding=recomputed_binding,
        protocol_version_valid=version_valid,
        observed_protocol_version=observed_version,
        expected_protocol_versions=tuple(expected_protocol_versions),
        session_addressing_valid=addressing_valid,
        transcript_verifier_id=transcript_verifier,
        verifier_context_id=context_verifier,
        state_count_declared=declared_count,
        state_count_declared_matches_list=count_matches_list,
        state_count_declared_matches_observed=count_matches_observed,
        state_sequence_metadata_consistent=metadata_consistent,
        declared_state_sequence_matches_derivation=sequence_matches,
        violations=tuple(violations),
        notes=tuple(notes),
    )


def _declared_state_identifiers(declared_list: Any) -> Tuple[str, ...] | None:
    """Return the declared symbolic identifiers, or ``None`` when malformed."""
    if not isinstance(declared_list, list):
        return None
    identifiers: list[str] = []
    for entry in declared_list:
        if not isinstance(entry, Mapping):
            return None
        identifier = entry.get("state_identifier")
        if not isinstance(identifier, str):
            return None
        identifiers.append(identifier)
    return tuple(identifiers)
