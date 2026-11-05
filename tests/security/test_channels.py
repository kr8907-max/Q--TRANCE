"""Tests for the quantum noise channel layer.

Milestone 3 -- channel abstraction and honest noise models.
"""

from __future__ import annotations

import numpy as np
import pytest

from backend.noise import (
    BitFlipChannel,
    BitPhaseFlipChannel,
    DepolarizingChannel,
    NoiseConfig,
    NoiseValidationError,
    PhaseFlipChannel,
    build_noise_channel,
    trace_distance,
)
from backend.quantum.density import projector
from backend.quantum.states import get_eigenstate

I2 = np.eye(2, dtype=complex)
X = np.array([[0, 1], [1, 0]], dtype=complex)
Y = np.array([[0, -1j], [1j, 0]], dtype=complex)
Z = np.array([[1, 0], [0, -1]], dtype=complex)

S = 1 / np.sqrt(2)
STATES = {
    "|0>": np.array([1, 0], dtype=complex),
    "|1>": np.array([0, 1], dtype=complex),
    "|+>": np.array([S, S], dtype=complex),
    "|->": np.array([S, -S], dtype=complex),
    "|+i>": np.array([S, 1j * S], dtype=complex),
    "|-i>": np.array([S, -1j * S], dtype=complex),
}


def rho_of(v: np.ndarray) -> np.ndarray:
    return np.outer(v, v.conj())







class TestIdealChannel:
    def test_none_is_identity(self) -> None:
        ch = build_noise_channel(NoiseConfig("none", 0.0))
        for v in STATES.values():
            rho = rho_of(v)
            assert np.allclose(ch.apply(rho), rho)

    def test_none_rejects_nonzero_strength(self) -> None:
        with pytest.raises(NoiseValidationError):
            build_noise_channel(NoiseConfig("none", 0.1))







class TestDepolarizing:
    def test_zero_is_identity(self) -> None:
        ch = DepolarizingChannel(0.0)
        for v in STATES.values():
            rho = rho_of(v)
            assert np.allclose(ch.apply(rho), rho)

    def test_full_depolarization_is_maximally_mixed(self) -> None:
        ch = DepolarizingChannel(1.0)
        for v in STATES.values():
            rho = rho_of(v)
            assert np.allclose(ch.apply(rho), I2 / 2)

    def test_half_depolarization(self) -> None:
        ch = DepolarizingChannel(0.5)
        for v in STATES.values():
            rho = rho_of(v)
            out = ch.apply(rho)

            expected = 0.625 * rho + 0.125 * (X @ rho @ X + Y @ rho @ Y + Z @ rho @ Z)
            assert np.allclose(out, expected)

    def test_probability_table_sums_to_one(self) -> None:
        for p in (0.0, 0.25, 0.5, 1.0):
            pr = DepolarizingChannel(p).probabilities
            assert pr.p_i + pr.p_x + pr.p_y + pr.p_z == pytest.approx(1.0)

    def test_invalid_parameters(self) -> None:
        for bad in (-0.1, 1.1, "x", None, True):
            with pytest.raises(NoiseValidationError):
                DepolarizingChannel(bad)

    def test_trace_preserved(self) -> None:
        ch = DepolarizingChannel(0.3)
        for v in STATES.values():
            rho = rho_of(v)
            assert np.isclose(np.trace(ch.apply(rho)), 1.0)

    def test_output_is_hermitian(self) -> None:
        ch = DepolarizingChannel(0.3)
        for v in STATES.values():
            rho = rho_of(v)
            out = ch.apply(rho)
            assert np.allclose(out, out.conj().T)







class TestBitFlip:
    def test_zero_is_identity(self) -> None:
        ch = BitFlipChannel(0.0)
        for v in STATES.values():
            rho = rho_of(v)
            assert np.allclose(ch.apply(rho), rho)

    def test_full_flip(self) -> None:
        ch = BitFlipChannel(1.0)
        for v in STATES.values():
            rho = rho_of(v)
            assert np.allclose(ch.apply(rho), X @ rho @ X)

    def test_half_flip(self) -> None:
        ch = BitFlipChannel(0.5)
        for v in STATES.values():
            rho = rho_of(v)
            out = ch.apply(rho)
            expected = 0.5 * rho + 0.5 * (X @ rho @ X)
            assert np.allclose(out, expected)

    def test_invalid_parameters(self) -> None:
        for bad in (-0.1, 1.1, "x"):
            with pytest.raises(NoiseValidationError):
                BitFlipChannel(bad)

    def test_trace_and_hermiticity(self) -> None:
        ch = BitFlipChannel(0.4)
        for v in STATES.values():
            rho = rho_of(v)
            out = ch.apply(rho)
            assert np.isclose(np.trace(out), 1.0)
            assert np.allclose(out, out.conj().T)







