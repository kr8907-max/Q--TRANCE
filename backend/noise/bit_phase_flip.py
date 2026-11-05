"""Bit-phase-flip channel.

Mathematical definition
-----------------------
A Pauli channel with the probability table::

    p_I = 1 - p        p_X = 0        p_Y = p        p_Z = 0

equivalently::

    E(rho) = (1 - p) rho + p * Y rho Y

``p`` is the probability that the Pauli ``Y`` is applied. As with the bit-flip
and phase-flip channels, ``p`` **is** an error probability -- unlike the
depolarizing channel's parameter.

Valid range
-----------
``0 <= p <= 1``.

Reference points
----------------
``p = 0``    identity channel.
``p = 1``    ``E(rho) = Y rho Y``: a simultaneous bit and phase flip.
``p = 1/2``  ``E(rho) = (rho + Y rho Y)/2``. This equals ``I/2`` for the ``Z``
             and ``X`` eigenstates, but leaves the ``Y`` eigenstates ``|+i>``
             and ``|-i>`` **unchanged** -- they are fixed points of the channel.

That last point matters for experiment design, exactly as the phase-flip
channel is invisible to a Z-basis measurement: a ``Y`` channel is invisible to
a Y-basis measurement. The experiment runner measures each state in the basis
the protocol derived for it, so how much disturbance a given channel produces is
a joint property of the channel and the state sequence, not of the channel
alone.

The ``Y`` channel is the *joint* flip: since ``Y = iXZ``, ``Y rho Y = XZ rho ZX``,
so it flips the computational bit **and** the relative phase at once. It is the
one Pauli error that a Z-basis or an X-basis measurement alone cannot separate
from the other two, which is why it appears in its own module rather than as a
combination of the two flip channels.

``p`` is a physical channel parameter, not a measurement error rate, not an
attack intensity and not a security threshold.
"""

from __future__ import annotations

from backend.noise.base import PauliProbabilities, QuantumChannel, require_unit_probability

__all__ = ["BitPhaseFlipChannel"]


class BitPhaseFlipChannel(QuantumChannel):
    """``E(rho) = (1 - p) rho + p Y rho Y`` with ``0 <= p <= 1``."""

    name = "bit_phase_flip"

    def __init__(self, strength: float = 0.0) -> None:
        p = require_unit_probability(strength, "bit-phase-flip")
        self._strength = p
        super().__init__(PauliProbabilities(p_i=1.0 - p, p_x=0.0, p_y=p, p_z=0.0))

    @property
    def strength(self) -> float:
        """The bit-phase-flip probability ``p``."""
        return self._strength

    def describe(self) -> dict:
        description = super().describe()
        description["strength"] = self._strength
        description["strength_meaning"] = "probability that Y is applied"
        description["valid_range"] = [0.0, 1.0]
        return description
