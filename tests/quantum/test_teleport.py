"""End-to-end tests of the three-qubit teleportation core.

Two independent verification paths:

* exact analytic branch analysis (no sampling, all four Bell outcomes),
* full circuit execution on Aer with the classical feed-forward present.

The discriminating input states are ``|+i>`` and ``|->`` rather than only
``|0>``/``|1>``: those states separate an X correction from a Z correction,
which computational-basis inputs can mask.
"""

from __future__ import annotations

import numpy as np
import pytest
from qiskit.quantum_info import DensityMatrix

from backend.quantum.density import fidelity_pure
from backend.quantum.states import EIGENSTATE_LABELS, PAULI_MATRICES, get_eigenstate
from backend.quantum.teleport import (
    corrected_branch_states,
    teleport_and_measure,
    teleport_circuit,
    teleport_premeasurement_statevector,
    uncorrected_branch_states,
)

from tests.quantum.statutil import assert_expected_probability, counts_to_probability

ATOL = 1e-10



DAMAGE_TOLERANCE = 1e-6
BRANCHES = ((0, 0), (0, 1), (1, 0), (1, 1))
LABELS = EIGENSTATE_LABELS

DISCRIMINATING = ("|+i>", "|-i>", "|+>", "|->")


BASIS_FOR_LABEL = {
    "|0>": "Z",
    "|1>": "Z",
    "|+>": "X",
    "|->": "X",
    "|+i>": "Y",
    "|-i>": "Y",
}

BIT_FOR_LABEL = {
    "|0>": "0",
    "|1>": "1",
    "|+>": "0",
    "|->": "1",
    "|+i>": "0",
    "|-i>": "1",
}


def _vector(label: str) -> np.ndarray:
    return get_eigenstate(label).vector


def test_premeasurement_state_is_normalized() -> None:
    state = np.asarray(teleport_premeasurement_statevector(_vector("|+i>")).data, dtype=complex)
    assert np.isclose(float(np.sum(np.abs(state) ** 2)), 1.0, atol=ATOL)


def test_premeasurement_state_matches_analytic_branch_decomposition() -> None:
    """The circuit must agree with the analytic Alice/Bob branch decomposition.

    ``teleport_premeasurement_statevector`` returns the state **after** the
    Bell-basis rotation ``CX(0, 1)`` then ``H(0)`` -- not the raw
    ``|psi> (x) |Phi+>`` tensor product. Grouped by Alice's outcome
    ``(m0, m1)`` that state is exactly

        (1/2) * sum_{m0, m1} |m0 m1>_01 (x) (Z**m0 . X**m1)|psi>_2

    Because Qiskit is little-endian, ``|m0 m1>_01`` is the four-vector
    ``e[m0 + 2 * m1]`` and Bob's qubit is the slow index, so each term is
    ``kron(branch_vector, e[m0 + 2 * m1])``.
    """
    basis_vectors = np.eye(4, dtype=complex)
    unitaries = {
        (0, 0): np.eye(2, dtype=complex),
        (0, 1): PAULI_MATRICES["X"],
        (1, 0): PAULI_MATRICES["Z"],
        (1, 1): PAULI_MATRICES["X"] @ PAULI_MATRICES["Z"],
    }

    for label in LABELS:
        psi = _vector(label)
        manual = np.zeros(8, dtype=complex)
        for branch, unitary in unitaries.items():
            m0, m1 = branch
            manual += np.kron(unitary @ psi, basis_vectors[m0 + 2 * m1])
        manual /= 2.0

        produced = np.asarray(teleport_premeasurement_statevector(psi).data, dtype=complex)
        assert np.allclose(produced, manual, atol=ATOL), label


def test_branches_are_equally_likely() -> None:
    """Each Bell outcome must carry probability 1/4."""
    psi = _vector("|+i>")
    full = np.asarray(teleport_premeasurement_statevector(psi).data, dtype=complex)
    branches = full.reshape(2, 2, 2).transpose(2, 1, 0)
    for m0, m1 in BRANCHES:
        probability = float(np.sum(np.abs(branches[m0, m1, :]) ** 2))
        assert np.isclose(probability, 0.25, atol=ATOL), (m0, m1, probability)


