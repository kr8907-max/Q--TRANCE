"""Orchestration for scenario simulation.

Builds configuration objects and calls :func:`backend.simulation.run_scenario`.
The API constructs no quantum circuit, applies no noise equation and models no
attack: it assembles the M3 configuration from typed input and reports the
observable half of what came back.

Ground truth is opt-in and labelled
-----------------------------------
The hidden attack label is only returned when the caller asked for it, and the
payload it arrives in identifies itself as evaluation material. That keeps the
operational path free of labels, which is what makes the detection endpoint
meaningful.
"""

from __future__ import annotations

from typing import Any, Dict

from backend.api.errors import ApiError, ErrorCode
from backend.api.schemas.simulation import GROUND_TRUTH_LABEL, SimulationRequest
from backend.attacks import AttackConfig, AttackValidationError
from backend.evaluation import deterministic_session_identifiers
from backend.noise import NoiseConfig, NoiseValidationError
from backend.protocol import ProtocolError
from backend.simulation import ScenarioConfig, ScenarioValidationError, run_scenario


_CONFIGURATION_ERRORS = (
    NoiseValidationError,
    AttackValidationError,
    ScenarioValidationError,
    ProtocolError,
)


def _configuration_error(exc: Exception) -> ApiError:
    return ApiError(
        ErrorCode.BAD_REQUEST,
        f"the scenario configuration was refused: {exc}",
        details={"reason": str(exc), "error_type": type(exc).__name__},
    )


def run_simulation(
    request: SimulationRequest,
    *,
    include_ground_truth: bool = False,
) -> Dict[str, Any]:
    """Execute one scenario.

    ``include_ground_truth`` is decided by the *route*, not by the request body:
    the operational endpoint never passes true, so no request body can turn a
    normal simulation response into one carrying an attack label.
    """
    try:
        noise = NoiseConfig(
            noise_type=request.noise.noise_type,
            noise_strength=request.noise.noise_strength,
        ).validate()
        attack = AttackConfig(
            attack_type=request.attack.attack_type,
            fraction=request.attack.fraction,
            seed=request.attack.seed,
            parameters=dict(request.attack.parameters),
        )






        session_id, nonce, created_at = deterministic_session_identifiers(
            request.random_seed
        )
        config = ScenarioConfig(
            scenario_id=request.scenario_id,
            message=request.message,
            signer_id=request.signer_id,
            verifier_id=request.verifier_id,
            protocol_version=request.protocol_version,
            state_count=request.state_count,
            shot_count=request.shot_count,
            random_seed=request.random_seed,
            measurement_mode=request.measurement_mode,
            noise=noise,
            attack=attack,
            session_id=session_id,
            nonce=nonce,
            created_at=created_at,
            extra_authorized_verifiers=tuple(request.extra_authorized_verifiers),
        )
    except _CONFIGURATION_ERRORS as exc:
        raise _configuration_error(exc) from exc

    try:
        result = run_scenario(config, measure_runtime=True)
    except _CONFIGURATION_ERRORS as exc:
        raise _configuration_error(exc) from exc

    observable = result.observable
    verification = observable.verification

    payload: Dict[str, Any] = {
        "scenario_id": observable.scenario_id,
        "protocol_version": observable.protocol_version,
        "state_count": int(observable.state_count),
        "measurement_mode": observable.measurement_mode,
        "simulator_seed": int(observable.simulator_seed),
        "mismatch_count": int(observable.mismatch_count),
        "mismatch_proportion": float(observable.mismatch_proportion),
        "mean_channel_disturbance": float(observable.mean_channel_disturbance),
        "basis_counts": dict(observable.basis_counts),
        "states": [item.to_dict() for item in observable.states],
        "verification": {
            "accepted": bool(verification.accepted),
            "session_valid": bool(verification.session_valid),
            "message_valid": bool(verification.message_valid),
            "transcript_valid": bool(verification.transcript_valid),
            "state_sequence_valid": bool(verification.state_sequence_valid),
            "measurement_valid": bool(verification.measurement_valid),
            "errors": list(verification.verification_errors),
            "warnings": list(verification.verification_warnings),
            "state_count": int(verification.state_count),
            "mismatch_count": int(verification.mismatch_count),
            "basis_counts": dict(verification.basis_counts),
            "measurement_summary": dict(verification.measurement_summary),
        },
        "authorization": observable.authorization.to_dict(),
        "runtime_seconds": observable.runtime_seconds,
        "observable_only": not include_ground_truth,
        "note": (
            "Observable output is what a verifier could see. It is produced in "
            "simulation and is not a measurement of any physical device."
        ),
    }

    if include_ground_truth:
        truth = result.ground_truth.to_dict()
        payload["ground_truth"] = {
            "label": GROUND_TRUTH_LABEL,
            "scenario_id": truth["scenario_id"],
            "is_malicious": bool(truth["is_malicious"]),
            "noise": dict(truth["noise"]),
            "attack": dict(truth["attack"]),
            "notes": list(truth["notes"]),
        }

    return payload
