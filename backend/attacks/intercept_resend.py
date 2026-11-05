"""Intercept-resend: an attacker measures the qubit and re-sends what she got.

What the attacker does
----------------------
For a configurable share of the signature states, the attacker on the channel::

    Alice --(qubit)--> Eve measures in basis B --> Eve re-prepares the
                                                      eigenstate she obtained
                                                      --> Bob

Concretely, for a received state ``rho`` and Eve's chosen basis ``B`` with
eigenstates ``|b>``:

1. draw the outcome ``b`` from the Born rule, ``Pr[b] = <b|rho|b>``;
2. re-prepare ``|b><b|`` and forward it.

This is a genuine measure-and-reprepare attack, not a random replacement. Its
consequence is the physical one: if Eve guesses the basis the protocol used for
that state, she forwards the correct state and causes no disturbance; if she
guesses wrong, the re-prepared eigenstate is unbiased with respect to the
protocol's basis and the verifier's measurement becomes a coin flip.

Eve's basis choice
------------------
``eve_basis`` is ``"Z"``, ``"X"``, ``"Y"`` or ``"random"``. ``"random"`` draws
a basis uniformly per intercepted state from the seeded generator. Because the
reference protocol's states are drawn from all six Pauli eigenstates, a fixed
wrong basis is disrupted for most states and a random basis is correct about a
third of the time -- so the observable disturbance is a joint property of Eve's
strategy and the protocol's own basis distribution.

What the attacker knows
-----------------------
The qubit as it arrives, and the number of states. She does **not** know the
basis the protocol derived for each state (that is the whole point of the
attack), nor the expected state sequence, nor the message binding.

What the attacker cannot do
---------------------------
Re-send the original state. The measurement is irreversible: once Eve has
measured in the wrong basis, no operation on her single copy can restore the
original. She also cannot tell afterwards which of her guesses were right.

Limitations
-----------
This models an *individual* (one-qubit-at-a-time) attack with a single copy of
each qubit and no quantum memory. It does not model coherent attacks over
several qubits, entanglement with an ancilla, or a basis choice that adapts to
earlier outcomes. The verifier-side disturbance is computed from the forwarded
states, so an attacker who guessed correctly is indistinguishable from an
honest channel for that state -- which is a physical fact, not an artefact of
the simulation.

Reproducibility
---------------
Eve's basis choices and measurement outcomes both come from the seeded
generator in :class:`~backend.attacks.base.AttackContext`, so the same seed
reproduces the same interception exactly.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import numpy as np

from backend.attacks.base import (
    AttackConfig,
    AttackContext,
    AttackOutcome,
    AttackScenario,
    AttackValidationError,
    as_state_matrices,
    select_targets,
)
from backend.quantum.states import pauli_eigenstates

__all__ = ["VALID_EVE_BASES", "InterceptResendAttack"]


VALID_EVE_BASES: Tuple[str, ...] = ("Z", "X", "Y", "random")


def _basis_eigenvectors(basis: str) -> Tuple[np.ndarray, np.ndarray]:
    """Return the ``+1`` and ``-1`` eigenvector of ``basis``.

    Taken from the verified M1 state definitions rather than re-derived here.
    """
    if basis not in ("X", "Y", "Z"):
        raise AttackValidationError(f"unknown basis {basis!r}")
    vectors = {}
    for state in pauli_eigenstates().values():
        if state.basis == basis:
            vectors[int(state.eigenvalue)] = np.asarray(state.vector, dtype=complex)
    return vectors[+1], vectors[-1]


class InterceptResendAttack(AttackScenario):
    """Measure-and-reprepare on a fraction of the received states."""

    name = "intercept_resend"
    uses_fraction = True

    def __init__(self, config: AttackConfig) -> None:
        super().__init__(config)
        eve_basis = self.parameters.get("eve_basis", "random")
        if eve_basis not in VALID_EVE_BASES:
            raise AttackValidationError(
                f"intercept_resend parameter 'eve_basis' must be one of "
                f"{list(VALID_EVE_BASES)}, got {eve_basis!r}"
            )
        unknown = sorted(set(self.parameters) - {"eve_basis"})
        if unknown:
            raise AttackValidationError(
                f"intercept_resend does not accept parameters {unknown}"
            )
        self._eve_basis = eve_basis

    @property
    def eve_basis(self) -> str:
        return self._eve_basis

    def _intercept(
        self,
        rho: np.ndarray,
        basis: str,
        rng: np.random.Generator,
    ) -> Tuple[np.ndarray, int]:
        """Measure ``rho`` in ``basis`` and return the re-prepared state."""
        plus, minus = _basis_eigenvectors(basis)
        probabilities = []
        for vector in (plus, minus):
            projector = np.outer(vector, np.conjugate(vector))
            value = float(np.real(np.trace(projector @ rho)))
            probabilities.append(min(1.0, max(0.0, value)))
        total = probabilities[0] + probabilities[1]
        if total <= 0.0:  # pragma: no cover - a valid density matrix cannot do this
            raise AttackValidationError("intercepted state has no probability mass")
        probabilities = [value / total for value in probabilities]
        outcome = int(rng.choice((0, 1), p=probabilities))
        chosen = plus if outcome == 0 else minus
        return np.outer(chosen, np.conjugate(chosen)), outcome

    def apply(self, context: AttackContext) -> AttackOutcome:
        states = list(as_state_matrices(context.received_states))
        targets = select_targets(len(states), self.fraction, context.rng)

        interceptions: List[Dict[str, Any]] = []
        for index in targets:
            basis = (
                str(context.rng.choice(("Z", "X", "Y")))
                if self._eve_basis == "random"
                else self._eve_basis
            )
            reprepared, outcome = self._intercept(states[index], basis, context.rng)
            states[index] = reprepared
            interceptions.append(
                {"index": index, "eve_basis": basis, "eve_outcome": outcome}
            )

        return AttackOutcome(
            received_states=tuple(states),
            transcript=context.transcript,
            verifier_context=context.verifier_context,
            authorization=context.authorization,
            ground_truth={
                "attack_type": self.name,
                "eve_basis": self._eve_basis,
                "fraction": self.fraction,
                "intercepted_indices": [item["index"] for item in interceptions],
                "interceptions": interceptions,
                "intercepted_state_count": len(interceptions),
                "attacker_knowledge": [
                    "the qubit as it arrives",
                    "the number of states",
                ],
                "attacker_ignorance": [
                    "the basis the protocol derived for each state",
                    "the verifier's expected state sequence",
                    "the message binding",
                ],
            },
        )
