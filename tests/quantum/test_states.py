"""Tests for the six Pauli eigenstates.

Every assertion checks an independent mathematical property (normalization,
eigenvalue, orthogonality, cross-basis overlap) rather than re-reading values
the module itself produced.
"""

from __future__ import annotations

import numpy as np
import pytest

from backend.quantum.states import (
    EIGENSTATE_LABELS,
    PAULI_MATRICES,
    get_eigenstate,
    pauli_eigenstates,
    pauli_expectation,
    preparation_circuit,
)

ATOL = 1e-12
LABELS = EIGENSTATE_LABELS


ORTHOGONAL_PAIRS = (("|0>", "|1>"), ("|+>", "|->"), ("|+i>", "|-i>"))


def test_six_states_are_registered():
    assert set(LABELS) == {"|0>", "|1>", "|+>", "|->", "|+i>", "|-i>"}
    assert len(pauli_eigenstates()) == 6


@pytest.mark.parametrize("label", LABELS)
def test_normalization(label: str) -> None:
    vector = get_eigenstate(label).vector
    assert np.isclose(float(np.vdot(vector, vector).real), 1.0, atol=ATOL)


@pytest.mark.parametrize("label", LABELS)
def test_pauli_eigenvalue(label: str) -> None:
    """``P|psi> = lambda|psi>`` exactly, for the declared basis and eigenvalue."""
    state = get_eigenstate(label)
    operator = PAULI_MATRICES[state.basis]
    assert np.allclose(operator @ state.vector, state.eigenvalue * state.vector, atol=ATOL)


@pytest.mark.parametrize("label", LABELS)
def test_expectation_equals_eigenvalue(label: str) -> None:
    state = get_eigenstate(label)
    value = pauli_expectation(state.vector, state.basis)
    assert np.isclose(value.real, float(state.eigenvalue), atol=ATOL)
    assert abs(value.imag) < ATOL


@pytest.mark.parametrize("label", LABELS)
def test_other_pauli_expectations_vanish(label: str) -> None:
    """An eigenstate of one Pauli has zero expectation for the other two."""
    state = get_eigenstate(label)
    for other in ("X", "Y", "Z"):
        if other == state.basis:
            continue
        value = pauli_expectation(state.vector, other)
        assert abs(value) < ATOL


def test_y_eigenvalue_relations() -> None:
    """The explicit relations required by the milestone."""
    y = PAULI_MATRICES["Y"]
    plus_i = get_eigenstate("|+i>").vector
    minus_i = get_eigenstate("|-i>").vector

    assert np.allclose(y @ plus_i, +1 * plus_i, atol=ATOL)
    assert np.allclose(y @ minus_i, -1 * minus_i, atol=ATOL)


@pytest.mark.parametrize("left,right", ORTHOGONAL_PAIRS)
def test_same_basis_states_are_orthogonal(left: str, right: str) -> None:
    a = get_eigenstate(left).vector
    b = get_eigenstate(right).vector
    assert abs(np.vdot(a, b)) < ATOL


def test_states_across_bases_are_not_orthogonal() -> None:
    """Non-orthogonality across bases is the resource the protocol will use."""
    pairs = [("|0>", "|+>"), ("|0>", "|+i>"), ("|1>", "|->"), ("|1>", "|-i>"), ("|+>", "|+i>")]
    for left, right in pairs:
        overlap = abs(np.vdot(get_eigenstate(left).vector, get_eigenstate(right).vector))
        assert np.isclose(overlap, 1.0 / np.sqrt(2.0), atol=1e-10), (left, right, overlap)


def test_states_are_pairwise_distinct_up_to_global_phase() -> None:
    for i, left in enumerate(LABELS):
        for right in LABELS[i + 1 :]:
            overlap = abs(np.vdot(get_eigenstate(left).vector, get_eigenstate(right).vector))
            assert not np.isclose(overlap, 1.0, atol=1e-9), (left, right)


def test_negative_plus_i_is_not_a_z_eigenvector() -> None:
    """Regression guard: |+i> must not be treated as a Z eigenstate."""
    vector = get_eigenstate("|+i>").vector
    assert not np.allclose(PAULI_MATRICES["Z"] @ vector, vector, atol=1e-6)


def test_preparation_circuit_reproduces_statevector() -> None:
    """The preparation circuit must yield the declared amplitudes exactly."""
    from qiskit.quantum_info import Statevector

    for label in LABELS:
        state = get_eigenstate(label)
        circuit = preparation_circuit(state.vector)
        produced = np.asarray(Statevector(circuit).data, dtype=complex)

        overlap = np.vdot(produced, state.vector)
        phase = overlap / abs(overlap)
        assert np.allclose(produced, phase * state.vector, atol=1e-10), label


def test_preparation_circuit_rejects_unnormalized_input() -> None:
    with pytest.raises(ValueError):
        preparation_circuit(np.array([1.0, 1.0], dtype=complex))