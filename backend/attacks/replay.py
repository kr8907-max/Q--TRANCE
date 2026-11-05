"""Replay: present a previously issued transcript as a fresh verification event.

What the attacker does
----------------------
Re-presents a transcript that was already issued and already verified. The
material is **not modified**: the transcript, its binding, its state sequence
and its quantum evidence are all left exactly as they were. The attacker's only
action is to submit them again.

That is why this scenario looks like a pass-through. It is the honest model of
the attack: replay is a *temporal* attack, and its causal effect exists in the
sequence of events, not in any single event.

    event 1: transcript T, nonce N  -> verified
    event 2: transcript T, nonce N  -> verified   <-- the same nonce again

Consequence for the evidence
----------------------------
Every ingredient of the replayed transcript may still be perfectly valid --
which is the property the milestone brief asks to preserve. A single replayed
event is therefore **indistinguishable from a fresh one** on the quantum
evidence alone. What a later milestone can use is the *observable stream*: the
same nonce (and the same ``created_at``) appearing in two events. M3 produces
that stream; consuming it is not M3's job.

This module therefore does not, and must not, implement a consumed-nonce store.
A replay-state policy or database belongs to a later milestone.

What the attacker knows
-----------------------
A transcript that was legitimately issued, including its nonce and session
identifier. The attacker does **not** need the message binding or the expected
state sequence, because the artifact it replays already satisfies them.

What the attacker cannot do
---------------------------
It cannot make the replayed transcript verify against a *different* message: the
binding check rejects that. Cross-message replay is therefore not modelled here
as a success; if a scenario needs it, the observable will show the ordinary
binding failure, which is not a replay-specific effect.

Limitations
-----------
No freshness window, no clock skew, no nonce store and no session ledger is
modelled. The scenario produces the artifacts a replay detector would need; it
does not decide anything.
"""

from __future__ import annotations

from backend.attacks.base import (
    AttackConfig,
    AttackContext,
    AttackOutcome,
    AttackScenario,
    AttackValidationError,
)

__all__ = ["VALID_REPLAY_MODES", "ReplayAttack"]




VALID_REPLAY_MODES = ("re_present", "cross_session")


class ReplayAttack(AttackScenario):
    """Re-present a previously issued transcript."""

    name = "replay"
    uses_fraction = False

    def __init__(self, config: AttackConfig) -> None:
        super().__init__(config)
        mode = self.parameters.get("mode", "re_present")
        if mode not in VALID_REPLAY_MODES:
            raise AttackValidationError(
                f"replay parameter 'mode' must be one of "
                f"{list(VALID_REPLAY_MODES)}, got {mode!r}"
            )
        unknown = sorted(set(self.parameters) - {"mode"})
        if unknown:
            raise AttackValidationError(f"replay does not accept parameters {unknown}")
        self._mode = mode

    @property
    def mode(self) -> str:
        return self._mode

    def apply(self, context: AttackContext) -> AttackOutcome:
        original = context.transcript


        return AttackOutcome(
            received_states=context.received_states,
            transcript=original,
            verifier_context=context.verifier_context,
            authorization=context.authorization,
            ground_truth={
                "attack_type": self.name,
                "mode": self._mode,
                "replayed_transcript_hash": original.transcript_hash,
                "replayed_nonce": original.nonce,
                "replayed_session_id": original.session_id,
                "replayed_created_at": original.created_at,
                "material_modified": False,
                "note": (
                    "the re-presented transcript is unchanged, so its content may "
                    "remain entirely valid; the observable signal is the repetition "
                    "of the nonce across events, not any defect in this event"
                ),
                "attacker_knowledge": [
                    "a previously issued transcript, including its nonce",
                ],
                "attacker_ignorance": [
                    "the message binding",
                    "the expected state sequence",
                ],
            },
        )
