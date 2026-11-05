"""Canonical three-qubit quantum teleportation.

Milestone 1 -- verified quantum core.

Qubit assignment
----------------
``q0``  input / secret state to be teleported
``q1``  Alice's half of the Bell pair
``q2``  Bob's half of the Bell pair (receives the correction)

Classical bits
--------------
``c0``  outcome of measuring ``q0``  -> ``m0``
``c1``  outcome of measuring ``q1``  -> ``m1``
``c2``  optional final measurement of ``q2``

Circuit order
-------------
1. prepare the input state on ``q0``
2. ``H(q1)``, ``CX(q1, q2)``            -- Bell pair |Phi+> on (q1, q2)
3. ``CX(q0, q1)``, ``H(q0)``            -- rotate into the Bell basis
4. ``measure(q0 -> c0)``, ``measure(q1 -> c1)``
5. ``X(q2)`` if ``c1``, then ``Z(q2)`` if ``c0``   -- ``Z**m0 . X**m1``
6. optional basis rotation and ``measure(q2 -> c2)``

Two independent verification paths are provided:

* ``teleport_premeasurement_statevector`` plus the branch helpers give an
  **exact analytic** check of all four Bell outcomes with no sampling at all.
* ``teleport_and_measure`` runs the full circuit on Aer with the classical
  feed-forward present, for an end-to-end shot-based check.

Bit-order convention
--------------------
For an n-qubit ``Statevector`` Qiskit indexes amplitudes little-endian:
``i = sum_k b_k 2**k``, so qubit 0 is the least significant bit. Bob's
uncorrected branch state for outcome ``(m0, m1)`` is therefore extracted by
reshaping the eight amplitudes to ``A[b0, b1, b2]`` and taking ``A[m0, m1, :]``.
"""

from __future__ import annotations

from typing import Dict, Tuple

import numpy as np
from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister
from qiskit.quantum_info import Statevector

from backend.quantum.bell import bell_circuit
from backend.quantum.correction import append_conditional_correction, correction_unitary
from backend.quantum.measure import add_basis_rotation, run_counts

__all__ = [
    "QUBIT_INPUT",
    "QUBIT_ALICE",
    "QUBIT_BOB",
    "CLBIT_M0",
    "CLBIT_M1",
    "CLBIT_BOB",
    "teleport_circuit",
    "teleport_premeasurement_statevector",
    "uncorrected_branch_states",
    "corrected_branch_states",
    "teleport_and_measure",
]

QUBIT_INPUT = 0
QUBIT_ALICE = 1
QUBIT_BOB = 2
CLBIT_M0 = 0
CLBIT_M1 = 1
CLBIT_BOB = 2

_BRANCHES: Tuple[Tuple[int, int], ...] = ((0, 0), (0, 1), (1, 0), (1, 1))


def _normalized(vector: np.ndarray) -> np.ndarray:
    state = np.asarray(vector, dtype=complex).reshape(2)
    norm = float(np.linalg.norm(state))
    if not np.isclose(norm, 1.0, atol=1e-12):
        raise ValueError(f"input state must be normalized, got norm {norm!r}")
    return state


def teleport_circuit(
    input_vector: np.ndarray | None = None,
    *,
    apply_correction: bool = True,
    measure_bob_basis: str | None = None,
) -> QuantumCircuit:
    """Build the full three-qubit teleportation circuit.

    Parameters
    ----------
    input_vector:
        Single-qubit state to teleport. ``None`` leaves ``q0`` in ``|0>``.
    apply_correction:
        When ``False`` the Pauli feed-forward is omitted. Used by the test
        suite as a control showing that the correction is load-bearing.
    measure_bob_basis:
        When given, rotate ``q2`` into this basis and measure it into ``c2``.
    """
    qreg = QuantumRegister(3, "q")
    creg = ClassicalRegister(3, "c")
    circuit = QuantumCircuit(qreg, creg, name="teleport")

    if input_vector is not None:
        circuit.initialize(_normalized(input_vector), [QUBIT_INPUT])

    circuit.compose(bell_circuit(QUBIT_ALICE, QUBIT_BOB, num_qubits=3), inplace=True)

    circuit.cx(QUBIT_INPUT, QUBIT_ALICE)
    circuit.h(QUBIT_INPUT)

    circuit.measure(QUBIT_INPUT, CLBIT_M0)
    circuit.measure(QUBIT_ALICE, CLBIT_M1)

    if apply_correction:
        append_conditional_correction(
            circuit, QUBIT_BOB, creg[CLBIT_M0], creg[CLBIT_M1]
        )

    if measure_bob_basis is not None:
        add_basis_rotation(circuit, QUBIT_BOB, measure_bob_basis)
        circuit.measure(QUBIT_BOB, CLBIT_BOB)

    return circuit


