"""The Bell state |Phi+> = (|00> + |11>) / sqrt(2) and its preparation circuit.

Milestone 1 -- verified quantum core.

Preparation circuit (canonical):

    H on q_a        ->  (|0> + |1>)|0> / sqrt(2)
    CX(q_a -> q_b)  ->  (|00> + |11>) / sqrt(2)

Qubit ordering note
-------------------
For a two-qubit ``Statevector`` Qiskit uses the little-endian index
``i = b0 + 2*b1``, so the amplitude vector of |Phi+> in the computational
basis is ``[1/sqrt(2), 0, 0, 1/sqrt(2)]``: index 0 is |00> and index 3 is |11>.
"""

from __future__ import annotations

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import DensityMatrix, Statevector

__all__ = [
    "bell_circuit",
    "bell_amplitudes_exact",
    "bell_statevector",
    "bell_density_matrix",
]


def bell_circuit(q_a: int = 0, q_b: int = 1, num_qubits: int | None = None) -> QuantumCircuit:
    """Return the |Phi+> preparation circuit entangling ``q_a`` and ``q_b``.

    Parameters
    ----------
    q_a:
        Control qubit index; receives H then acts as the CX control.
    q_b:
        Target qubit index; receives the CX.
    num_qubits:
        Total qubits in the returned circuit. Defaults to ``max(q_a, q_b) + 1``.
    """
    if q_a == q_b:
        raise ValueError("q_a and q_b must be distinct qubits")
    if num_qubits is None:
        num_qubits = max(q_a, q_b) + 1
    if min(q_a, q_b) < 0 or max(q_a, q_b) >= num_qubits:
        raise ValueError("qubit indices must lie inside [0, num_qubits)")

    qc = QuantumCircuit(num_qubits, name="bell_phi_plus")
    qc.h(q_a)
    qc.cx(q_a, q_b)
    return qc


def bell_amplitudes_exact() -> np.ndarray:
    """Return the exact two-qubit amplitude vector of |Phi+> (little-endian)."""
    return np.array([1.0 / np.sqrt(2.0), 0.0, 0.0, 1.0 / np.sqrt(2.0)], dtype=complex)


def bell_statevector() -> Statevector:
    """Return |Phi+> as a ``Statevector`` produced by the actual circuit."""
    return Statevector(bell_circuit())


def bell_density_matrix() -> DensityMatrix:
    """Return |Phi+><Phi+| as a ``DensityMatrix``."""
    return DensityMatrix(bell_statevector())