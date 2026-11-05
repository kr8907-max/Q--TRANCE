"""The reference signer.

The signer turns a message into a session and a canonical transcript. It is
deliberately ignorant of everything that comes later: it imports no attack
module, no detection module, no noise model and no threshold logic, and it
knows nothing about how a transcript will be attacked.

Responsibilities
----------------
The signer owns *protocol* concerns only:

* what state is being transported, and why it belongs to the signature
  sequence (derived from the message binding);
* which session the sequence belongs to;
* what the verifier will need in order to check the signature.

The *quantum* concerns stay in :mod:`backend.quantum`: the signer calls
:func:`backend.quantum.teleport.teleport_circuit` and
:func:`backend.quantum.measure.run_counts` and never re-implements
teleportation mathematics.

Teleportation, once per state
-----------------------------
For each state in the sequence the signer prepares the corresponding Pauli
eigenstate, runs the verified three-qubit teleportation circuit with the
classical feed-forward correction enabled, and records Alice's two public Bell
bits. Bob's qubit is deliberately **not** measured here: measuring the received
qubit is the verifier's job, and letting the signer do it would blur the two
roles.

Seeding
-------
``simulator_seed`` is a simulation-harness knob, not a cryptographic value. The
per-state seed is ``simulator_seed + index``, so a signing run is reproducible
when a caller asks for it and the recorded branch metadata is reproducible too.
The default is ``0``: this reference prototype is deterministic by default, in
the same spirit as the M1 quantum core, which never uses uncontrolled global
randomness. Cryptographic unpredictability lives in ``session_id`` and
``nonce`` (see :mod:`backend.protocol.session`) and is never derived from this
seed.
"""

from __future__ import annotations

from typing import List, Tuple

from backend.protocol.encoding import derive_state_sequence, sequence_metadata
from backend.protocol.models import (
    DEFAULT_STATE_COUNT,
    PROTOCOL_VERSION,
    TRANSCRIPT_VERSION,
    ProtocolValidationError,
    Session,
    SessionStatus,
    SignatureState,
    SigningResult,
    TeleportationBranch,
    validate_identifier,
)
from backend.protocol.session import create_session, session_binding, session_with_status
from backend.protocol.transcript import build_transcript
from backend.quantum.correction import split_bell_count_string
from backend.quantum.measure import run_counts
from backend.quantum.states import get_eigenstate
from backend.quantum.teleport import teleport_circuit

__all__ = [
    "DEFAULT_SIMULATOR_SEED",
    "VERIFICATION_POLICY_METADATA",
    "teleport_signature_state",
    "sign_session",
    "sign",
]


DEFAULT_SIMULATOR_SEED = 0




VERIFICATION_POLICY_METADATA = {
    "basis_policy": "binding-derived",
    "measurement_mode": "projective-analytic",
    "correction_convention": "Z^m0 . X^m1",
    "state_sequence_source": "message-binding",
}


def teleport_signature_state(
    state: SignatureState,
    *,
    simulator_seed: int,
) -> TeleportationBranch:
    """Teleport one signature state and return Alice's public Bell bits.

    Calls the verified M1 engine. The returned bits are ordered ``(m0, m1)``
    using M1's empirically verified count-string convention
    (:func:`backend.quantum.correction.split_bell_count_string`), so this module
    never re-derives bit ordering.
    """
    vector = get_eigenstate(state.label).vector
    circuit = teleport_circuit(vector, apply_correction=True, measure_bob_basis=None)
    counts = run_counts(circuit, shots=1, seed_simulator=simulator_seed)

    if len(counts) != 1:
        raise ProtocolValidationError(
            f"single-shot teleportation of state {state.index} returned "
            f"{len(counts)} distinct outcomes"
        )
    key = next(iter(counts))




    m0, m1 = split_bell_count_string(str(key)[1:3])
    return TeleportationBranch(index=state.index, m0=m0, m1=m1)


def sign_session(
    session: Session,
    *,
    simulator_seed: int = DEFAULT_SIMULATOR_SEED,
) -> SigningResult:
    """Execute the signing workflow for an existing session.

    Steps: derive the state sequence from the binding, teleport each state
    through the M1 engine, then assemble and hash the transcript. The session
    is returned with status ``SIGNED``.
    """
    validate_identifier(session.signer_id, "signer_id")
    validate_identifier(session.verifier_id, "verifier_id")

    binding = session_binding(session)
    states: Tuple[SignatureState, ...] = derive_state_sequence(binding, session.state_count)

    branches: List[TeleportationBranch] = [
        teleport_signature_state(state, simulator_seed=simulator_seed + state.index)
        for state in states
    ]

    transcript = build_transcript(
        transcript_version=TRANSCRIPT_VERSION,
        protocol_version=session.protocol_version,
        session_id=session.session_id,
        nonce=session.nonce,
        created_at=session.created_at,
        message_hash=session.message_hash,
        message_binding=binding,
        signer_id=session.signer_id,
        verifier_id=session.verifier_id,
        state_count=session.state_count,
        state_sequence_metadata=sequence_metadata(session.state_count, binding=binding),
        states=states,
        teleportation_branches=branches,
        verification_metadata=dict(VERIFICATION_POLICY_METADATA),
    )
    return SigningResult(
        session=session_with_status(session, SessionStatus.SIGNED),
        transcript=transcript,
    )


def sign(
    message: str,
    *,
    signer_id: str | None = None,
    verifier_id: str | None = None,
    state_count: int = DEFAULT_STATE_COUNT,
    protocol_version: str = PROTOCOL_VERSION,
    simulator_seed: int = DEFAULT_SIMULATOR_SEED,
    session: Session | None = None,
) -> SigningResult:
    """Convenience entry point: create a session if needed, then sign.

    Passing an explicit ``session`` is how a test controls the identifier and
    the nonce; in that case ``signer_id`` and ``verifier_id`` are taken from the
    session and may be omitted. Otherwise they are required and
    :func:`backend.protocol.session.create_session` generates the identifiers
    from the OS CSPRNG.
    """
    if session is None:
        if signer_id is None or verifier_id is None:
            raise ProtocolValidationError(
                "signer_id and verifier_id are required when no session is supplied"
            )
        session = create_session(
            message,
            signer_id=signer_id,
            verifier_id=verifier_id,
            state_count=state_count,
            protocol_version=protocol_version,
        )
    elif message != session.message:
        raise ProtocolValidationError(
            "the supplied session was created for a different message"
        )
    return sign_session(session, simulator_seed=simulator_seed)