@pytest.mark.parametrize("label", LABELS)
def test_uncorrected_branches_match_predicted_states(label: str) -> None:
    """Pre-correction branch states are |psi>, X|psi>, Z|psi>, XZ|psi>."""
    psi = _vector(label)
    observed = uncorrected_branch_states(psi)
    predicted = {
        (0, 0): psi,
        (0, 1): PAULI_MATRICES["X"] @ psi,
        (1, 0): PAULI_MATRICES["Z"] @ psi,
        (1, 1): PAULI_MATRICES["X"] @ PAULI_MATRICES["Z"] @ psi,
    }
    for branch in BRANCHES:
        expected = predicted[branch]
        actual = observed[branch]
        overlap = np.vdot(actual, expected)
        phase = overlap / abs(overlap) if abs(overlap) > 0 else 1.0
        assert np.allclose(actual, phase * expected, atol=ATOL), (label, branch)


NON_TRIVIAL_BRANCHES = ((0, 1), (1, 0), (1, 1))


@pytest.mark.parametrize("label", LABELS)
def test_correction_is_necessary(label: str) -> None:
    """Without the correction, at least one non-trivial branch fails to return |psi>.

    A single branch can coincide with ``|psi>`` by accident whenever ``|psi>``
    is an eigenstate of the Pauli that branch applies: ``Z|0> = |0>``,
    ``X|+> = |+>``, and ``XZ|+i> = -i Y|+i> = -i|+i>``. The property is
    therefore asserted over the set of non-trivial branches -- the correction
    is load-bearing exactly when it is not the identity on every one of them.
    """
    psi = _vector(label)
    uncorrected = uncorrected_branch_states(psi)
    fidelities = {
        branch: float(fidelity_pure(psi, DensityMatrix(uncorrected[branch])))
        for branch in NON_TRIVIAL_BRANCHES
    }
    assert min(fidelities.values()) < 1.0 - DAMAGE_TOLERANCE, (label, fidelities)






DAMAGED_BRANCHES = {
    "|0>": {(0, 1), (1, 1)},
    "|1>": {(0, 1), (1, 1)},
    "|+>": {(1, 0), (1, 1)},
    "|->": {(1, 0), (1, 1)},
    "|+i>": {(0, 1), (1, 0)},
    "|-i>": {(0, 1), (1, 0)},
}


@pytest.mark.parametrize("label", LABELS)
def test_damaged_branch_set_matches_the_pauli_algebra(label: str) -> None:
    """Pin exactly which branches the correction repairs.

    Stronger than asserting "some branch is wrong": it pins the ``XZ = -iY``
    identity, which is why the ``(1, 1)`` branch is harmless for a Y eigenstate
    but not for a computational-basis state.
    """
    psi = _vector(label)
    uncorrected = uncorrected_branch_states(psi)
    observed = {
        branch
        for branch in NON_TRIVIAL_BRANCHES
        if float(fidelity_pure(psi, DensityMatrix(uncorrected[branch]))) < 1.0 - DAMAGE_TOLERANCE
    }
    assert observed == DAMAGED_BRANCHES[label], (label, observed)


@pytest.mark.parametrize("label", ("|+i>", "|-i>"))
def test_y_eigenstate_damaged_branches_are_maximally_wrong(label: str) -> None:
    """For a Y eigenstate the damaged branches are orthogonal to ``|psi>``."""
    psi = _vector(label)
    uncorrected = uncorrected_branch_states(psi)
    for branch in DAMAGED_BRANCHES[label]:
        fidelity = float(fidelity_pure(psi, DensityMatrix(uncorrected[branch])))
        assert np.isclose(fidelity, 0.0, atol=1e-10), (label, branch, fidelity)


