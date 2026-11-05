"""Authorization and impersonation evidence: two separate identity checks.

Why the two checks are separate
-------------------------------
The project audit called this out explicitly. These are different attack
surfaces and must not be merged into one "identity mismatch":

=========================================  ====================================
**signer authorization**                   "someone claims to be Alice"
**verifier authorization**                 "Bob is not entitled to check this
                                           session"
=========================================  ====================================

They concern different fields (``transcript.signer_id`` versus
``transcript.verifier_id`` and the verifier's own identity), they are decided by
different bookkeeping, and conflating them would hide one of the surfaces. The
engine emits one finding per violated check, each naming the role.

What the evidence can and cannot show
-------------------------------------
The evidence is a **membership test on declared identifiers**: the identity the
artifact presents, against the set the verification system authorises. It is
deterministic and needs no threshold.

It is *not* proof of identity. Nothing in this project authenticates anybody:
there is no credential, no certificate and no key, so ``signer_id`` is a name.
A quantum measurement certainly cannot establish identity. This module says
which name was presented and whether that name was authorised, and stops there.

The engine recomputes the membership test rather than trusting a pre-computed
boolean, and reports when the two disagree -- a disagreement between the
verifier's recorded flag and the recomputed result is itself evidence that the
bookkeeping and the artifact do not line up.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple

from backend.detection.models import ObservableDetectionInput

__all__ = ["AuthorizationCheck", "AuthorizationReport", "analyse_authorization"]


SIGNER_ROLE = "signer"
VERIFIER_ROLE = "verifier"


@dataclass(frozen=True)
class AuthorizationCheck:
    """One identity check: what was presented, what was expected, and why."""

    role: str
    presented_identity: str | None
    authorized_identities: Tuple[str, ...]
    authorized: bool | None
    reported_authorized: bool | None
    reported_agrees: bool | None
    reason: str

    @property
    def violated(self) -> bool:
        """Return whether the check definitively failed."""
        return self.authorized is False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "presented_identity": self.presented_identity,
            "authorized_identities": list(self.authorized_identities),
            "authorized": self.authorized,
            "reported_authorized": self.reported_authorized,
            "reported_agrees": self.reported_agrees,
            "violated": self.violated,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class AuthorizationReport:
    """The two authorization checks for one session."""

    signer: AuthorizationCheck
    verifier: AuthorizationCheck
    notes: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signer": self.signer.to_dict(),
            "verifier": self.verifier.to_dict(),
            "notes": list(self.notes),
        }


def _check(
    *,
    role: str,
    presented: Any,
    authorized_identities: Tuple[str, ...],
    reported: Any,
) -> AuthorizationCheck:
    """Run one membership test and explain the outcome."""
    identities = tuple(str(item) for item in authorized_identities)
    presented_identity = presented if isinstance(presented, str) and presented else None

    if presented_identity is None:
        return AuthorizationCheck(
            role=role,
            presented_identity=None,
            authorized_identities=identities,
            authorized=None,
            reported_authorized=reported if isinstance(reported, bool) else None,
            reported_agrees=None,
            reason=(
                f"no {role} identity was observable, so {role} authorization could "
                f"not be established"
            ),
        )

    if not identities:
        return AuthorizationCheck(
            role=role,
            presented_identity=presented_identity,
            authorized_identities=(),
            authorized=None,
            reported_authorized=reported if isinstance(reported, bool) else None,
            reported_agrees=None,
            reason=(
                f"the presented {role} {presented_identity!r} could not be checked: "
                f"no authorised {role} identities were supplied"
            ),
        )

    authorized = presented_identity in identities
    reported_bool = reported if isinstance(reported, bool) else None
    reported_agrees = None if reported_bool is None else reported_bool == authorized

    if authorized:
        reason = (
            f"presented {role} {presented_identity!r} is among the authorised "
            f"{role} identities {list(identities)}"
        )
    else:
        reason = (
            f"presented {role} {presented_identity!r} is not among the authorised "
            f"{role} identities {list(identities)}"
        )

    return AuthorizationCheck(
        role=role,
        presented_identity=presented_identity,
        authorized_identities=identities,
        authorized=authorized,
        reported_authorized=reported_bool,
        reported_agrees=reported_agrees,
        reason=reason,
    )


def analyse_authorization(
    detection_input: ObservableDetectionInput,
) -> AuthorizationReport:
    """Return the signer and verifier authorization checks for a session.

    The presented identities come from the transcript; the authorised sets and
    the recorded booleans come from the authorization context the verification
    system holds. Both are observable to the verifier.
    """
    notes: list[str] = [
        "authorization is a membership test on declared identities; it is not "
        "proof of identity, and no quantum measurement can establish identity",
    ]

    signer = _check(
        role=SIGNER_ROLE,
        presented=detection_input.signer_id,
        authorized_identities=detection_input.authorized_signers,
        reported=detection_input.reported_signer_authorized,
    )
    verifier = _check(
        role=VERIFIER_ROLE,
        presented=detection_input.verifier_id,
        authorized_identities=detection_input.authorized_verifiers,
        reported=detection_input.reported_verifier_authorized,
    )

    if signer.reported_agrees is False:
        notes.append(
            "the recorded signer authorization flag disagrees with the "
            "recomputed membership test"
        )
    if verifier.reported_agrees is False:
        notes.append(
            "the recorded verifier authorization flag disagrees with the "
            "recomputed membership test"
        )

    return AuthorizationReport(signer=signer, verifier=verifier, notes=tuple(notes))