def teleport_premeasurement_statevector(input_vector: np.ndarray) -> Statevector:
    """Return the three-qubit state after steps 1-3, before any measurement.

    Analytic construction, cross-checked against the circuit:

        |psi>_0 (x) |Phi+>_12  with little-endian kron ordering
        ``kron(bell_amplitudes, input_amplitudes)`` because qubit 0 is the
        least significant index.
    """
    state = _normalized(input_vector)
    circuit = QuantumCircuit(3)
    circuit.initialize(state, [QUBIT_INPUT])
    circuit.compose(bell_circuit(QUBIT_ALICE, QUBIT_BOB, num_qubits=3), inplace=True)
    circuit.cx(QUBIT_INPUT, QUBIT_ALICE)
    circuit.h(QUBIT_INPUT)
    return Statevector(circuit)


def uncorrected_branch_states(input_vector: np.ndarray) -> Dict[Tuple[int, int], np.ndarray]:
    """Return Bob's qubit state for each Bell outcome, before correction.

    Each branch has probability 1/4, so the extracted amplitudes are
    normalized before being returned. The expected values are ``|psi>``,
    ``X|psi>``, ``Z|psi>`` and ``XZ|psi>`` for ``(0,0)``, ``(0,1)``, ``(1,0)``
    and ``(1,1)`` respectively.
    """
    state = _normalized(input_vector)
    full = np.asarray(teleport_premeasurement_statevector(state).data, dtype=complex)

    branches = full.reshape(2, 2, 2).transpose(2, 1, 0)

    out: Dict[Tuple[int, int], np.ndarray] = {}
    for m0, m1 in _BRANCHES:
        amp = branches[m0, m1, :]
        norm = float(np.linalg.norm(amp))
        if norm <= 0.0:  # pragma: no cover - cannot happen for |Phi+>
            raise AssertionError(f"branch {(m0, m1)} has zero norm")
        out[(m0, m1)] = amp / norm
    return out


def corrected_branch_states(input_vector: np.ndarray) -> Dict[Tuple[int, int], np.ndarray]:
    """Return Bob's qubit state for each Bell outcome, after ``Z**m0 . X**m1``.

    In the ideal noiseless model every entry equals the input state exactly.
    """
    state = _normalized(input_vector)
    out: Dict[Tuple[int, int], np.ndarray] = {}
    for branch, pre in uncorrected_branch_states(state).items():
        out[branch] = correction_unitary(*branch) @ pre
    return out


def teleport_and_measure(
    input_vector: np.ndarray,
    basis: str,
    shots: int,
    seed_simulator: int | None = None,
    apply_correction: bool = True,
) -> Dict[str, int]:
    """Run the full teleportation circuit on Aer and measure Bob's qubit.

    The returned counts are keyed by Bob's final bit ``c2`` only. With the
    correction applied and a noiseless simulator, the outcome for an input
    state that is an eigenstate of the chosen ``basis`` Pauli is deterministic.
    """
    circuit = teleport_circuit(
        input_vector,
        apply_correction=apply_correction,
        measure_bob_basis=basis,
    )
    counts = run_counts(circuit, shots=shots, seed_simulator=seed_simulator)
    collapsed: Dict[str, int] = {}
    for key, value in counts.items():

        bob_bit = str(key)[0]
        collapsed[bob_bit] = collapsed.get(bob_bit, 0) + int(value)
    return collapsed