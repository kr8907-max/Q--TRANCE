"""Bit-flip channel.

Mathematical definition
-----------------------
A Pauli channel with the probability table::

    p_I = 1 - p        p_X = p        p_Y = 0        p_Z = 0

equivalently::

    E(rho) = (1 - p) rho + p * X rho X

``p`` **is** the probability of an error here: with probability ``p`` the
channel applies the Pauli ``X``, and with probability ``1 - p`` it does nothing.
This differs from the depolarizing channel in this package, where the free
parameter is not an error probability. Do not assume one formula covers all
four models.

Valid range
-----------
``0 <= p <= 1``.

Reference points
----------------
``p = 0``    identity channel.
``p = 1``    ``E(rho) = X rho X``: a deterministic bit flip.
``p = 1/2``  ``E(|0><0|) = I/2``, the maximally mixed state.

``p`` is a physical channel parameter, not a measurement error rate, not an
attack intensity and not a security threshold.
"""

from __future__ import annotations

from backend.noise.base import PauliProbabilities, QuantumChannel, require_unit_probability

__all__ = ["BitFlipChannel"]


class BitFlipChannel(QuantumChannel):
    """``E(rho) = (1 - p) rho + p X rho X`` with ``0 <= p <= 1``."""

    name = "bit_flip"

    def __init__(self, strength: float = 0.0) -> None:
        p = require_unit_probability(strength, "bit-flip")
        self._strength = p
        super().__init__(PauliProbabilities(p_i=1.0 - p, p_x=p, p_y=0.0, p_z=0.0))

    @property
    def strength(self) -> float:
        """The bit-flip probability ``p``."""
        return self._strength

    def describe(self) -> dict:
        description = super().describe()
        description["strength"] = self._strength
        description["strength_meaning"] = "probability that X is applied"
        description["valid_range"] = [0.0, 1.0]
        return description