class TestPhaseFlip:
    def test_zero_is_identity(self) -> None:
        ch = PhaseFlipChannel(0.0)
        for v in STATES.values():
            rho = rho_of(v)
            assert np.allclose(ch.apply(rho), rho)

    def test_full_flip(self) -> None:
        ch = PhaseFlipChannel(1.0)
        for v in STATES.values():
            rho = rho_of(v)
            assert np.allclose(ch.apply(rho), Z @ rho @ Z)

    def test_half_flip(self) -> None:
        ch = PhaseFlipChannel(0.5)
        for v in STATES.values():
            rho = rho_of(v)
            out = ch.apply(rho)
            expected = 0.5 * rho + 0.5 * (Z @ rho @ Z)
            assert np.allclose(out, expected)

    def test_invalid_parameters(self) -> None:
        for bad in (-0.1, 1.1):
            with pytest.raises(NoiseValidationError):
                PhaseFlipChannel(bad)

    def test_trace_and_hermiticity(self) -> None:
        ch = PhaseFlipChannel(0.4)
        for v in STATES.values():
            rho = rho_of(v)
            out = ch.apply(rho)
            assert np.isclose(np.trace(out), 1.0)
            assert np.allclose(out, out.conj().T)







class TestBitPhaseFlip:
    def test_zero_is_identity(self) -> None:
        ch = BitPhaseFlipChannel(0.0)
        for v in STATES.values():
            rho = rho_of(v)
            assert np.allclose(ch.apply(rho), rho)

    def test_full_flip(self) -> None:
        ch = BitPhaseFlipChannel(1.0)
        for v in STATES.values():
            rho = rho_of(v)
            assert np.allclose(ch.apply(rho), Y @ rho @ Y)

    def test_half_is_maximally_mixed_for_non_y_eigenstates(self) -> None:
        """At p=1/2 the Y channel averages rho with Y rho Y.

        For a Y eigenstate this is a fixed point (not I/2).  For any state
        orthogonal in the Bloch sphere it becomes I/2.  We check the non-Y
        eigenstates explicitly.
        """
        ch = BitPhaseFlipChannel(0.5)
        for name, v in STATES.items():
            rho = rho_of(v)
            out = ch.apply(rho)
            if name in ("|+i>", "|-i>"):

                assert np.allclose(out, rho)
            else:
                assert np.allclose(out, I2 / 2)

    def test_invalid_parameters(self) -> None:
        for bad in (-0.1, 1.1):
            with pytest.raises(NoiseValidationError):
                BitPhaseFlipChannel(bad)

    def test_trace_and_hermiticity(self) -> None:
        ch = BitPhaseFlipChannel(0.4)
        for v in STATES.values():
            rho = rho_of(v)
            out = ch.apply(rho)
            assert np.isclose(np.trace(out), 1.0)
            assert np.allclose(out, out.conj().T)







class TestFactory:
    def test_build_all_types(self) -> None:
        for t, s in (("none", 0.0), ("depolarizing", 0.1), ("bit_flip", 0.2),
                     ("phase_flip", 0.3), ("bit_phase_flip", 0.4)):
            ch = build_noise_channel(NoiseConfig(t, s))
            assert ch is not None

    def test_build_rejects_unknown_type(self) -> None:
        with pytest.raises(NoiseValidationError):
            build_noise_channel(NoiseConfig("unknown", 0.1))







class TestTraceDistance:
    def test_identical_states(self) -> None:
        rho = rho_of(STATES["|0>"])
        assert trace_distance(rho, rho) == pytest.approx(0.0)

    def test_orthogonal_states(self) -> None:
        rho0 = rho_of(STATES["|0>"])
        rho1 = rho_of(STATES["|1>"])
        assert trace_distance(rho0, rho1) == pytest.approx(1.0)

    def test_non_hermitian_input_raises(self) -> None:
        bad = np.array([[1, 2], [3, 4]], dtype=complex)
        with pytest.raises(ValueError):
            trace_distance(bad, bad)

    def test_non_unit_trace_raises(self) -> None:
        bad = np.array([[2, 0], [0, 0]], dtype=complex)
        with pytest.raises(ValueError):
            trace_distance(bad, bad)
