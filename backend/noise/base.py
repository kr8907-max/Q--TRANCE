"""Quantum-channel abstraction and honest Pauli noise models.

The channel layer is the only place in the project where a qubit state is
modified by something other than the protocol itself. Everything downstream --
attacks, experiments, and (later) detection -- is expressed in terms of it.

The map
-------
A channel is a completely positive trace-preserving (CPTP) map on density
matrices::

    rho_out = E(rho_in)

Every channel in this package is applied to a **density matrix**, so a channel
that is a probabilistic mixture of unitaries is represented exactly by its
average action, not by a sampled trajectory. That is deliberate: it makes the
channel deterministic, and therefore directly testable, and it keeps sampling
out of the noise layer (see "Where randomness lives" below).

Pauli channels
--------------
All four honest noise models in this package are *Pauli channels*::

    E(rho) = p_I rho + p_X X rho X + p_Y Y rho Y + p_Z Z rho Z

with ``p_I + p_X + p_Y + p_Z = 1`` and every ``p >= 0``. The single free
parameter of each model is mapped onto those four probabilities by the model's
own module; the mapping is *not* the same for all four, and each module
documents its own.

Where randomness lives
----------------------
The modelled channels are deterministic, so ``NoiseConfig`` carries no seed.
This is a deliberate departure from a naive "every config needs a seed" design:
randomness in this project has three distinct homes, and mixing them would
confuse a physical channel parameter with a sampling artefact.

===========================  ==========================================
kind of randomness           where it lives
===========================  ==========================================
cryptographic identifiers    ``backend.protocol.session`` (OS CSPRNG)
simulation sampling          scenario / attack seed, ``simulation.seed``
physical channel parameter   ``NoiseConfig.noise_strength`` (not a sample)
===========================  ==========================================

The same three-way distinction appears in the milestone brief as "do not
confuse physical channel parameter, sampled measurement error, attack
intensity".
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Sequence, Tuple

import numpy as np

from backend.quantum.density import as_density_matrix
from backend.quantum.states import PAULI_MATRICES

__all__ = [
    "PAULI_NAMES",
    "VALID_NOISE_TYPES",
    "NoiseValidationError",
    "PauliProbabilities",
    "QuantumChannel",
    "IdentityChannel",
    "ChannelApplication",
    "NoiseConfig",
    "trace_distance",
    "apply_channel_to_states",
    "require_unit_probability",
    "as_qubit_density_matrix",
]


PAULI_NAMES: Tuple[str, ...] = ("I", "X", "Y", "Z")


VALID_NOISE_TYPES: Tuple[str, ...] = (
    "none",
    "depolarizing",
    "bit_flip",
    "phase_flip",
    "bit_phase_flip",
)

_PROBABILITY_TOLERANCE = 1e-9


class NoiseValidationError(ValueError):
    """Raised when a noise parameter is outside its documented range."""


def _require_probability(value: Any, where: str) -> float:
    """Return ``value`` as a float in ``[0, 1]``, or raise."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise NoiseValidationError(
            f"{where} must be a real number in [0, 1], got {type(value).__name__}"
        )
    number = float(value)
    if not np.isfinite(number):
        raise NoiseValidationError(f"{where} must be finite, got {value!r}")
    if not 0.0 <= number <= 1.0:
        raise NoiseValidationError(f"{where} must lie in [0, 1], got {number!r}")
    return number


