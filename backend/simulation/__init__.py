"""Experiment simulation: scenarios, seeds, runner and results.

This package ties the lower layers together for reproducible experiments::

    backend.quantum  ->  backend.protocol  ->  backend.noise / backend.attacks
                                                          |
                                                          v
                                                 backend.simulation

What it produces
----------------
:class:`~backend.simulation.results.ExperimentResult`, which holds two strictly
separated halves:

* :class:`~backend.simulation.results.ObservableExperimentData` -- what a
  verifier can actually see, and the only thing a later detection engine may
  consume;
* :class:`~backend.simulation.results.GroundTruthMetadata` -- what the
  experiment actually did, for benchmarking only.

What it deliberately does not produce
-------------------------------------
No verdict. There is no threshold, no classifier, no security score and no
accept/reject decision about whether a run "was an attack". The numbers here are
observations; interpreting them belongs to a later milestone.
"""

from backend.simulation.results import (
    AuthorizationObservations,
    ExperimentResult,
    GroundTruthMetadata,
    ObservableExperimentData,
    StateObservation,
)
from backend.simulation.runner import ExperimentRunner, run_scenario, run_sweep
from backend.simulation.scenario import (
    MEASUREMENT_MODES,
    REFERENCE_ATTACK_FRACTION_SWEEP,
    REFERENCE_NOISE_SWEEP,
    ScenarioConfig,
    ScenarioValidationError,
    sweep_attack_fraction,
    sweep_noise,
)
from backend.simulation.seed import (
    MAX_SEED,
    SEED_DOMAIN,
    derive_seed,
    generator,
    validate_master_seed,
)

__all__ = [
    "MEASUREMENT_MODES",
    "REFERENCE_NOISE_SWEEP",
    "REFERENCE_ATTACK_FRACTION_SWEEP",
    "MAX_SEED",
    "SEED_DOMAIN",
    "ScenarioConfig",
    "ScenarioValidationError",
    "ExperimentRunner",
    "ExperimentResult",
    "ObservableExperimentData",
    "GroundTruthMetadata",
    "StateObservation",
    "AuthorizationObservations",
    "run_scenario",
    "run_sweep",
    "sweep_noise",
    "sweep_attack_fraction",
    "derive_seed",
    "generator",
    "validate_master_seed",
]
