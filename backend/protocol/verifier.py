"""The reference verifier.

The verifier is the party that must **not** trust the signer. Everything it
needs it either receives as authenticated protocol data (the message, the
session identifier, the nonce, the protocol version) or reconstructs itself
from the message binding. In particular::

    # never done here
    verifier.expected_states = signer.states

The expected state sequence is *derived* by
:func:`backend.protocol.encoding.derive_state_sequence` from a binding the
verifier recomputes on its own. The states declared in the transcript are then
compared against that reconstruction, so a transcript that lies about its
states is rejected rather than believed.

Verification is deterministic and ideal
---------------------------------------
This milestone performs no threshold-based classification and no statistical
detection. For a transcript produced by a correct signer over an ideal,
noiseless channel, verification succeeds; for a tampered or inconsistent
transcript it fails. The raw counts it exposes (``mismatch_count``,
``basis_counts``, ``measurement_summary``) are diagnostics for later
milestones, not decisions.

The quantum path
----------------
For each state the verifier:

1. takes the expected state's vector from the verified M1 quantum core;
2. reconstructs the qubit it received from Alice's recorded public Bell bits
   using M1's exact branch decomposition
   (:func:`backend.quantum.teleport.uncorrected_branch_states`);
3. applies the M1 Pauli correction ``Z**m0 . X**m1``;
4. rotates into the state's basis with M1's
   :func:`backend.quantum.measure.add_basis_rotation` and computes the
   projective probability of the expected eigenvalue with M1's
   :func:`backend.quantum.density.p_match`.

Step 2 is the simulation seam. In an ideal model the received qubit is exactly
the branch image of the expected state, so the verifier can reconstruct it from
public data. A later milestone replaces this reconstruction with the actual
channel output, at which point noise and tampering make step 4 fail.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import DensityMatrix, Statevector

from backend.protocol.binding import compute_message_binding, compute_message_hash
from backend.protocol.encoding import derive_state_sequence, sequence_metadata
from backend.protocol.models import (
    ProtocolValidationError,
    SignatureState,
    TeleportationBranch,
    Transcript,
    VerificationResult,
    VerifierContext,
)
from backend.protocol.transcript import is_transcript_hash_valid, transcript_from_dict
from backend.quantum.correction import correction_unitary
from backend.quantum.density import p_match
from backend.quantum.measure import add_basis_rotation, basis_rotation_matrix
from backend.quantum.states import get_eigenstate
from backend.quantum.teleport import uncorrected_branch_states

__all__ = [
    "MEASUREMENT_TOLERANCE",
    "StateMeasurement",
    "measure_state_in_basis",
    "verify_state_measurement",
    "ReferenceVerifier",
    "verify",
]




MEASUREMENT_TOLERANCE = 1e-9


@dataclass(frozen=True)
class StateMeasurement:
    """The verifier's per-state quantum check."""

    index: int
    basis: str
    expected_bit: int
    probability: float
    matched: bool


def measure_state_in_basis(
    vector: np.ndarray,
    basis: str,
    expected_eigenvalue: int,
) -> float:
    """Return the projective probability of measuring ``expected_eigenvalue``.

    Accepts either a pure statevector (shape ``(2,)``) or a density matrix
    (shape ``(2, 2)``).

    For a **pure** state the qubit is prepared, rotated into ``basis`` by the
    verified M1 rotation gate sequence, and the probability of the corresponding
    computational-basis outcome is returned -- the Milestone 2 path, unchanged.

    A density matrix cannot be loaded into a circuit with ``initialize``, so for
    a **mixed** state the same rotation is applied as a matrix using the verified
    M1 rotation operator. The two paths agree exactly on pure states, which the
    test suite checks. Milestone 3 needs the mixed-state path because a noisy or
    tampered channel produces mixed states.

    A value of ``1.0`` means the state is exactly the expected eigenstate;
    ``0.5`` means it is unbiased between the two eigenstates, i.e. wrong.
    """
    state = np.asarray(vector, dtype=complex)
    expected_bit = 0 if expected_eigenvalue > 0 else 1
    target = np.array([1.0, 0.0] if expected_bit == 0 else [0.0, 1.0], dtype=complex)

    if state.shape == (2,):
        circuit = QuantumCircuit(1)
        circuit.initialize(state, [0])
        add_basis_rotation(circuit, 0, basis)
        rotated = np.asarray(Statevector(circuit).data, dtype=complex)
        return float(p_match(DensityMatrix(rotated), target))

    if state.shape == (2, 2):
        rotation = basis_rotation_matrix(basis)
        rotated = rotation @ state @ rotation.conj().T
        return float(p_match(DensityMatrix(rotated), target))

    raise ValueError(
        f"expected a statevector of shape (2,) or a density matrix of shape "
        f"(2, 2), got shape {state.shape}"
    )


