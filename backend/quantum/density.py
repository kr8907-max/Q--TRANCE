"""Projective-measurement mathematics and fidelity for the quantum core.

Milestone 1 -- verified quantum core.

Definitions
-----------
For a pure expected state ``|psi>``::

    P_psi   = |psi><psi|
    P_perp  = I - P_psi
    p_match = Tr(P_psi rho)
    p_mismatch = 1 - p_match

For a **pure** expected state and any density matrix ``rho`` the analytic
fidelity is ``F = <psi|rho|psi>``, and therefore::

    p_match == F    (identically, not approximately)

These are **the same quantity computed two ways**, not two independent
security signals. ``p_match`` computed from ``rho`` is the analytic value;
the same quantity estimated from finite shot counts is a sampled estimator.
They are kept separate here so the estimator can be compared against the
analytic value, and they must never be reported as independent evidence.
"""

from __future__ import annotations

from typing import Iterable, Sequence

import numpy as np
from qiskit.quantum_info import DensityMatrix, Statevector, partial_trace

__all__ = [
    "as_statevector_array",
    "as_density_matrix",
    "projector",
    "perpendicular_projector",
    "p_match",
    "p_mismatch",
    "fidelity_pure",
    "fidelity_of_pure_states",
    "is_pure",
    "partial_trace_qubits",
]

_I2 = np.eye(2, dtype=complex)


def as_statevector_array(state: Statevector | np.ndarray | Sequence[complex]) -> np.ndarray:
    """Return a normalized complex amplitude vector of length ``2**n``."""
    if isinstance(state, Statevector):
        vector = np.asarray(state.data, dtype=complex)
    else:
        vector = np.asarray(state, dtype=complex)
    vector = vector.reshape(-1)
    if vector.size == 0 or (vector.size & (vector.size - 1)) != 0:
        raise ValueError(f"statevector length must be a power of two, got {vector.size}")
    norm = float(np.linalg.norm(vector))
    if not np.isclose(norm, 1.0, atol=1e-9):
        raise ValueError(f"statevector must be normalized, got norm {norm!r}")
    return vector


def as_density_matrix(rho: DensityMatrix | np.ndarray) -> np.ndarray:
    """Return ``rho`` as a complex matrix, validating shape and trace."""
    matrix = np.asarray(rho.data if isinstance(rho, DensityMatrix) else rho, dtype=complex)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError(f"density matrix must be square, got shape {matrix.shape}")
    trace = complex(np.trace(matrix))
    if not np.isclose(trace.real, 1.0, atol=1e-9) or abs(trace.imag) > 1e-9:
        raise ValueError(f"density matrix must have unit trace, got {trace!r}")
    return matrix


def projector(state: Statevector | np.ndarray | Sequence[complex]) -> np.ndarray:
    """Return ``P_psi = |psi><psi|``."""
    vector = as_statevector_array(state)
    return np.outer(vector, np.conjugate(vector))


def perpendicular_projector(state: Statevector | np.ndarray | Sequence[complex]) -> np.ndarray:
    """Return ``P_perp = I - |psi><psi|``."""
    vector = as_statevector_array(state)
    return np.eye(vector.size, dtype=complex) - projector(vector)


def p_match(rho: DensityMatrix | np.ndarray, psi: Statevector | np.ndarray) -> float:
    """Return ``Tr(P_psi rho)``, the probability of the ``|psi>`` outcome."""
    matrix = as_density_matrix(rho)
    proj = projector(psi)
    if matrix.shape != proj.shape:
        raise ValueError(
            f"rho shape {matrix.shape} does not match projector shape {proj.shape}"
        )
    value = complex(np.trace(proj @ matrix))
    if abs(value.imag) > 1e-9:
        raise ValueError(f"probability has non-negligible imaginary part {value!r}")
    return float(value.real)


def p_mismatch(rho: DensityMatrix | np.ndarray, psi: Statevector | np.ndarray) -> float:
    """Return ``1 - Tr(P_psi rho)``."""
    return 1.0 - p_match(rho, psi)


def fidelity_pure(psi: Statevector | np.ndarray, rho: DensityMatrix | np.ndarray) -> float:
    """Return ``F = <psi|rho|psi>`` for a pure expected state ``|psi>``."""
    vector = as_statevector_array(psi)
    matrix = as_density_matrix(rho)
    if matrix.shape[0] != vector.size:
        raise ValueError(
            f"rho dimension {matrix.shape[0]} does not match state dimension {vector.size}"
        )
    value = complex(np.vdot(vector, matrix @ vector))
    if abs(value.imag) > 1e-9:
        raise ValueError(f"fidelity has non-negligible imaginary part {value!r}")
    return float(value.real)


def fidelity_of_pure_states(
    psi: Statevector | np.ndarray,
    phi: Statevector | np.ndarray,
) -> float:
    """Return ``|<psi|phi>|**2`` for two pure states."""
    a = as_statevector_array(psi)
    b = as_statevector_array(phi)
    if a.size != b.size:
        raise ValueError("states must have the same dimension")
    return float(abs(np.vdot(a, b)) ** 2)


def is_pure(rho: DensityMatrix | np.ndarray, atol: float = 1e-9) -> bool:
    """Return ``True`` when ``Tr(rho**2) == 1`` within ``atol``."""
    matrix = as_density_matrix(rho)
    purity = complex(np.trace(matrix @ matrix))
    return bool(np.isclose(purity.real, 1.0, atol=atol) and abs(purity.imag) < atol)


def partial_trace_qubits(rho: DensityMatrix, qubits: Iterable[int]) -> DensityMatrix:
    """Return the reduced density matrix over ``qubits``."""
    return partial_trace(rho, list(qubits))