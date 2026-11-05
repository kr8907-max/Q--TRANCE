"""Tests for Z/X/Y basis measurements and the wrong-order regression."""

from __future__ import annotations

import numpy as np
import pytest
from qiskit.quantum_info import Operator

from backend.quantum.measure import (
    BASIS_ROTATION_GATES,
    VALID_BASES,
    WRONG_Y_ROTATION_GATES,
    add_basis_rotation,
    basis_rotation_matrix,
    measure_statevector,
    run_counts,
    wrong_y_rotation_matrix,
)
from backend.quantum.states import EIGENSTATE_LABELS, PAULI_MATRICES, get_eigenstate

ATOL = 1e-10


DETERMINISTIC_OUTCOMES = {
    "|0>": ("Z", "0"),
    "|1>": ("Z", "1"),
    "|+>": ("X", "0"),
    "|->": ("X", "1"),
    "|+i>": ("Y", "0"),
    "|-i>": ("Y", "1"),
}


def test_rotation_gate_table() -> None:
    assert BASIS_ROTATION_GATES["Z"] == ()
    assert BASIS_ROTATION_GATES["X"] == ("h",)
    assert BASIS_ROTATION_GATES["Y"] == ("sdg", "h")
    assert WRONG_Y_ROTATION_GATES == ("h", "s")
    assert VALID_BASES == ("Z", "X", "Y")


@pytest.mark.parametrize("basis,pauli", [("Z", "Z"), ("X", "X"), ("Y", "Y")])
def test_rotation_conjugates_pauli_to_z(basis: str, pauli: str) -> None:
    """``R_P P R_P^dag == Z`` for every basis."""
    rotation = basis_rotation_matrix(basis)
    conjugated = rotation @ PAULI_MATRICES[pauli] @ rotation.conj().T
    assert np.allclose(conjugated, PAULI_MATRICES["Z"], atol=ATOL)


def test_y_rotation_equals_h_times_sdg() -> None:
    """Circuit order ``sdg`` then ``h`` realises the operator ``H . Sdg``.

    Circuit order reverses matrix-product order, so the correct expectation is
    ``HGate @ SdgGate``, not ``SdgGate @ HGate``.
    """
    from qiskit.circuit.library import HGate, SdgGate

    expected = np.asarray(Operator(HGate()).data) @ np.asarray(Operator(SdgGate()).data)
    assert np.allclose(basis_rotation_matrix("Y"), expected, atol=ATOL)


def test_wrong_y_rotation_differs_from_correct_one() -> None:
    assert not np.allclose(basis_rotation_matrix("Y"), wrong_y_rotation_matrix(), atol=1e-6)


def test_wrong_y_rotation_conjugates_y_to_x_not_z() -> None:
    """The wrong sequence realises ``S . H``, which sends ``Y`` to ``X``."""
    rotation = wrong_y_rotation_matrix()
    conjugated = rotation @ PAULI_MATRICES["Y"] @ rotation.conj().T
    assert np.allclose(conjugated, PAULI_MATRICES["X"], atol=1e-9)
    assert not np.allclose(conjugated, PAULI_MATRICES["Z"], atol=1e-9)


@pytest.mark.parametrize("label", EIGENSTATE_LABELS)
def test_deterministic_basis_measurement(label: str) -> None:
    basis, expected_bit = DETERMINISTIC_OUTCOMES[label]
    counts = measure_statevector(get_eigenstate(label).vector, basis, shots=500, seed_simulator=11)
    assert set(counts) == {expected_bit}, (label, basis, counts)


@pytest.mark.parametrize("label", ["|+i>", "|-i>"])
def test_wrong_y_sequence_is_not_deterministic(label: str) -> None:
    """Regression: H-then-S is NOT a valid Y-basis rotation.

    Algebraically it realises ``S . H``, which conjugates ``Y`` to ``X``
    rather than to ``Z``. Physically it maps the Y eigenstates onto the X
    eigenstates (``|+i> -> |+>``, ``|-i> -> |->``), so the following
    computational-basis measurement is 50/50 rather than deterministic. A
    correct Y-basis measurement must be deterministic for a Y eigenstate.
    """
    from qiskit import QuantumCircuit

    from tests.quantum.statutil import assert_expected_probability, counts_to_probability

    _, correct_bit = DETERMINISTIC_OUTCOMES[label]

    circuit = QuantumCircuit(1, 1)
    circuit.initialize(get_eigenstate(label).vector, [0])
    for name in WRONG_Y_ROTATION_GATES:
        getattr(circuit, name)(0)
    circuit.measure(0, 0)

    counts = run_counts(circuit, shots=4000, seed_simulator=11)
    assert set(counts) == {"0", "1"}, (label, counts)

    successes, trials = counts_to_probability(counts, "0")
    assert_expected_probability(successes, trials, 0.5)
    assert correct_bit in counts


def test_wrong_y_sequence_would_fail_a_correctness_assertion() -> None:
    """The wrong sequence cannot satisfy the Y-basis correctness property."""
    rotation = wrong_y_rotation_matrix()
    conjugated = rotation @ PAULI_MATRICES["Y"] @ rotation.conj().T
    assert not np.allclose(conjugated, PAULI_MATRICES["Z"], atol=1e-6)


def test_x_rotation_is_hadamard() -> None:
    from qiskit.circuit.library import HGate

    assert np.allclose(basis_rotation_matrix("X"), np.asarray(Operator(HGate()).data), atol=ATOL)


def test_z_rotation_is_identity() -> None:
    assert np.allclose(basis_rotation_matrix("Z"), np.eye(2, dtype=complex), atol=ATOL)


def test_unknown_basis_is_rejected() -> None:
    with pytest.raises(ValueError):
        basis_rotation_matrix("W")


def test_add_basis_rotation_gate_order_for_y() -> None:
    from qiskit import QuantumCircuit

    circuit = QuantumCircuit(1)
    add_basis_rotation(circuit, 0, "Y")
    assert [i.operation.name for i in circuit.data] == ["sdg", "h"]


def test_measurement_is_reproducible_with_seed() -> None:
    vector = np.array([1.0, 1.0], dtype=complex) / np.sqrt(2.0)

    def run(seed: int) -> dict:
        return measure_statevector(vector, "X", shots=333, seed_simulator=seed)

    assert run(2024) == run(2024)


def test_superposition_gives_balanced_outcomes() -> None:
    from tests.quantum.statutil import assert_expected_probability, counts_to_probability

    vector = np.array([1.0, 1.0], dtype=complex) / np.sqrt(2.0)
    counts = measure_statevector(vector, "Z", shots=4000, seed_simulator=31)
    successes, trials = counts_to_probability(counts, "0")
    assert_expected_probability(successes, trials, 0.5)