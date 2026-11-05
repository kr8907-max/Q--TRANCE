"""Pauli eigenstates: the six single-qubit reference states.

Milestone 1 -- verified quantum core. No protocol, attack, detection or
security logic lives in this module.

States implemented
------------------
Z basis (eigenstates of Z, with Z|b> = (-1)^b |b>):

    |0> = (1, 0)^T
    |1> = (0, 1)^T

X basis (eigenstates of X, with X = [[0, 1], [1, 0]]):

    |+> = (|0> + |1>) / sqrt(2)        X|+> = +|+>
    |-> = (|0> - |1>) / sqrt(2)        X|-> = -|->

Y basis (eigenstates of Y, with Y = [[0, -i], [i, 0]]):

    |+i> = (|0> + i|1>) / sqrt(2)      Y|+i> = +|+i>
    |-i> = (|0> - i|1>) / sqrt(2)      Y|-i> = -|-i>

Global phase
------------
Two statevectors differing only by a unit-modulus scalar represent the same
physical state. Eigenvalue assertions are therefore phrased as
``P|psi> = lambda|psi>`` instead of comparing raw amplitudes.

Qubit ordering
--------------
Where a state is wrapped in a ``qiskit.quantum_info.Statevector``, Qiskit's
little-endian convention applies: for an n-qubit state the basis index is
``sum_k b_k * 2**k``, i.e. qubit 0 is the least significant bit. This is
re-verified empirically by ``tests/quantum/test_bit_ordering.py`` rather than
assumed from documentation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

__all__ = [
    "PAULI_MATRICES",
    "PauliEigenstate",
    "EIGENSTATE_LABELS",
    "pauli_eigenstates",
    "get_eigenstate",
    "preparation_circuit",
    "pauli_expectation",
]

_SQRT1_2 = 1.0 / np.sqrt(2.0)


PAULI_MATRICES: Dict[str, np.ndarray] = {
    "I": np.array([[1.0, 0.0], [0.0, 1.0]], dtype=complex),
    "X": np.array([[0.0, 1.0], [1.0, 0.0]], dtype=complex),
    "Y": np.array([[0.0, -1.0j], [1.0j, 0.0]], dtype=complex),
    "Z": np.array([[1.0, 0.0], [0.0, -1.0]], dtype=complex),
}


@dataclass(frozen=True)
class PauliEigenstate:
    """A named single-qubit Pauli eigenstate.

    Attributes
    ----------
    label:
        Human-readable ket label, e.g. ``"|+i>"``.
    basis:
        Pauli operator this state is an eigenstate of: ``"X"``, ``"Y"`` or ``"Z"``.
    eigenvalue:
        Eigenvalue of ``basis`` for this state: ``+1`` or ``-1``.
    vector:
        Complex amplitude vector in the computational (Z) basis, shape ``(2,)``.
    """

    label: str
    basis: str
    eigenvalue: int
    vector: np.ndarray

    @property
    def statevector(self) -> Statevector:
        """Return this state as a Qiskit ``Statevector``."""
        return Statevector(self.vector)


_DEFINITIONS: Tuple[Tuple[str, str, int, Tuple[complex, complex]], ...] = (
    ("|0>", "Z", +1, (1.0, 0.0)),
    ("|1>", "Z", -1, (0.0, 1.0)),
    ("|+>", "X", +1, (_SQRT1_2, _SQRT1_2)),
    ("|->", "X", -1, (_SQRT1_2, -_SQRT1_2)),
    ("|+i>", "Y", +1, (_SQRT1_2, 1.0j * _SQRT1_2)),
    ("|-i>", "Y", -1, (_SQRT1_2, -1.0j * _SQRT1_2)),
)

EIGENSTATE_LABELS: Tuple[str, ...] = tuple(d[0] for d in _DEFINITIONS)

_EIGENSTATES: Dict[str, PauliEigenstate] = {
    label: PauliEigenstate(
        label=label,
        basis=basis,
        eigenvalue=eigenvalue,
        vector=np.array(amps, dtype=complex),
    )
    for label, basis, eigenvalue, amps in _DEFINITIONS
}


def pauli_eigenstates() -> Dict[str, PauliEigenstate]:
    """Return a fresh mapping ``label -> PauliEigenstate`` for all six states."""
    return dict(_EIGENSTATES)


def get_eigenstate(label: str) -> PauliEigenstate:
    """Return the eigenstate registered under ``label``.

    Raises
    ------
    KeyError
        If ``label`` is not one of the six reference states.
    """
    try:
        return _EIGENSTATES[label]
    except KeyError as exc:  # pragma: no cover - defensive
        raise KeyError(
            f"unknown Pauli eigenstate {label!r}; expected one of {EIGENSTATE_LABELS}"
        ) from exc


def preparation_circuit(vector: np.ndarray, qubit: int = 0, num_qubits: int = 1) -> QuantumCircuit:
    """Return a circuit that prepares ``vector`` on ``qubit``.

    The vector must be normalized; an unnormalized input is a programming
    error rather than something to silently rescale.
    """
    state = np.asarray(vector, dtype=complex).reshape(2)
    norm = float(np.linalg.norm(state))
    if not np.isclose(norm, 1.0, atol=1e-12):
        raise ValueError(f"state must be normalized, got norm {norm!r}")
    if not 0 <= qubit < num_qubits:
        raise ValueError("qubit must lie inside [0, num_qubits)")

    circuit = QuantumCircuit(num_qubits, name="prepare")
    circuit.initialize(state, [qubit])
    return circuit


def pauli_expectation(vector: np.ndarray, pauli: str) -> complex:
    """Return ``<psi|P|psi>`` for the given Pauli operator name."""
    v = np.asarray(vector, dtype=complex).reshape(2)
    return complex(np.vdot(v, PAULI_MATRICES[pauli] @ v))