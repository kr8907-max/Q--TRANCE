"""Honest noise models and the quantum-channel abstraction.

This package contains only *honest* channel models: processes that act on a
qubit regardless of any adversary. Adversarial channel effects live in
:mod:`backend.attacks`; they use the same :class:`~backend.noise.base.QuantumChannel`
abstraction but are never described as noise.

Dependency direction::

    backend.quantum  ->  backend.protocol  ->  backend.noise  ->  backend.attacks

``backend.noise`` imports ``backend.quantum`` and nothing else from this
project. It does not import ``backend.attacks``, ``backend.simulation``, or any
future detection module.
"""

from backend.noise.base import (
    PAULI_NAMES,
    VALID_NOISE_TYPES,
    ChannelApplication,
    IdentityChannel,
    NoiseConfig,
    NoiseValidationError,
    PauliProbabilities,
    QuantumChannel,
    apply_channel_to_states,
    require_unit_probability,
    trace_distance,
)
from backend.noise.bit_flip import BitFlipChannel
from backend.noise.bit_phase_flip import BitPhaseFlipChannel
from backend.noise.depolarizing import (
    DEPOLARIZING_MAX_STRENGTH,
    DepolarizingChannel,
)
from backend.noise.phase_flip import PhaseFlipChannel

__all__ = [
    "PAULI_NAMES",
    "VALID_NOISE_TYPES",
    "DEPOLARIZING_MAX_STRENGTH",
    "ChannelApplication",
    "IdentityChannel",
    "NoiseConfig",
    "NoiseValidationError",
    "PauliProbabilities",
    "QuantumChannel",
    "BitFlipChannel",
    "BitPhaseFlipChannel",
    "DepolarizingChannel",
    "PhaseFlipChannel",
    "apply_channel_to_states",
    "require_unit_probability",
    "trace_distance",
    "build_noise_channel",
]


def build_noise_channel(config: NoiseConfig) -> QuantumChannel:
    """Return the channel described by ``config``.

    ``noise_type="none"`` gives the identity channel regardless of strength
    (which :meth:`NoiseConfig.validate` requires to be zero).

    Raises :class:`~backend.noise.base.NoiseValidationError` for an unknown type
    or an out-of-range strength. Nothing is silently coerced or clamped.
    """
    config = config.validate()
    if config.noise_type == "none":
        return IdentityChannel()
    if config.noise_type == "depolarizing":
        return DepolarizingChannel(config.noise_strength)
    if config.noise_type == "bit_flip":
        return BitFlipChannel(config.noise_strength)
    if config.noise_type == "phase_flip":
        return PhaseFlipChannel(config.noise_strength)
    if config.noise_type == "bit_phase_flip":
        return BitPhaseFlipChannel(config.noise_strength)


    raise NoiseValidationError(
        f"noise_type {config.noise_type!r} has no registered channel"
    )
