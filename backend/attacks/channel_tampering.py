"""Channel tampering: Pauli error injection on a fraction of the states.

What the attacker does
----------------------
A controlled corruption of the transmitted qubits: on a configurable share of
the signature states, one of the Pauli operators ``X``, ``Z``, ``XZ`` -- or a
Pauli drawn uniformly at random per targeted state -- is applied to the state
that reaches the verifier.

    rho_received  ->  P rho_received P

This is a *coherent* single-Pauli corruption, not a probabilistic channel. It
is applied to exactly the states the attack selected, which is why it produces
a clean continuum of disturbance as ``fraction`` rises rather than a smooth
degradation.

What the attacker knows
-----------------------
The states as they arrive on the channel, and how many there are. The attacker
does **not** know the verifier's expected state sequence, which basis the
protocol derived for each state, or whether the corrupted states will be
measured in a basis that reveals the corruption. A Pauli ``Z`` applied to a
state that is subsequently measured in the Z basis is invisible; the same Pauli
applied to an X-basis state is maximally disruptive. The observable disturbance
is therefore a joint property of the attack and the protocol's own basis
choices.

What the attacker cannot do
---------------------------
Restore a corrupted state, or learn the expected sequence from the disturbance
it caused.

Limitations
-----------
This models an attacker who can apply a Pauli operator but does not measure.
It does not model partial/weak measurements, coherent attacks across several
states, or entanglement with an ancilla. See
``docs/security/attack-models.md``.

Reproducibility
---------------
Which states are targeted, and which Pauli is drawn for ``pauli="random"``,
come from the seeded generator in :class:`~backend.attacks.base.AttackContext`.
The same seed reproduces the same corruption exactly.
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
from backend.quantum.states import PAULI_MATRICES

__all__ = ["VALID_TAMPER_PAULIS", "ChannelTamperingAttack"]


VALID_TAMPER_PAULIS: Tuple[str, ...] = ("X", "Z", "XZ", "random")


class ChannelTamperingAttack(AttackScenario):
    """Inject a Pauli error into a fraction of the received states."""

    name = "channel_tampering"
    uses_fraction = True

    def __init__(self, config: AttackConfig) -> None:
        super().__init__(config)
        pauli = self.parameters.get("pauli", "X")
        if pauli not in VALID_TAMPER_PAULIS:
            raise AttackValidationError(
                f"channel_tampering parameter 'pauli' must be one of "
                f"{list(VALID_TAMPER_PAULIS)}, got {pauli!r}"
            )
        unknown = sorted(set(self.parameters) - {"pauli"})
        if unknown:
            raise AttackValidationError(
                f"channel_tampering does not accept parameters {unknown}"
            )
        self._pauli = pauli

    @property
    def pauli(self) -> str:
        return self._pauli

    def _operator(self, label: str) -> np.ndarray:
        if label == "XZ":
            return PAULI_MATRICES["X"] @ PAULI_MATRICES["Z"]
        return PAULI_MATRICES[label]

    def apply(self, context: AttackContext) -> AttackOutcome:
        states = list(as_state_matrices(context.received_states))
        targets = select_targets(len(states), self.fraction, context.rng)

        applied: List[Dict[str, Any]] = []
        for index in targets:
            label = (
                str(context.rng.choice(("X", "Z", "XZ")))
                if self._pauli == "random"
                else self._pauli
            )
            operator = self._operator(label)
            states[index] = operator @ states[index] @ operator.conj().T
            applied.append({"index": index, "pauli": label})

        return AttackOutcome(
            received_states=tuple(states),
            transcript=context.transcript,
            verifier_context=context.verifier_context,
            authorization=context.authorization,
            ground_truth={
                "attack_type": self.name,
                "pauli": self._pauli,
                "fraction": self.fraction,
                "targeted_indices": [item["index"] for item in applied],
                "applied_paulis": applied,
                "modified_state_count": len(applied),
                "attacker_knowledge": [
                    "the received states",
                    "the number of states",
                ],
                "attacker_ignorance": [
                    "the verifier's expected state sequence",
                    "the basis derived for each state",
                    "which corruptions the measurement will reveal",
                ],
            },
        )
