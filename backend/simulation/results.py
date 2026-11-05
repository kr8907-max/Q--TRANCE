"""Experiment results, with observable evidence separated from ground truth.

The separation this module enforces
-----------------------------------
::

    ExperimentResult
        observable    ObservableExperimentData   <- a detector may consume this
        ground_truth  GroundTruthMetadata        <- a detector must never see this

``ObservableExperimentData`` contains only what a verifier can actually observe:
the received states it measured, the bits it obtained, the protocol's own
verification result, the authorization context it holds, and raw counts. It
carries no attack type, no attack parameter, no noise strength and no
``is_malicious`` flag.

``GroundTruthMetadata`` contains exactly those things, for benchmarking.

The separation is not a naming convention: ``ObservableExperimentData`` has no
field that references ``GroundTruthMetadata``, so a consumer can be handed one
without the other, and the test suite constructs and consumes the observable
alone.

Statistics are observations, not verdicts
-----------------------------------------
The numeric fields here are raw measurements: counts, an empirical mismatch
proportion, empirical basis frequencies and a mean state disturbance. None of
them is called "safe", "unsafe", "attack", "legitimate", "accepted" or
"rejected", and nothing compares them against a threshold. Interpreting them is
a later milestone's job.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Tuple

from backend.protocol.models import VerificationResult

__all__ = [
    "StateObservation",
    "AuthorizationObservations",
    "ObservableExperimentData",
    "GroundTruthMetadata",
    "ExperimentResult",
]


@dataclass(frozen=True)
class StateObservation:
    """What the verifier observed for one signature state.

    ``probability_expected`` is the projective probability of the expected
    eigenvalue, computed analytically from the received qubit. It is the raw
    physical quantity and is available in both measurement modes.

    ``matched`` records whether the verifier's measurement agreed with the
    expected eigenvalue, and its precise meaning depends on the mode recorded in
    ``ObservableExperimentData.measurement_mode``:

    ``"projective-analytic"``
        the measurement is deterministic, so ``matched`` means the received
        qubit *is* the expected eigenstate (probability within tolerance of 1).
    ``"sampled"``
        ``matched`` means the finite-shot outcome happened to be the expected
        bit; the underlying probability is still reported alongside.

    The two are never conflated, because the mode travels with the observation.
    """

    index: int
    basis: str
    expected_bit: int
    probability_expected: float
    matched: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "basis": self.basis,
            "expected_bit": self.expected_bit,
            "probability_expected": self.probability_expected,
            "matched": self.matched,
        }


@dataclass(frozen=True)
class AuthorizationObservations:
    """The authorization context the verifier held, and whether it was satisfied.

    This is protocol authorization bookkeeping -- a deterministic membership
    test on declared identities -- not threat detection. There is no statistic
    and no threshold here.
    """

    presented_signer: str
    presented_verifier: str
    authorized_signers: Tuple[str, ...]
    authorized_verifiers: Tuple[str, ...]
    signer_authorized: bool
    verifier_authorized: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "presented_signer": self.presented_signer,
            "presented_verifier": self.presented_verifier,
            "authorized_signers": list(self.authorized_signers),
            "authorized_verifiers": list(self.authorized_verifiers),
            "signer_authorized": self.signer_authorized,
            "verifier_authorized": self.verifier_authorized,
        }


@dataclass(frozen=True)
class ObservableExperimentData:
    """Everything a verifier can observe about one experiment.

    A future detection engine may consume exactly this and nothing else.
    """

    scenario_id: str
    protocol_version: str
    state_count: int
    states: Tuple[StateObservation, ...]
    basis_counts: Mapping[str, int]
    mismatch_count: int
    mismatch_proportion: float
    mean_channel_disturbance: float
    verification: VerificationResult
    authorization: AuthorizationObservations
    simulator_seed: int
    measurement_mode: str
    runtime_seconds: float | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "protocol_version": self.protocol_version,
            "state_count": self.state_count,
            "states": [state.to_dict() for state in self.states],
            "basis_counts": dict(self.basis_counts),
            "mismatch_count": self.mismatch_count,
            "mismatch_proportion": self.mismatch_proportion,
            "mean_channel_disturbance": self.mean_channel_disturbance,
            "verification": self.verification.to_dict(),
            "authorization": self.authorization.to_dict(),
            "simulator_seed": self.simulator_seed,
            "measurement_mode": self.measurement_mode,
            "runtime_seconds": self.runtime_seconds,
        }


@dataclass(frozen=True)
class GroundTruthMetadata:
    """What actually happened, for benchmarking only.

    A detection engine must never read this. It is stored beside the observable
    data rather than inside it.
    """

    scenario_id: str
    is_malicious: bool
    noise: Mapping[str, Any]
    attack: Mapping[str, Any]
    notes: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "is_malicious": self.is_malicious,
            "noise": dict(self.noise),
            "attack": dict(self.attack),
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class ExperimentResult:
    """One experiment: observable evidence plus separately stored ground truth."""

    observable: ObservableExperimentData
    ground_truth: GroundTruthMetadata

    def detector_view(self) -> ObservableExperimentData:
        """Return the observable half only.

        Exists so a caller -- and the test suite -- can be explicit about handing
        a later milestone nothing but the observable evidence.
        """
        return self.observable

    def to_dict(self) -> Dict[str, Any]:
        return {
            "observable": self.observable.to_dict(),
            "ground_truth": self.ground_truth.to_dict(),
        }
