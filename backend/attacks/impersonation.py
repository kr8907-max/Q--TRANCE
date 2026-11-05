"""Impersonation: a transcript that claims an identity it is not entitled to.

What the attacker does
----------------------
Replaces the signer identity declared in the transcript with one that the
authorization context does not authorise, then recomputes the transcript hash
so the artifact is internally consistent::

    transcript.signer_id  :=  presented_signer

The **quantum channel is not touched**. No state is measured, disturbed or
replaced, and the received states are passed through unchanged. That separation
is the point of this scenario: impersonation is a protocol-level attack surface,
not a channel disturbance, and the two must be studied independently.

What the attacker knows
-----------------------
The transcript, the public canonicalization, and the identity it wishes to
present.

What the attacker cannot do
---------------------------
* It cannot make the *quantum* evidence inconsistent, because it does not touch
  the quantum evidence at all.
* It does not learn anything about the message binding or the expected state
  sequence.

**A quantum measurement alone cannot detect this attack.** The states arriving
at the verifier are exactly the states an honest signer would send. Any
detection of impersonation must come from protocol-level authorization
bookkeeping, not from the quantum evidence. This is stated here because it is
the single most likely place for a later milestone to make an unsupported
claim.

Relationship to unauthorized verification
-----------------------------------------
Impersonation is "someone pretends to be Alice". It is deliberately distinct
from :mod:`backend.attacks.unauthorized_verification`, which is "Bob is not
entitled to check this session". The two mutate different fields and are
detected -- if at all -- by different bookkeeping.

Limitations
-----------
The authorization context is supplied by the experiment, not derived from a
real identity system. There is no authentication, no credential and no
certificate anywhere in this project; ``signer_id`` is a name, and the scenario
models the *consequence* of presenting the wrong name, not the means of
obtaining it.
"""

from __future__ import annotations

from typing import Any, Dict

from backend.attacks.base import (
    AttackConfig,
    AttackContext,
    AttackOutcome,
    AttackScenario,
    AttackValidationError,
    reseal_transcript,
)
from backend.protocol.models import validate_identifier

__all__ = ["DEFAULT_IMPERSONATED_SIGNER", "ImpersonationAttack"]


DEFAULT_IMPERSONATED_SIGNER = "unauthorized-signer"


class ImpersonationAttack(AttackScenario):
    """Present an unauthorised signer identity in an otherwise valid transcript."""

    name = "impersonation"
    uses_fraction = False

    def __init__(self, config: AttackConfig) -> None:
        super().__init__(config)
        unknown = sorted(set(self.parameters) - {"presented_signer"})
        if unknown:
            raise AttackValidationError(
                f"impersonation does not accept parameters {unknown}"
            )
        self._presented_signer = validate_identifier(
            self.parameters.get("presented_signer", DEFAULT_IMPERSONATED_SIGNER),
            "presented_signer",
        )

    @property
    def presented_signer(self) -> str:
        return self._presented_signer

    def apply(self, context: AttackContext) -> AttackOutcome:
        original = context.transcript
        forged = reseal_transcript(original, signer_id=self._presented_signer)

        return AttackOutcome(
            received_states=context.received_states,
            transcript=forged,
            verifier_context=context.verifier_context,
            authorization=context.authorization,
            ground_truth={
                "attack_type": self.name,
                "presented_signer": self._presented_signer,
                "original_signer": original.signer_id,
                "authorized_signers": sorted(context.authorization.authorized_signers),
                "signer_was_authorized": context.authorization.signer_authorized(
                    self._presented_signer
                ),
                "channel_untouched": True,
                "attacker_knowledge": [
                    "the transcript",
                    "the public canonicalization",
                    "the identity it wishes to present",
                ],
                "attacker_ignorance": [
                    "the message binding",
                    "the expected state sequence",
                ],
            },
        )
