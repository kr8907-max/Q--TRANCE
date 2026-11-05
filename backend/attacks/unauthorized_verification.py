"""Unauthorized verification: a party not entitled to check a session tries to.

What the attacker does
----------------------
An identity that the authorization context does not list as an authorised
verifier for the session presents itself as the verifying party::

    verifier_context.verifier_id  :=  presented_verifier
    transcript.verifier_id        :=  presented_verifier   (re-sealed)

The transcript's ``verifier_id`` is rewritten too, so that M2's *addressing*
check (``transcript.verifier_id == verifier_context.verifier_id``) is satisfied
and the only thing standing between the unauthorized party and a result is the
authorization context. That isolation is deliberate: it makes the scenario test
the authorization surface rather than re-testing M2's addressing check.

The quantum channel is not touched.

Relationship to impersonation
-----------------------------
This is "Bob is not entitled to verify this session", which is **not** the same
as "someone pretends to be Alice". The project audit called this distinction
out explicitly:

============================  ==========================================
impersonation                 a signer identity that is not authorised
unauthorized verification     a *verifier* identity that is not authorised
============================  ==========================================

They mutate different fields, they are detected (if at all) by different
bookkeeping, and conflating them would hide a real attack surface.

What the attacker knows
-----------------------
The transcript, the public canonicalization, and the identity it wishes to
present.

What the attacker cannot do
---------------------------
It cannot alter the quantum evidence, and it gains no information about the
message binding or the expected state sequence. A correct authorization check
is the only thing that distinguishes this event from a legitimate one.

Limitations
-----------
The authorization context is experiment-supplied. Nothing here models how an
unauthorized party would obtain a transcript in the first place, and nothing
here authenticates anybody.
"""

from __future__ import annotations

from dataclasses import replace

from backend.attacks.base import (
    AttackConfig,
    AttackContext,
    AttackOutcome,
    AttackScenario,
    AttackValidationError,
    reseal_transcript,
)
from backend.protocol.models import validate_identifier

__all__ = ["DEFAULT_UNAUTHORIZED_VERIFIER", "UnauthorizedVerificationAttack"]


DEFAULT_UNAUTHORIZED_VERIFIER = "unauthorized-verifier"


class UnauthorizedVerificationAttack(AttackScenario):
    """Let an unauthorised verifier identity present a valid transcript."""

    name = "unauthorized_verification"
    uses_fraction = False

    def __init__(self, config: AttackConfig) -> None:
        super().__init__(config)
        unknown = sorted(set(self.parameters) - {"presented_verifier"})
        if unknown:
            raise AttackValidationError(
                f"unauthorized_verification does not accept parameters {unknown}"
            )
        self._presented_verifier = validate_identifier(
            self.parameters.get("presented_verifier", DEFAULT_UNAUTHORIZED_VERIFIER),
            "presented_verifier",
        )

    @property
    def presented_verifier(self) -> str:
        return self._presented_verifier

    def apply(self, context: AttackContext) -> AttackOutcome:
        original = context.transcript
        forged = reseal_transcript(original, verifier_id=self._presented_verifier)
        presented_context = replace(
            context.verifier_context, verifier_id=self._presented_verifier
        )

        return AttackOutcome(
            received_states=context.received_states,
            transcript=forged,
            verifier_context=presented_context,
            authorization=context.authorization,
            ground_truth={
                "attack_type": self.name,
                "presented_verifier": self._presented_verifier,
                "original_verifier": original.verifier_id,
                "authorized_verifiers": sorted(
                    context.authorization.authorized_verifiers
                ),
                "verifier_was_authorized": context.authorization.verifier_authorized(
                    self._presented_verifier
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
