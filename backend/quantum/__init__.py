"""Verified quantum core for SIH26141 (Milestone 1).

This package contains the quantum-mechanical primitives: Pauli eigenstates,
the Bell state, three-qubit teleportation with Pauli corrections, projective
measurement mathematics, and basis measurements.

It also re-exports :mod:`backend.quantum.cache`, the opt-in transpilation cache
that serves those primitives. The cache stores compiled circuits and never
outcomes, it is off unless a caller enables it, and it changes no result -- see
that module's docstring and ``tests/quantum/test_cache.py``. It is included here
because it is a property of how the primitives are *executed* rather than of any
protocol, and it knows nothing about protocols, attacks, noise, detection,
thresholds, the API or the frontend.

Like the rest of the package it has no knowledge of any protocol, attack, noise
model, detector, threshold, API or frontend. In particular this package imports
nothing from ``protocol``, ``attacks``, ``detection``, ``security``, ``api`` or
``frontend``.
"""

from backend.quantum.bell import (
    bell_amplitudes_exact,
    bell_circuit,
    bell_density_matrix,
    bell_statevector,
)
from backend.quantum.cache import (
    CacheError,
    CacheStats,
    cache_stats,
    circuit_digest,
    disable,
    enable,
    enabled,
    is_enabled,
    transpiled,
)
from backend.quantum.correction import (
    CORRECTION_TABLE,
    append_conditional_correction,
    apply_pauli_correction,
    correction_label,
    correction_unitary,
    split_bell_count_string,
)
from backend.quantum.density import (
    as_density_matrix,
    as_statevector_array,
    fidelity_of_pure_states,
    fidelity_pure,
    is_pure,
    p_match,
    p_mismatch,
    partial_trace_qubits,
    perpendicular_projector,
    projector,
)
from backend.quantum.measure import (
    BASIS_ROTATION_GATES,
    VALID_BASES,
    WRONG_Y_ROTATION_GATES,
    add_basis_rotation,
    aer_simulator,
    basis_rotation_matrix,
    measure_statevector,
    run_counts,
    wrong_y_rotation_matrix,
)
from backend.quantum.states import (
    EIGENSTATE_LABELS,
    PAULI_MATRICES,
    PauliEigenstate,
    get_eigenstate,
    pauli_eigenstates,
    pauli_expectation,
    preparation_circuit,
)
from backend.quantum.teleport import (
    CLBIT_BOB,
    CLBIT_M0,
    CLBIT_M1,
    QUBIT_ALICE,
    QUBIT_BOB,
    QUBIT_INPUT,
    corrected_branch_states,
    teleport_and_measure,
    teleport_circuit,
    teleport_premeasurement_statevector,
    uncorrected_branch_states,
)

__all__ = [

    "EIGENSTATE_LABELS",
    "PAULI_MATRICES",
    "PauliEigenstate",
    "get_eigenstate",
    "pauli_eigenstates",
    "pauli_expectation",
    "preparation_circuit",

    "CacheError",
    "CacheStats",
    "cache_stats",
    "circuit_digest",
    "disable",
    "enable",
    "enabled",
    "is_enabled",
    "transpiled",

    "bell_amplitudes_exact",
    "bell_circuit",
    "bell_density_matrix",
    "bell_statevector",

    "CORRECTION_TABLE",
    "append_conditional_correction",
    "apply_pauli_correction",
    "correction_label",
    "correction_unitary",
    "split_bell_count_string",

    "BASIS_ROTATION_GATES",
    "VALID_BASES",
    "WRONG_Y_ROTATION_GATES",
    "add_basis_rotation",
    "aer_simulator",
    "basis_rotation_matrix",
    "measure_statevector",
    "run_counts",
    "wrong_y_rotation_matrix",

    "as_density_matrix",
    "as_statevector_array",
    "fidelity_of_pure_states",
    "fidelity_pure",
    "is_pure",
    "p_match",
    "p_mismatch",
    "partial_trace_qubits",
    "perpendicular_projector",
    "projector",

    "CLBIT_BOB",
    "CLBIT_M0",
    "CLBIT_M1",
    "QUBIT_ALICE",
    "QUBIT_BOB",
    "QUBIT_INPUT",
    "corrected_branch_states",
    "teleport_and_measure",
    "teleport_circuit",
    "teleport_premeasurement_statevector",
    "uncorrected_branch_states",
]