"""Regression tests that pin the Qiskit bit-ordering convention empirically.

The audit established this behaviour on Qiskit 2.5.2 / Aer 0.17.2 / CPython
3.13.5. It is asserted here so that a future Qiskit change is caught rather
than silently corrupting the correction logic.

Verified convention
-------------------
For ``circuit.measure([q0, q1], [c0, c1])`` the returned count string is
ordered by **classical-bit index with the highest clbit leftmost**. So
``s[0]`` is ``c1`` and ``s[1]`` is ``c0``.

The decisive experiment permutes the qubit-to-clbit mapping. With the
identity mapping both candidate conventions predict the same string, which is
why the first probe was inconclusive; only the permuted mapping separates
"ordered by clbit index" from "ordered by qubit index".
"""

from __future__ import annotations

from qiskit import QuantumCircuit

from backend.quantum.measure import run_counts
from backend.quantum.states import get_eigenstate
from backend.quantum.teleport import teleport_circuit, uncorrected_branch_states

from tests.quantum.statutil import assert_expected_probability

SHOTS = 256
SEED = 42

BELL_BRANCHES = ("00", "01", "10", "11")


def test_identity_mapping_is_ambiguous_by_construction() -> None:
    """x on q1 with measure([0,1],[0,1]) yields '10' under either convention."""
    circuit = QuantumCircuit(2, 2)
    circuit.x(1)
    circuit.measure([0, 1], [0, 1])
    counts = run_counts(circuit, shots=SHOTS, seed_simulator=SEED)
    assert set(counts) == {"10"}, counts


def test_permuted_mapping_decides_the_convention() -> None:
    """x on q0 with q0->c1, q1->c0 yields '10' only under clbit ordering.

    Ordered by clbit index (highest leftmost): c1=1, c0=0 -> '10'.
    Ordered by qubit index (highest leftmost): q1=0, q0=1 -> '01'.
    """
    circuit = QuantumCircuit(2, 2)
    circuit.x(0)
    circuit.measure([0, 1], [1, 0])
    counts = run_counts(circuit, shots=SHOTS, seed_simulator=SEED)
    assert set(counts) == {"10"}, counts


def test_inverse_permutation_is_consistent() -> None:
    """The mirror experiment: x on q1 with q1->c0 gives '01'."""
    circuit = QuantumCircuit(2, 2)
    circuit.x(1)
    circuit.measure([1, 0], [0, 1])
    counts = run_counts(circuit, shots=SHOTS, seed_simulator=SEED)
    assert set(counts) == {"01"}, counts


def test_count_string_length_matches_number_of_clbits() -> None:
    circuit = QuantumCircuit(3, 3)
    circuit.x([0, 1, 2])
    circuit.measure([0, 1, 2], [0, 1, 2])
    counts = run_counts(circuit, shots=SHOTS, seed_simulator=SEED)
    assert set(counts) == {"111"}, counts
    assert all(len(key) == 3 for key in counts)


def test_teleport_count_string_layout() -> None:
    """In the teleport circuit the three-character key is (c2, c1, c0)."""
    circuit = teleport_circuit(get_eigenstate("|+i>").vector, measure_bob_basis="Y")
    counts = run_counts(circuit, shots=4000, seed_simulator=SEED)
    assert all(len(key) == 3 for key in counts)

    bobs = {str(key)[0] for key in counts}
    assert bobs <= {"0", "1"}

    assert bobs == {"0"}, counts


def test_branch_extraction_matches_count_statistics() -> None:
    """Analytic branch probabilities must match the simulated Bell outcomes.

    The tolerance is the exact Clopper-Pearson binomial interval at the suite
    default confidence (``tests/quantum/statutil.py``), not an arbitrary
    percentage band.
    """
    vector = get_eigenstate("|0>").vector
    circuit = teleport_circuit(vector, measure_bob_basis="Z")
    counts = run_counts(circuit, shots=8000, seed_simulator=SEED)

    observed: dict[str, int] = {}
    for key, value in counts.items():
        branch = str(key)[1:3]
        observed[branch] = observed.get(branch, 0) + int(value)

    total = sum(observed.values())
    assert total == 8000, total
    assert set(observed) == set(BELL_BRANCHES), observed
    for branch in BELL_BRANCHES:
        assert_expected_probability(observed[branch], total, 0.25)


    assert set(uncorrected_branch_states(vector)) == {(0, 0), (0, 1), (1, 0), (1, 1)}


def test_bit_ordering_is_reproducible() -> None:
    def run(seed: int) -> dict:
        circuit = QuantumCircuit(2, 2)
        circuit.h(0)
        circuit.cx(0, 1)
        circuit.measure([0, 1], [0, 1])
        return run_counts(circuit, shots=777, seed_simulator=seed)

    assert run(2024) == run(2024)