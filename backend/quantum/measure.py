"""Basis rotations, computational-basis measurement, and shot execution.

Milestone 1 -- verified quantum core.

Basis convention
----------------
A measurement in the Pauli ``P`` basis is performed by applying a unitary
``R_P`` satisfying ``R_P P R_P^dag = Z`` and then measuring in the
computational basis. The measured bit ``b`` then corresponds to the
eigenvalue ``(-1)**b`` of ``P``::

    basis   R_P          gates appended      algebraic check
    Z       I            (none)             Z = Z
    X       H            h                  H X H = Z
    Y       Sdg . H      sdg, h             (H Sdg) Y (H Sdg)^dag = Z

The alternative Y sequence ``H`` then ``S`` is **not** equal to ``Sdg`` then
``H``. Algebraically it realises ``S . H``, which conjugates ``Y`` to ``X``
rather than to ``Z``. Physically it maps the Y eigenstates onto the X
eigenstates, so a following computational-basis measurement returns a 50/50
split instead of a deterministic outcome while still looking plausible. The
wrong sequence is exported only so the test suite can prove it fails.

Shot execution
--------------
``run_counts`` transposes the circuit for the Aer CPU backend with a fixed
transpiler seed and forwards an explicit simulator seed, so identical
(circuit, shots, seed) triples reproduce identical counts.
"""

from __future__ import annotations

from typing import Dict, Sequence, Tuple

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator
from qiskit_aer import AerSimulator

from backend.quantum.cache import transpiled as _transpiled

__all__ = [
    "VALID_BASES",
    "BASIS_ROTATION_GATES",
    "WRONG_Y_ROTATION_GATES",
    "add_basis_rotation",
    "basis_rotation_matrix",
    "wrong_y_rotation_matrix",
    "measure_statevector",
    "aer_simulator",
    "run_counts",
]



BASIS_ROTATION_GATES: Dict[str, Tuple[str, ...]] = {
    "Z": (),
    "X": ("h",),
    "Y": ("sdg", "h"),
}



VALID_BASES: Tuple[str, ...] = tuple(BASIS_ROTATION_GATES)


WRONG_Y_ROTATION_GATES: Tuple[str, ...] = ("h", "s")


def _check_basis(basis: str) -> str:
    if basis not in BASIS_ROTATION_GATES:
        raise ValueError(f"unknown basis {basis!r}; expected one of {VALID_BASES}")
    return basis


def _append_gates(circuit: QuantumCircuit, qubit: int, gates: Sequence[str]) -> None:
    for name in gates:
        getattr(circuit, name)(qubit)


def add_basis_rotation(circuit: QuantumCircuit, qubit: int, basis: str) -> QuantumCircuit:
    """Append the rotation that maps the ``basis`` Pauli onto Z on ``qubit``."""
    basis = _check_basis(basis)
    _append_gates(circuit, qubit, BASIS_ROTATION_GATES[basis])
    return circuit


def _rotation_matrix_from_gates(gates: Sequence[str]) -> np.ndarray:
    circuit = QuantumCircuit(1)
    _append_gates(circuit, 0, gates)
    return np.asarray(Operator(circuit).data, dtype=complex)


def basis_rotation_matrix(basis: str) -> np.ndarray:
    """Return ``R_P`` as a 2x2 matrix, built from the actual appended gates."""
    basis = _check_basis(basis)
    return _rotation_matrix_from_gates(BASIS_ROTATION_GATES[basis])


def wrong_y_rotation_matrix() -> np.ndarray:
    """Return the matrix of the intentionally incorrect H-then-S Y rotation."""
    return _rotation_matrix_from_gates(WRONG_Y_ROTATION_GATES)


def aer_simulator() -> AerSimulator:
    """Return an Aer CPU simulator instance."""
    return AerSimulator()


def run_counts(
    circuit: QuantumCircuit,
    shots: int,
    seed_simulator: int | None = None,
    seed_transpiler: int = 0,
) -> Dict[str, int]:
    """Transpile and execute ``circuit``, returning the count dictionary.

    Both seeds are explicit so that results are reproducible.

    Transpilation goes through :func:`backend.quantum.cache.transpiled`, which
    is a plain pass-through to Qiskit's transpiler unless a caller has
    explicitly enabled the transpiled-circuit cache. The cache stores only the
    compiled circuit -- never an outcome -- so enabling it cannot change a
    count; see that module for the guarantee and its proof obligations.
    """
    if shots <= 0:
        raise ValueError("shots must be positive")
    simulator = aer_simulator()
    compiled = _transpiled(circuit, simulator, seed_transpiler=seed_transpiler)
    result = simulator.run(compiled, shots=shots, seed_simulator=seed_simulator).result()
    counts = result.get_counts()
    return {str(k): int(v) for k, v in counts.items()}


def measure_statevector(
    vector: np.ndarray,
    basis: str,
    shots: int,
    seed_simulator: int | None = None,
) -> Dict[str, int]:
    """Prepare ``vector``, rotate into ``basis``, and measure in 1 qubit / 1 clbit.

    The returned single-character bit is ``0`` when the state has eigenvalue
    ``+1`` for the basis Pauli and ``1`` when it has eigenvalue ``-1``.
    """
    state = np.asarray(vector, dtype=complex).reshape(2)
    circuit = QuantumCircuit(1, 1)
    circuit.initialize(state, [0])
    add_basis_rotation(circuit, 0, basis)
    circuit.measure(0, 0)
    return run_counts(circuit, shots=shots, seed_simulator=seed_simulator)
