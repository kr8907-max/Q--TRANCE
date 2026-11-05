"""Tests for projective-measurement mathematics and fidelity."""

from __future__ import annotations

import numpy as np
import pytest
from qiskit.quantum_info import DensityMatrix, Statevector

from backend.quantum.bell import bell_density_matrix
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
from backend.quantum.states import EIGENSTATE_LABELS, get_eigenstate

ATOL = 1e-12
IDENTITY = np.eye(2, dtype=complex)


@pytest.mark.parametrize("label", EIGENSTATE_LABELS)
def test_projector_is_hermitian_idempotent_trace_one(label: str) -> None:
    proj = projector(get_eigenstate(label).vector)
    assert np.allclose(proj, proj.conj().T, atol=ATOL)
    assert np.allclose(proj @ proj, proj, atol=ATOL)
    assert np.isclose(float(np.trace(proj).real), 1.0, atol=ATOL)


@pytest.mark.parametrize("label", EIGENSTATE_LABELS)
def test_projectors_sum_to_identity(label: str) -> None:
    vector = get_eigenstate(label).vector
    assert np.allclose(projector(vector) + perpendicular_projector(vector), IDENTITY, atol=ATOL)


@pytest.mark.parametrize("label", EIGENSTATE_LABELS)
def test_p_match_and_fidelity_are_identical_for_pure_states(label: str) -> None:
    """For pure expected states ``Tr(P_psi rho) == <psi|rho|psi>`` identically."""
    vector = get_eigenstate(label).vector
    rho = DensityMatrix(vector)
    assert np.isclose(p_match(rho, vector), fidelity_pure(vector, rho), atol=ATOL)


@pytest.mark.parametrize("label", EIGENSTATE_LABELS)
def test_p_match_is_one_for_the_matching_state(label: str) -> None:
    vector = get_eigenstate(label).vector
    assert np.isclose(p_match(DensityMatrix(vector), vector), 1.0, atol=ATOL)
    assert np.isclose(p_mismatch(DensityMatrix(vector), vector), 0.0, atol=ATOL)


def _orthogonal_partner(vector: np.ndarray) -> np.ndarray:
    """Return a normalized state exactly orthogonal to ``vector``.

    Projects a computational-basis vector through ``P_perp = I - |psi><psi|``
    and normalizes. Orthogonality holds by construction, so no case is skipped.
    """
    for candidate in (
        np.array([1.0, 0.0], dtype=complex),
        np.array([0.0, 1.0], dtype=complex),
    ):
        projected = perpendicular_projector(vector) @ candidate
        norm = float(np.linalg.norm(projected))
        if norm > 1e-9:
            return projected / norm
    raise AssertionError("no orthogonal partner exists")  # pragma: no cover


@pytest.mark.parametrize("label", EIGENSTATE_LABELS)
def test_p_match_is_zero_for_the_orthogonal_state(label: str) -> None:
    vector = get_eigenstate(label).vector
    other = _orthogonal_partner(vector)
    assert abs(np.vdot(other, vector)) < 1e-12
    assert np.isclose(p_match(DensityMatrix(other), vector), 0.0, atol=ATOL)
    assert np.isclose(fidelity_pure(vector, DensityMatrix(other)), 0.0, atol=ATOL)


@pytest.mark.parametrize("label", EIGENSTATE_LABELS)
def test_maximally_mixed_gives_one_half(label: str) -> None:
    vector = get_eigenstate(label).vector
    assert np.isclose(p_match(IDENTITY / 2.0, vector), 0.5, atol=ATOL)


def test_probabilities_sum_to_one() -> None:
    vector = get_eigenstate("|+i>").vector
    rho = bell_density_matrix()
    single = partial_trace_qubits(rho, [0])
    assert np.isclose(p_match(single, vector) + p_mismatch(single, vector), 1.0, atol=ATOL)


def test_fidelity_of_identical_pure_states_is_one() -> None:
    for label in EIGENSTATE_LABELS:
        vector = get_eigenstate(label).vector
        assert np.isclose(fidelity_of_pure_states(vector, vector), 1.0, atol=ATOL)


def test_fidelity_of_orthogonal_states_is_zero() -> None:
    assert np.isclose(
        fidelity_of_pure_states(get_eigenstate("|0>").vector, get_eigenstate("|1>").vector),
        0.0,
        atol=ATOL,
    )


def test_purity_flags() -> None:
    assert is_pure(DensityMatrix(get_eigenstate("|+>").vector))
    assert not is_pure(DensityMatrix(IDENTITY / 2.0))


def test_bell_state_reduced_fidelity_is_one_half() -> None:
    """For a maximally entangled pair any local pure state has fidelity 1/2."""
    reduced = partial_trace_qubits(bell_density_matrix(), [0])
    for label in EIGENSTATE_LABELS:
        assert np.isclose(fidelity_pure(get_eigenstate(label).vector, reduced), 0.5, atol=1e-10)


def test_statevector_and_density_representations_agree() -> None:
    vector = get_eigenstate("|+i>").vector
    rho = DensityMatrix(vector)
    assert np.allclose(as_density_matrix(rho), projector(vector), atol=ATOL)
    assert np.allclose(as_statevector_array(Statevector(vector)), vector, atol=ATOL)


def test_unnormalized_state_is_rejected() -> None:
    with pytest.raises(ValueError):
        as_statevector_array(np.array([1.0, 1.0], dtype=complex))


def test_invalid_density_matrix_is_rejected() -> None:
    with pytest.raises(ValueError):
        as_density_matrix(np.array([[2.0, 0.0], [0.0, 0.0]], dtype=complex))


def test_dimension_mismatch_is_rejected() -> None:
    with pytest.raises(ValueError):
        p_match(np.eye(4, dtype=complex) / 4.0, get_eigenstate("|0>").vector)


def test_fidelity_matches_sampled_projective_probability() -> None:
    """Analytic fidelity of a teleported branch equals the sampled estimate."""
    from backend.quantum.measure import measure_statevector
    from backend.quantum.states import get_eigenstate
    from tests.quantum.statutil import assert_expected_probability, counts_to_probability

    vector = get_eigenstate("|+i>").vector
    analytic = p_match(DensityMatrix(vector), vector)
    counts = measure_statevector(vector, "Y", shots=2000, seed_simulator=17)
    successes, trials = counts_to_probability(counts, "0")
    assert_expected_probability(successes, trials, analytic)
    assert np.isclose(analytic, 1.0, atol=ATOL)