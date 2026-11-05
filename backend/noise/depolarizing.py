"""Depolarizing channel.

Mathematical definition
-----------------------
Three equivalent forms, all of which this module implements and tests against::

    E(rho) = (1 - p) rho + p * (I / 2)                      [interpolation form]

    E(rho) = (1 - 3p/4) rho + (p/4)(X rho X + Y rho Y + Z rho Z)
                                                            [Kraus / Pauli form]

    p_I = 1 - 3p/4,  p_X = p_Y = p_Z = p/4                  [probability table]

The first is the most readable: the state is linearly interpolated towards the
maximally mixed state ``I/2`` with weight ``p``. The equivalence follows from
``X rho X + Y rho Y + Z rho Z = 2 Tr(rho) I - rho``, which for a unit-trace
state is ``2I - rho``.

Valid range
-----------
``0 <= p <= 1``, where ``p`` is the **depolarizing parameter**, i.e. the weight
of ``I/2`` in the interpolation above.

The probability table stays non-negative up to ``p = 4/3``, so the channel is
CPTP on the wider interval, and ``qiskit_aer.noise.depolarizing_error`` accepts
it. This implementation nevertheless rejects ``p > 1``, because on ``(1, 4/3]``
the coefficient of ``rho`` becomes negative and the map no longer describes
depolarisation towards ``I/2`` -- it describes a state-inverting map that
happens to share the same algebraic family. Rejecting it explicitly is
preferable to silently applying a channel whose name no longer matches its
behaviour. See ``docs/security/noise-and-channel.md``.

Reference points
----------------
``p = 0``  identity channel.
``p = 1``  ``E(rho) = I/2`` for every ``rho``: complete depolarisation.

``p`` is a **physical channel parameter**. It is not a measurement error rate, not
an attack intensity, and not a security threshold.
"""

from __future__ import annotations

from backend.noise.base import (
    NoiseValidationError,
    PauliProbabilities,
    QuantumChannel,
)

__all__ = ["DEPOLARIZING_MAX_STRENGTH", "DepolarizingChannel"]



DEPOLARIZING_MAX_STRENGTH = 1.0


class DepolarizingChannel(QuantumChannel):
    """``E(rho) = (1 - p) rho + p * I/2`` with ``0 <= p <= 1``."""

    name = "depolarizing"

    def __init__(self, strength: float = 0.0) -> None:
        if isinstance(strength, bool) or not isinstance(strength, (int, float)):
            raise NoiseValidationError(
                f"depolarizing strength must be a real number, got "
                f"{type(strength).__name__}"
            )
        p = float(strength)
        if not 0.0 <= p <= DEPOLARIZING_MAX_STRENGTH:
            raise NoiseValidationError(
                f"depolarizing strength must lie in "
                f"[0, {DEPOLARIZING_MAX_STRENGTH}], got {p!r}"
            )
        self._strength = p
        super().__init__(
            PauliProbabilities(
                p_i=1.0 - 3.0 * p / 4.0,
                p_x=p / 4.0,
                p_y=p / 4.0,
                p_z=p / 4.0,
            )
        )

    @property
    def strength(self) -> float:
        """The depolarizing parameter ``p``."""
        return self._strength

    def describe(self) -> dict:
        description = super().describe()
        description["strength"] = self._strength
        description["strength_meaning"] = "weight of I/2 in (1-p) rho + p I/2"
        description["valid_range"] = [0.0, DEPOLARIZING_MAX_STRENGTH]
        return description