@pytest.mark.parametrize("label", LABELS)
@pytest.mark.parametrize("branch", BRANCHES)
def test_corrected_branch_recovers_input_exactly(label: str, branch: tuple) -> None:
    """Exact, phase-sensitive recovery of |psi> for every state and branch."""
    psi = _vector(label)
    recovered = corrected_branch_states(psi)[branch]
    assert np.allclose(recovered, psi, atol=ATOL), (label, branch)


@pytest.mark.parametrize("label", DISCRIMINATING)
def test_discriminating_states_recover_exactly(label: str) -> None:
    psi = _vector(label)
    for branch in BRANCHES:
        assert np.allclose(corrected_branch_states(psi)[branch], psi, atol=ATOL), (label, branch)


@pytest.mark.parametrize("label", LABELS)
def test_swapped_bit_interpretation_fails(label: str) -> None:
    """Regression: reading the bits as X**m0 Z**m1 must NOT recover |psi>."""
    psi = _vector(label)
    uncorrected = uncorrected_branch_states(psi)
    failures = 0
    for branch in BRANCHES:
        m0, m1 = branch
        swapped = (PAULI_MATRICES["Z"] if m1 else np.eye(2)) @ (
            PAULI_MATRICES["X"] if m0 else np.eye(2)
        )
        recovered = swapped @ uncorrected[branch]
        if not np.allclose(recovered, psi, atol=ATOL):
            failures += 1
    assert failures > 0, f"swapped bit interpretation unexpectedly passed for {label}"


@pytest.mark.parametrize("label", LABELS)
def test_shot_based_pipeline_is_deterministic(label: str) -> None:
    """Full Aer run with feed-forward must give the expected bit every shot."""
    basis = BASIS_FOR_LABEL[label]
    expected_bit = BIT_FOR_LABEL[label]

    counts = teleport_and_measure(_vector(label), basis, shots=2000, seed_simulator=1234)
    assert set(counts) == {expected_bit}, (label, counts)
    successes, trials = counts_to_probability(counts, expected_bit)
    assert successes == trials


def test_shot_based_pipeline_matches_analytic_probability() -> None:
    """|+> teleported and measured in X must give 0 with probability 1."""
    counts = teleport_and_measure(_vector("|+>"), "X", shots=1000, seed_simulator=7)
    successes, trials = counts_to_probability(counts, "0")
    assert_expected_probability(successes, trials, 1.0)


def test_control_without_correction_is_random() -> None:
    """Control: dropping the correction destroys the deterministic outcome."""
    psi = _vector("|0>")
    counts = teleport_and_measure(
        psi, "Z", shots=4000, seed_simulator=99, apply_correction=False
    )
    assert set(counts) <= {"0", "1"}, counts
    successes, trials = counts_to_probability(counts, "0")
    assert_expected_probability(successes, trials, 0.5)


def test_correction_makes_the_difference_for_same_seed() -> None:
    """Same seed, correction on vs off: deterministic vs mixed."""
    psi = _vector("|0>")
    with_correction = teleport_and_measure(psi, "Z", shots=2000, seed_simulator=5)
    without_correction = teleport_and_measure(
        psi, "Z", shots=2000, seed_simulator=5, apply_correction=False
    )
    assert set(with_correction) == {"0"}
    assert set(without_correction) == {"0", "1"}


def test_seeded_teleportation_is_reproducible() -> None:
    psi = _vector("|+i>")

    def run(seed: int) -> dict:
        return teleport_and_measure(psi, "Y", shots=500, seed_simulator=seed)

    assert run(2024) == run(2024)


def test_all_four_bell_outcomes_are_observed() -> None:
    """The simulator must actually produce all four Bell outcomes."""
    from backend.quantum.measure import run_counts

    circuit = teleport_circuit(_vector("|+i>"), measure_bob_basis="Y")
    counts = run_counts(circuit, shots=8000, seed_simulator=4242)
    outcomes = {str(key)[1:3] for key in counts}
    assert outcomes == {"00", "01", "10", "11"}, outcomes