def verify_state_measurement(
    expected: SignatureState,
    branch: TeleportationBranch,
    received_state: np.ndarray | None = None,
) -> StateMeasurement:
    """Run the verifier's quantum check for one state and Bell branch.

    ``received_state`` is the **simulation seam**. When it is ``None`` -- the
    default, and exactly the Milestone 2 behaviour -- the received qubit is
    reconstructed from the branch bits using M1's exact branch decomposition,
    which is correct for an ideal channel. Milestone 3 supplies the *actual*
    received qubit instead (after a noise channel or a channel attack has acted
    on it), and the check can then fail.

    The branch bits are used either way, because in a teleportation protocol the
    receiver applies the correction dictated by the announced classical bits
    regardless of what arrived.
    """
    vector = get_eigenstate(expected.label).vector
    if received_state is None:
        received = uncorrected_branch_states(vector)[(branch.m0, branch.m1)]
    else:
        received = np.asarray(received_state, dtype=complex)
    U = correction_unitary(branch.m0, branch.m1)
    if received.shape == (2,):
        corrected = U @ received
    elif received.shape == (2, 2):
        corrected = U @ received @ U.conj().T
    else:
        raise ValueError(
            f"received_state must have shape (2,) or (2, 2), got {received.shape}"
        )
    probability = measure_state_in_basis(corrected, expected.basis, expected.eigenvalue)
    return StateMeasurement(
        index=expected.index,
        basis=expected.basis,
        expected_bit=0 if expected.eigenvalue > 0 else 1,
        probability=probability,
        matched=probability >= 1.0 - MEASUREMENT_TOLERANCE,
    )


