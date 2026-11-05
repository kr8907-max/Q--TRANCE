"""Tests for the Bell state |Phi+> and its preparation circuit."""

from __future__ import annotations

import numpy as np
import pytest
from qiskit.quantum_info import partial_trace

from backend.quantum.bell import (
    bell_amplitudes_exact,
    bell_circuit,
    bell_density_matrix,
    bell_statevector,
)
from backend.quantum.density import is_pure
from backend.quantum.measure import run_counts

from tests.quantum.statutil import assert_expected_probability, counts_to_probability

ATOL = 1e-12


def test_exact_amplitudes() -> None:
    exact = bell_amplitudes_exact()
    assert exact.shape == (4,)
    assert np.isclose(exact[0], 1.0 / np.sqrt(2.0), atol=ATOL)
    assert np.isclose(exact[3], 1.0 / np.sqrt(2.0), atol=ATOL)

    assert abs(exact[1]) < ATOL
    assert abs(exact[2]) < ATOL


def test_circuit_matches_exact_amplitudes() -> None:
    produced = np.asarray(bell_statevector().data, dtype=complex)
    assert np.allclose(produced, bell_amplitudes_exact(), atol=1e-12)


def test_normalization() -> None:
    vector = np.asarray(bell_statevector().data, dtype=complex)
    assert np.isclose(float(np.sum(np.abs(vector) ** 2)), 1.0, atol=ATOL)


def test_reduced_single_qubit_state_is_maximally_mixed() -> None:
    rho = bell_density_matrix()
    reduced = partial_trace(rho, [0])
    expected = np.eye(2, dtype=complex) / 2.0
    assert np.allclose(np.asarray(reduced.data, dtype=complex), expected, atol=1e-10)


def test_reduced_state_purity_is_one_half() -> None:
    rho = bell_density_matrix()
    reduced = np.asarray(partial_trace(rho, [0]).data, dtype=complex)
    purity = complex(np.trace(reduced @ reduced))
    assert np.isclose(purity.real, 0.5, atol=1e-10)


def test_full_state_is_pure_but_reduced_is_mixed() -> None:
    rho = bell_density_matrix()
    assert is_pure(rho)
    assert not is_pure(partial_trace(rho, [0]))


def test_state_is_entangled_not_a_product() -> None:
    """|Phi+> must not factorise into rho_A (x) rho_B."""
    rho = np.asarray(bell_density_matrix().data, dtype=complex)
    rho_a = np.asarray(partial_trace(bell_density_matrix(), [0]).data, dtype=complex)
    rho_b = np.asarray(partial_trace(bell_density_matrix(), [1]).data, dtype=complex)
    product = np.kron(rho_a, rho_b)
    assert not np.allclose(rho, product, atol=1e-9)


def test_measurement_has_only_00_and_11() -> None:
    circuit = bell_circuit()
    circuit.measure_all()
    counts = run_counts(circuit, shots=4000, seed_simulator=1234)
    assert set(counts) <= {"00", "11"}, counts


def test_measurement_is_balanced() -> None:
    circuit = bell_circuit()
    circuit.measure_all()
    counts = run_counts(circuit, shots=4000, seed_simulator=1234)
    successes, trials = counts_to_probability(counts, "00")
    assert_expected_probability(successes, trials, 0.5)


def test_same_seed_reproduces_identical_counts() -> None:
    def run(seed: int) -> dict:
        circuit = bell_circuit()
        circuit.measure_all()
        return run_counts(circuit, shots=1000, seed_simulator=seed)

    assert run(2024) == run(2024)


def test_different_seeds_agree_on_support() -> None:
    def run(seed: int) -> dict:
        circuit = bell_circuit()
        circuit.measure_all()
        return run_counts(circuit, shots=1000, seed_simulator=seed)

    assert set(run(2024)) == set(run(2025)) == {"00", "11"}


def test_bell_circuit_rejects_identical_qubits() -> None:
    with pytest.raises(ValueError):
        bell_circuit(0, 0)