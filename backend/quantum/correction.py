"""Pauli corrections for the teleportation protocol.

Milestone 1 -- verified quantum core.

Convention (fixed here, derived and asserted by the test suite)
---------------------------------------------------------------
Alice measures her two qubits and obtains classical bits ``m0`` (outcome of
``q0``, the input qubit that received the final Hadamard) and ``m1`` (outcome
of ``q1``). Bob must then apply

    U(m0, m1) = Z**m0 . X**m1

where ``.`` is matrix multiplication, so Z sits on the *left*.

Circuit order is the reverse of matrix-product order, therefore the circuit
must append **X first, then Z**. Appending Z first would realise
``X . Z = -Z . X``, i.e. the correct unitary only up to a global phase of -1.
That is invisible to any probability/fidelity comparison but visible to a
phase-sensitive statevector comparison in the branch ``m0 = m1 = 1``.

Outcome table::

    (m0, m1)    U(m0, m1)    gates appended to Bob's qubit
    (0, 0)      I            (none)
    (0, 1)      X            x
    (1, 0)      Z            z
    (1, 1)      Z . X        x  then  z

Derivation
----------
Writing the initial state as ``|psi>_0 (x) |Phi+>_{12}`` and applying
``CX(0,1)`` then ``H(0)`` gives, grouped by Alice's outcome ``(m0, m1)``,
Bob's uncorrected qubit state::

    (0, 0) :  |psi>
    (0, 1) :  X|psi>
    (1, 0) :  Z|psi>
    (1, 1) :  XZ|psi>  =  -ZX|psi>

Each branch has probability 1/4. Since ``(ZX)(XZ) = I``, ``(X)(X) = I`` and
``(Z)(Z) = I``, applying ``U(m0, m1) = Z**m0 X**m1`` recovers ``|psi>``
exactly in all four branches. This is verified numerically in
``tests/quantum/test_teleport.py``.

Count-string convention
-----------------------
For ``circuit.measure([q0, q1], [c0, c1])`` the returned count string is
ordered by **classical-bit index with the highest clbit leftmost**, so
``s[0]`` is ``c1`` and ``s[1]`` is ``c0``. Therefore ``m0 = s[1]`` and
``m1 = s[0]``. This is verified empirically in
``tests/quantum/test_bit_ordering.py``, not assumed from documentation.
"""

from __future__ import annotations

from typing import Dict, Tuple

import numpy as np
from qiskit.circuit import Clbit, QuantumCircuit

from backend.quantum.states import PAULI_MATRICES

__all__ = [
    "CORRECTION_TABLE",
    "correction_label",
    "correction_unitary",
    "apply_pauli_correction",
    "append_conditional_correction",
    "split_bell_count_string",
]



CORRECTION_TABLE: Dict[Tuple[int, int], str] = {
    (0, 0): "I",
    (0, 1): "X",
    (1, 0): "Z",
    (1, 1): "ZX",
}

_IDENTITY_2 = np.eye(2, dtype=complex)


def _bit(value: int, name: str) -> int:
    if value not in (0, 1):
        raise ValueError(f"{name} must be 0 or 1, got {value!r}")
    return int(value)


def correction_label(m0: int, m1: int) -> str:
    """Return the Pauli word ``"I"``, ``"X"``, ``"Z"`` or ``"ZX"`` for ``(m0, m1)``."""
    return CORRECTION_TABLE[(_bit(m0, "m0"), _bit(m1, "m1"))]


def correction_unitary(m0: int, m1: int) -> np.ndarray:
    """Return the 2x2 operator ``Z**m0 . X**m1`` that Bob must apply.

    This is the matrix, not the circuit gate order; see the module docstring.
    """
    m0 = _bit(m0, "m0")
    m1 = _bit(m1, "m1")
    z_part = PAULI_MATRICES["Z"] if m0 else _IDENTITY_2
    x_part = PAULI_MATRICES["X"] if m1 else _IDENTITY_2
    return z_part @ x_part


def apply_pauli_correction(circuit: QuantumCircuit, qubit: int, m0: int, m1: int) -> QuantumCircuit:
    """Append the correction for ``(m0, m1)`` to ``circuit`` acting on ``qubit``.

    Gates are appended X-then-Z so the resulting operator is ``Z**m0 . X**m1``,
    because circuit order reverses matrix-product order.
    """
    m0 = _bit(m0, "m0")
    m1 = _bit(m1, "m1")
    if m1:
        circuit.x(qubit)
    if m0:
        circuit.z(qubit)
    return circuit


def append_conditional_correction(
    circuit: QuantumCircuit,
    qubit: int,
    clbit_m0: Clbit,
    clbit_m1: Clbit,
) -> QuantumCircuit:
    """Append the feed-forward correction controlled on Alice's two classical bits.

    ``clbit_m1`` controls the X (appended first), ``clbit_m0`` controls the Z
    (appended second), yielding ``Z**m0 . X**m1``.
    """
    with circuit.if_test((clbit_m1, 1)):
        circuit.x(qubit)
    with circuit.if_test((clbit_m0, 1)):
        circuit.z(qubit)
    return circuit


def split_bell_count_string(count_string: str) -> Tuple[int, int]:
    """Split a two-bit Bell count string into ``(m0, m1)``.

    Assumes ``measure([q0, q1], [c0, c1])`` and the empirically verified
    convention that the string is ordered by clbit index with the highest
    clbit leftmost: ``s[0] == c1 == m1`` and ``s[1] == c0 == m0``.
    """
    if len(count_string) != 2 or set(count_string) - {"0", "1"}:
        raise ValueError(f"expected a 2-bit binary string, got {count_string!r}")
    m1 = int(count_string[0])
    m0 = int(count_string[1])
    return m0, m1