def require_unit_probability(value: Any, label: str) -> float:
    """Return ``value`` as a float in ``[0, 1]``.

    Shared by the three flip channels, whose free parameter *is* an error
    probability. The depolarizing channel deliberately does not use this: its
    parameter has a different meaning and a different range.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise NoiseValidationError(
            f"{label} probability must be a real number, got {type(value).__name__}"
        )
    p = float(value)
    if not np.isfinite(p):
        raise NoiseValidationError(f"{label} probability must be finite, got {value!r}")
    if not 0.0 <= p <= 1.0:
        raise NoiseValidationError(
            f"{label} probability must lie in [0, 1], got {p!r}"
        )
    return p


@dataclass(frozen=True)
class PauliProbabilities:
    """Explicit probability table of a single-qubit Pauli channel.

    ``E(rho) = p_i rho + p_x X rho X + p_y Y rho Y + p_z Z rho Z``
    """

    p_i: float
    p_x: float
    p_y: float
    p_z: float

    def validate(self) -> "PauliProbabilities":
        """Validate every probability and that the table is normalised."""
        for name, value in (
            ("p_i", self.p_i),
            ("p_x", self.p_x),
            ("p_y", self.p_y),
            ("p_z", self.p_z),
        ):
            _require_probability(value, f"PauliProbabilities.{name}")
        total = float(self.p_i) + float(self.p_x) + float(self.p_y) + float(self.p_z)
        if abs(total - 1.0) > _PROBABILITY_TOLERANCE:
            raise NoiseValidationError(
                f"Pauli probabilities must sum to 1, got {total!r}"
            )
        return self

    def as_dict(self) -> Dict[str, float]:
        return {
            "p_i": float(self.p_i),
            "p_x": float(self.p_x),
            "p_y": float(self.p_y),
            "p_z": float(self.p_z),
        }

    def error_probability(self) -> float:
        """Total probability that a non-identity Pauli is applied."""
        return float(self.p_x) + float(self.p_y) + float(self.p_z)


class QuantumChannel(ABC):
    """A CPTP map on single-qubit density matrices.

    Subclasses supply a name, a documented parameterisation and the resulting
    :class:`PauliProbabilities`. The application itself is defined once, here.
    """


    name: str = "channel"

    def __init__(self, probabilities: PauliProbabilities) -> None:
        self._probabilities = probabilities.validate()

    @property
    def probabilities(self) -> PauliProbabilities:
        return self._probabilities

    def apply(self, state: Any) -> np.ndarray:
        """Return ``E(rho)`` for a density matrix or a pure state vector.

        A length-2 vector is interpreted as a pure state and converted with
        ``|psi><psi|``. The result is always a 2x2 complex density matrix.
        """
        rho = as_qubit_density_matrix(state)
        probabilities = self._probabilities
        output = probabilities.p_i * rho
        for pauli, weight in (
            ("X", probabilities.p_x),
            ("Y", probabilities.p_y),
            ("Z", probabilities.p_z),
        ):
            if weight:
                operator = PAULI_MATRICES[pauli]
                output = output + weight * (operator @ rho @ operator)
        return _as_density_matrix_checked(output)

    def describe(self) -> Dict[str, Any]:
        """Return the physical description of the configured process."""
        return {
            "channel": self.name,
            "pauli_probabilities": self._probabilities.as_dict(),
            "error_probability": self._probabilities.error_probability(),
        }

    def apply_with_metadata(self, state: Any) -> "ChannelApplication":
        """Return the input, the output and the process description together."""
        rho = as_qubit_density_matrix(state)
        return ChannelApplication(
            channel=self.name,
            parameters=self.describe(),
            input_state=rho,
            output_state=self.apply(rho),
        )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"{type(self).__name__}({self._probabilities.as_dict()})"


class IdentityChannel(QuantumChannel):
    """The ideal channel: ``E(rho) = rho``."""

    name = "none"

    def __init__(self) -> None:
        super().__init__(PauliProbabilities(1.0, 0.0, 0.0, 0.0))


@dataclass(frozen=True)
class ChannelApplication:
    """One application of a channel: input, output and process metadata.

    The metadata describes the *physical process* (which channel, with which
    probabilities). It never carries an attack label, and the experiment runner
    never copies it into observable evidence -- see
    ``backend.simulation.results.ObservableExperimentData``.
    """

    channel: str
    parameters: Mapping[str, Any]
    input_state: np.ndarray
    output_state: np.ndarray

    def trace_distance(self) -> float:
        """Return ``T(input, output)``, the disturbance this application caused."""
        return trace_distance(self.input_state, self.output_state)

    def describe(self) -> Dict[str, Any]:
        return {
            "channel": self.channel,
            "parameters": dict(self.parameters),
            "trace_distance": self.trace_distance(),
        }


@dataclass(frozen=True)
class NoiseConfig:
    """Configuration of an honest noise model.

    ``noise_strength`` is the model's own parameter; its meaning and valid
    range are documented per model. It is a *physical* quantity, not a
    threshold, not a security limit, and not an attack intensity.
    """

    noise_type: str = "none"
    noise_strength: float = 0.0

    def validate(self) -> "NoiseConfig":
        if not isinstance(self.noise_type, str) or self.noise_type not in VALID_NOISE_TYPES:
            raise NoiseValidationError(
                f"noise_type must be one of {list(VALID_NOISE_TYPES)}, "
                f"got {self.noise_type!r}"
            )
        if isinstance(self.noise_strength, bool) or not isinstance(
            self.noise_strength, (int, float)
        ):
            raise NoiseValidationError(
                f"noise_strength must be a real number, got "
                f"{type(self.noise_strength).__name__}"
            )
        strength = float(self.noise_strength)
        if not np.isfinite(strength):
            raise NoiseValidationError(f"noise_strength must be finite, got {strength!r}")
        if self.noise_type == "none":
            if strength != 0.0:
                raise NoiseValidationError(
                    "noise_type 'none' requires noise_strength 0.0, "
                    f"got {strength!r}"
                )
        elif strength < 0.0:
            raise NoiseValidationError(
                f"noise_strength must be non-negative, got {strength!r}"
            )
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            "noise_type": self.noise_type,
            "noise_strength": float(self.noise_strength),
        }

    @classmethod
    def from_dict(cls, data: Any) -> "NoiseConfig":
        if not isinstance(data, dict):
            raise NoiseValidationError(
                f"noise config must be an object, got {type(data).__name__}"
            )
        unknown = sorted(set(data) - {"noise_type", "noise_strength"})
        if unknown:
            raise NoiseValidationError(f"noise config has unknown fields {unknown}")
        try:
            config = cls(
                noise_type=data.get("noise_type", "none"),
                noise_strength=data.get("noise_strength", 0.0),
            )
        except NoiseValidationError:
            raise
        return config.validate()


def trace_distance(rho: Any, sigma: Any) -> float:
    """Return ``T(rho, sigma) = 1/2 * Tr|rho - sigma|`` for two qubit states.

    The value lies in ``[0, 1]`` for density matrices. It is used as the raw
    "how much did the channel change this state" statistic in experiment
    results; it is a measurement, not a judgement.
    """
    left = as_qubit_density_matrix(rho)
    right = as_qubit_density_matrix(sigma)
    difference = left - right
    eigenvalues = np.linalg.eigvalsh((difference + difference.conj().T) / 2.0)
    return float(np.sum(np.abs(eigenvalues)) / 2.0)


def apply_channel_to_states(
    channel: QuantumChannel,
    states: Sequence[Any],
) -> Tuple[np.ndarray, ...]:
    """Apply ``channel`` to every state, returning a tuple of density matrices."""
    return tuple(channel.apply(state) for state in states)


def as_qubit_density_matrix(state: Any) -> np.ndarray:
    """Coerce a pure vector or density matrix to a validated 2x2 matrix."""
    if isinstance(state, np.ndarray) and state.shape == (2,):
        vector = np.asarray(state, dtype=complex).reshape(2)
        norm = float(np.linalg.norm(vector))
        if not np.isclose(norm, 1.0, atol=1e-9):
            raise NoiseValidationError(
                f"state vector must be normalised, got norm {norm!r}"
            )
        return np.outer(vector, np.conjugate(vector))
    matrix = as_density_matrix(state)
    if matrix.shape != (2, 2):
        raise NoiseValidationError(
            f"this channel acts on one qubit; expected a 2x2 matrix, got "
            f"{matrix.shape}"
        )
    return matrix


def _as_density_matrix_checked(matrix: np.ndarray) -> np.ndarray:
    """Validate that a channel output is a legitimate density matrix."""
    result = np.asarray(matrix, dtype=complex)
    trace = complex(np.trace(result))
    if not np.isclose(trace.real, 1.0, atol=1e-9) or abs(trace.imag) > 1e-9:
        raise AssertionError(
            f"channel output is not trace preserving: trace {trace!r}"
        )
    if not np.allclose(result, result.conj().T, atol=1e-9):
        raise AssertionError("channel output is not Hermitian")
    return result
