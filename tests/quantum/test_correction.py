"""Tests for the Pauli correction convention ``Z**m0 . X**m1``."""

from __future__ import annotations

import numpy as np
import pytest
from qiskit import QuantumCircuit

from backend.quantum.correction import (
    CORRECTION_TABLE,
    append_conditional_correction,
    apply_pauli_correction,
    correction_label,
    correction_unitary,
    split_bell_count_string,
)
from backend.quantum.states import PAULI_MATRICES

ATOL = 1e-12
IDENTITY = np.eye(2, dtype=complex)



UNITARY_FOR_LABEL = {
    "I": IDENTITY,
    "X": PAULI_MATRICES["X"],
    "Z": PAULI_MATRICES["Z"],
    "ZX": PAULI_MATRICES["Z"] @ PAULI_MATRICES["X"],
}


def test_table_entries() -> None:
    assert CORRECTION_TABLE == {(0, 0): "I", (0, 1): "X", (1, 0): "Z", (1, 1): "ZX"}


@pytest.mark.parametrize(
    "m0,m1,expected",
    [
        (0, 0, IDENTITY),
        (0, 1, PAULI_MATRICES["X"]),
        (1, 0, PAULI_MATRICES["Z"]),
        (1, 1, PAULI_MATRICES["Z"] @ PAULI_MATRICES["X"]),
    ],
)
def test_correction_unitary(m0: int, m1: int, expected: np.ndarray) -> None:
    assert np.allclose(correction_unitary(m0, m1), expected, atol=ATOL)


def test_labels_are_consistent_with_the_unitaries() -> None:
    """``correction_label`` and ``correction_unitary`` describe the same operator.

    Asserting the label against ``CORRECTION_TABLE`` would be circular, since
    ``correction_label`` is a lookup into that very table. The label is instead
    decoded back into an operator through ``PAULI_MATRICES`` and compared with
    the matrix ``correction_unitary`` builds numerically.
    """
    for m0 in (0, 1):
        for m1 in (0, 1):
            label = correction_label(m0, m1)
            assert label in UNITARY_FOR_LABEL, (m0, m1, label)
            assert np.allclose(
                correction_unitary(m0, m1), UNITARY_FOR_LABEL[label], atol=ATOL
            ), (m0, m1, label)


def test_all_corrections_are_unitary() -> None:
    for m0 in (0, 1):
        for m1 in (0, 1):
            u = correction_unitary(m0, m1)
            assert np.allclose(u @ u.conj().T, IDENTITY, atol=ATOL)
            assert np.allclose(u.conj().T @ u, IDENTITY, atol=ATOL)


def test_branch_11_appends_x_then_z() -> None:
    """Circuit order must be X then Z so the operator is Z . X."""
    circuit = QuantumCircuit(1)
    apply_pauli_correction(circuit, 0, 1, 1)
    names = [instruction.operation.name for instruction in circuit.data]
    assert names == ["x", "z"], names


def test_branch_11_matrix_equals_z_times_x() -> None:
    from qiskit.quantum_info import Operator

    circuit = QuantumCircuit(1)
    apply_pauli_correction(circuit, 0, 1, 1)
    assert np.allclose(np.asarray(Operator(circuit).data), PAULI_MATRICES["Z"] @ PAULI_MATRICES["X"], atol=ATOL)


def test_wrong_order_differs_by_global_phase_minus_one() -> None:
    """Z-then-X realises X . Z, which is -Z . X: a detectable error."""
    from qiskit.quantum_info import Operator

    circuit = QuantumCircuit(1)
    circuit.z(0)
    circuit.x(0)
    wrong = np.asarray(Operator(circuit).data)
    right = PAULI_MATRICES["Z"] @ PAULI_MATRICES["X"]

    assert not np.allclose(wrong, right, atol=1e-9)
    assert np.allclose(wrong, -right, atol=ATOL)


def test_single_gate_branches() -> None:
    x_only = QuantumCircuit(1)
    apply_pauli_correction(x_only, 0, 0, 1)
    assert [i.operation.name for i in x_only.data] == ["x"]

    z_only = QuantumCircuit(1)
    apply_pauli_correction(z_only, 0, 1, 0)
    assert [i.operation.name for i in z_only.data] == ["z"]

    none = QuantumCircuit(1)
    apply_pauli_correction(none, 0, 0, 0)
    assert none.data == []


@pytest.mark.parametrize(
    "count_string,expected",
    [("00", (0, 0)), ("01", (1, 0)), ("10", (0, 1)), ("11", (1, 1))],
)
def test_split_bell_count_string(count_string: str, expected: tuple) -> None:
    """s[0] is c1 (== m1) and s[1] is c0 (== m0)."""
    assert split_bell_count_string(count_string) == expected


@pytest.mark.parametrize("bad", ["0", "000", "2a", "", "1x"])
def test_split_bell_count_string_rejects_malformed(bad: str) -> None:
    with pytest.raises(ValueError):
        split_bell_count_string(bad)


@pytest.mark.parametrize("m0,m1", [(-1, 0), (0, 2), (0.5, 0)])
def test_invalid_bits_are_rejected(m0, m1) -> None:
    with pytest.raises(ValueError):
        correction_unitary(m0, m1)


def test_conditional_correction_builds_without_error() -> None:
    """The feed-forward block must construct and reference the right clbits."""
    circuit = QuantumCircuit(1, 2)
    append_conditional_correction(circuit, 0, circuit.clbits[0], circuit.clbits[1])
    assert len(circuit.data) == 2
    for instruction in circuit.data:
        assert instruction.operation.condition is not None