class ReferenceVerifier:
    """Deterministic verifier for the reference protocol."""

    def verify(
        self,
        transcript: Transcript | Dict[str, Any],
        message: str,
        verifier_context: VerifierContext,
        received_states: Sequence[np.ndarray] | None = None,
    ) -> VerificationResult:
        """Verify ``transcript`` against ``message`` and ``verifier_context``.

        Accepts either a :class:`Transcript` or plain transcript data. Malformed
        data produces ``accepted=False`` with a recorded error; it is never
        silently accepted.

        ``received_states`` is the optional simulation seam added in Milestone 3.
        When omitted, the verifier reconstructs each received qubit from the
        recorded Bell branch bits -- the Milestone 2 behaviour, unchanged. When
        supplied, the verifier measures the qubits it is actually given, so a
        noisy or tampered channel can make verification fail.
        """
        errors: List[str] = []
        warnings: List[str] = []


        try:
            parsed = (
                transcript
                if isinstance(transcript, Transcript)
                else transcript_from_dict(transcript)
            )
        except ProtocolValidationError as exc:


            return VerificationResult(
                accepted=False,
                session_valid=False,
                message_valid=False,
                transcript_valid=False,
                state_sequence_valid=False,
                measurement_valid=False,
                verification_errors=(f"transcript validation failed: {exc}",),
                verification_warnings=(),
            )

        transcript_valid = True
        session_valid = True
        message_valid = True
        state_sequence_valid = True
        measurement_valid = True


        if not is_transcript_hash_valid(parsed):
            transcript_valid = False
            errors.append(
                "transcript_hash does not match the canonical transcript content"
            )


        if parsed.protocol_version != verifier_context.expected_protocol_version:
            session_valid = False
            errors.append(
                f"protocol_version {parsed.protocol_version!r} is not the version "
                f"this verifier speaks "
                f"({verifier_context.expected_protocol_version!r})"
            )
        if parsed.verifier_id != verifier_context.verifier_id:
            session_valid = False
            errors.append(
                f"transcript is addressed to verifier {parsed.verifier_id!r}, but "
                f"this verifier is {verifier_context.verifier_id!r}"
            )
        if parsed.state_count != len(parsed.states):
            session_valid = False
            errors.append("state_count does not match the declared state list")


        expected_message_hash = compute_message_hash(message)
        if expected_message_hash != parsed.message_hash:
            message_valid = False
            errors.append("message_hash does not match the supplied message")




        recomputed_binding = compute_message_binding(
            protocol_version=parsed.protocol_version,
            session_id=parsed.session_id,
            nonce=parsed.nonce,
            message=message,
        )
        if recomputed_binding != parsed.message_binding:
            message_valid = False
            errors.append(
                "message_binding does not match the binding recomputed from "
                "protocol_version, session_id, nonce and message"
            )


        expected_states = derive_state_sequence(recomputed_binding, parsed.state_count)
        mismatch_count = sum(
            1
            for declared, expected in zip(parsed.states, expected_states)
            if declared != expected
        )
        if mismatch_count:
            state_sequence_valid = False
            errors.append(
                f"{mismatch_count} of {parsed.state_count} declared states do not "
                f"match the sequence derived from the message binding"
            )
        expected_metadata = sequence_metadata(parsed.state_count, binding=recomputed_binding)
        if parsed.state_sequence_metadata != expected_metadata:
            state_sequence_valid = False
            errors.append(
                "declared state_sequence_metadata does not match the derivation "
                "the verifier performed"
            )


        basis_counts: Dict[str, int] = {}
        measurements: List[StateMeasurement] = []
        branch_lookup = {branch.index: branch for branch in parsed.teleportation_branches}

        supplied_states: Tuple[np.ndarray, ...] | None = None
        if received_states is not None:
            supplied_states = tuple(
                np.asarray(state, dtype=complex) for state in received_states
            )
            if len(supplied_states) != parsed.state_count:
                measurement_valid = False
                errors.append(
                    f"{len(supplied_states)} received states were supplied but the "
                    f"transcript declares {parsed.state_count}"
                )

        for expected in expected_states:
            basis_counts[expected.basis] = basis_counts.get(expected.basis, 0) + 1
            branch = branch_lookup.get(expected.index)
            if branch is None:
                measurement_valid = False
                errors.append(f"no teleportation branch recorded for state {expected.index}")
                continue
            received = (
                None
                if supplied_states is None or len(supplied_states) != parsed.state_count
                else supplied_states[expected.index]
            )
            measurement = verify_state_measurement(
                expected, branch, received_state=received
            )
            measurements.append(measurement)
            if not measurement.matched:
                measurement_valid = False
                errors.append(
                    f"state {expected.index} ({expected.state_identifier}) measured in "
                    f"the {expected.basis} basis did not yield the expected eigenvalue "
                    f"(projective probability {measurement.probability:.12f})"
                )

        matched = sum(1 for measurement in measurements if measurement.matched)
        measurement_summary = {
            "checked": len(measurements),
            "matched": matched,
            "mismatched": len(measurements) - matched,
        }

        warnings.append(
            "reference verification is structural: it establishes binding and "
            "consistency, not unforgeability"
        )

        accepted = (
            transcript_valid
            and session_valid
            and message_valid
            and state_sequence_valid
            and measurement_valid
            and not errors
        )

        return VerificationResult(
            accepted=accepted,
            session_valid=session_valid,
            message_valid=message_valid,
            transcript_valid=transcript_valid,
            state_sequence_valid=state_sequence_valid,
            measurement_valid=measurement_valid,
            verification_errors=tuple(errors),
            verification_warnings=tuple(warnings),
            state_count=parsed.state_count,
            mismatch_count=mismatch_count,
            basis_counts=basis_counts,
            measurement_summary=measurement_summary,
        )


def verify(
    transcript: Transcript | Dict[str, Any],
    message: str,
    verifier_context: VerifierContext,
    received_states: Sequence[np.ndarray] | None = None,
) -> VerificationResult:
    """Convenience wrapper around :meth:`ReferenceVerifier.verify`."""
    return ReferenceVerifier().verify(
        transcript, message, verifier_context, received_states=received_states
    )
