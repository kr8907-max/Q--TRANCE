"""Forgery: produce a transcript that claims a message the signer never signed.

Two modes, because the reference protocol has a documented limitation that must
be demonstrated rather than hidden.

``mode="rebind_only"`` (default)
    The attacker rewrites the message, the message hash and the message
    binding in an existing transcript, but reuses the state sequence that was
    derived for the *original* binding. Everything else -- the session
    identifier, the nonce, the protocol version -- is left alone, and the
    transcript hash is recomputed so the artifact is internally consistent.

    The protocol's transcript-hash check cannot catch this. What catches it is
    the verifier's independent reconstruction: it derives the expected sequence
    from the binding *it* computes and finds it disagrees with the declared
    one. This is the causal effect the scenario exists to produce.

``mode="full_forge"``
    The attacker constructs a complete transcript for a message of her choosing:
    her own session identifier and nonce, a binding derived from them, the state
    sequence derived from that binding, and arbitrary (structurally valid) Bell
    branch bits. Because every ingredient is public and deterministic, the
    result **verifies successfully**.

    This is not a bug in the simulation. It is the honest demonstration of the
    property documented in ``docs/protocol/reference-qds.md``: the reference
    protocol has no secret key, so it provides binding and structural integrity
    and **no unforgeability**. M3 produces the evidence; deciding what that
    evidence means is a later milestone's job.

What the attacker knows
-----------------------
The public canonicalization, the public state-sequence derivation, the message
she wishes to forge, and (for ``rebind_only``) a transcript she has obtained.
The attacker does **not** possess any key, because no key exists in this
construction.

What the attacker cannot do
---------------------------
Nothing in this module computes an optimal quantum forgery strategy. There is
no quantum forgery at all: the scenarios are protocol-level manipulations of a
classical artifact. A forger who could not derive the state sequence (for
example, against a future construction that keeps the mapping secret) is out of
scope here.

Limitations
-----------
``full_forge`` succeeds only because the derivation is public. If the protocol
is later extended with a secret, this scenario must be re-examined.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

from backend.attacks.base import (
    AttackConfig,
    AttackContext,
    AttackOutcome,
    AttackScenario,
    AttackValidationError,
    reseal_transcript,
)
from backend.protocol.binding import compute_message_binding, compute_message_hash
from backend.protocol.encoding import derive_state_sequence
from backend.protocol.models import TeleportationBranch, validate_message
from backend.protocol.transcript import build_transcript

__all__ = ["VALID_FORGERY_MODES", "DEFAULT_FORGED_MESSAGE", "ForgeryAttack"]


VALID_FORGERY_MODES: Tuple[str, ...] = ("rebind_only", "full_forge")


DEFAULT_FORGED_MESSAGE = "forged transfer authorisation"


class ForgeryAttack(AttackScenario):
    """Attempt to make a transcript assert a message that was never signed."""

    name = "forgery"
    uses_fraction = False

    def __init__(self, config: AttackConfig) -> None:
        super().__init__(config)
        mode = self.parameters.get("mode", "rebind_only")
        if mode not in VALID_FORGERY_MODES:
            raise AttackValidationError(
                f"forgery parameter 'mode' must be one of "
                f"{list(VALID_FORGERY_MODES)}, got {mode!r}"
            )
        unknown = sorted(set(self.parameters) - {"mode", "forged_message"})
        if unknown:
            raise AttackValidationError(
                f"forgery does not accept parameters {unknown}"
            )
        self._mode = mode
        self._forged_message = validate_message(
            self.parameters.get("forged_message", DEFAULT_FORGED_MESSAGE),
            "forged_message",
        )

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def forged_message(self) -> str:
        """The message the attacker wants a signature for."""
        return self._forged_message

    def apply(self, context: AttackContext) -> AttackOutcome:
        if self._mode == "rebind_only":
            return self._rebind(context)
        return self._full_forge(context)

    def _rebind(self, context: AttackContext) -> AttackOutcome:
        """Rewrite the message/binding, keep the original state sequence."""
        original = context.transcript
        forged_message = self.forged_message
        forged_binding = compute_message_binding(
            protocol_version=original.protocol_version,
            session_id=original.session_id,
            nonce=original.nonce,
            message=forged_message,
        )
        forged = reseal_transcript(
            original,
            message_hash=compute_message_hash(forged_message),
            message_binding=forged_binding,
        )
        return AttackOutcome(
            received_states=context.received_states,
            transcript=forged,
            verifier_context=context.verifier_context,
            authorization=context.authorization,
            ground_truth={
                "attack_type": self.name,
                "mode": self._mode,
                "original_message_hash": original.message_hash,
                "forged_message": forged_message,
                "forged_message_hash": forged.message_hash,
                "forged_binding": forged_binding,
                "state_sequence_reused": True,
                "attacker_knowledge": [
                    "the public canonicalization",
                    "an existing transcript",
                    "the message it wishes to forge",
                ],
                "attacker_ignorance": ["any key (none exists in this construction)"],
            },
        )

    def _full_forge(self, context: AttackContext) -> AttackOutcome:
        """Build a complete, self-consistent transcript for a chosen message."""
        forged_message = self.forged_message
        original = context.transcript


        binding = compute_message_binding(
            protocol_version=original.protocol_version,
            session_id=original.session_id,
            nonce=original.nonce,
            message=forged_message,
        )
        states = derive_state_sequence(binding, original.state_count)
        branches = tuple(
            TeleportationBranch(
                index=state.index,
                m0=int(context.rng.integers(0, 2)),
                m1=int(context.rng.integers(0, 2)),
            )
            for state in states
        )
        forged = build_transcript(
            transcript_version=original.transcript_version,
            protocol_version=original.protocol_version,
            session_id=original.session_id,
            nonce=original.nonce,
            created_at=original.created_at,
            message_hash=compute_message_hash(forged_message),
            message_binding=binding,
            signer_id=original.signer_id,
            verifier_id=original.verifier_id,
            state_count=original.state_count,
            state_sequence_metadata=original.state_sequence_metadata,
            states=states,
            teleportation_branches=branches,
            verification_metadata=dict(original.verification_metadata),
        )
        return AttackOutcome(
            received_states=context.received_states,
            transcript=forged,
            verifier_context=context.verifier_context,
            authorization=context.authorization,
            ground_truth={
                "attack_type": self.name,
                "mode": self._mode,
                "original_message_hash": original.message_hash,
                "forged_message": forged_message,
                "forged_message_hash": forged.message_hash,
                "forged_binding": binding,
                "state_sequence_reused": False,
                "state_sequence_rederived": True,
                "succeeded_without_any_key": True,
                "attacker_knowledge": [
                    "the public canonicalization",
                    "the public state-sequence derivation",
                    "the message it wishes to forge",
                ],
                "attacker_ignorance": ["any key (none exists in this construction)"],
            },
        )
