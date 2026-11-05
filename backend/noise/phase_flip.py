"""Phase-flip channel.

Mathematical definition
-----------------------
A Pauli channel with the probability table::

    p_I = 1 - p        p_X = 0        p_Y = 0        p_Z = p

equivalently::

    E(rho) = (1 - p) rho + p * Z rho Z

``p`` is the probability that the Pauli ``Z`` is applied. As with the bit-flip
channel, ``p`` **is** an error probability -- unlike the depolarizing channel's
parameter.

Valid range
-----------
``0 <= p <= 1``.

Reference points
----------------
``p = 0``    identity channel.
``p = 1``    ``E(rho) = Z rho Z``: a deterministic phase flip.
``p = 1/2``  ``E(|+><+|) = I/2``; the ``Z`` eigenstates ``|0>`` and ``|1>`` are
unaffected for every ``p``, because ``Z rho Z = rho`` for both.

That last point matters for experiment design: a phase-flip channel is
*invisible* to a computational-basis (Z-basis) measurement. The experiment
runner measures each state in the basis the protocol derived for it, which is
what makes phase noise observable at all.

``p`` is a physical channel parameter, not a measurement error rate, not an
attack intensity and not a security threshold.
"""

from __future__ import annotations

from backend.noise.base import PauliProbabilities, QuantumChannel, require_unit_probability

__all__ = ["PhaseFlipChannel"]


class PhaseFlipChannel(QuantumChannel):
    """``E(rho) = (1 - p) rho + p Z rho Z`` with ``0 <= p <= 1``."""

    name = "phase_flip"

    def __init__(self, strength: float = 0.0) -> None:
        p = require_unit_probability(strength, "phase-flip")
        self._strength = p
        super().__init__(PauliProbabilities(p_i=1.0 - p, p_x=0.0, p_y=0.0, p_z=p))

    @property
    def strength(self) -> float:
        """The phase-flip probability ``p``."""
        return self._strength

    def describe(self) -> dict:
        description = super().describe()
        description["strength"] = self._strength
        description["strength_meaning"] = "probability that Z is applied"
        description["valid_range"] = [0.0, 1.0]
        return description
