# Noise and Channel Models

Milestone 3 -- Honest noise models and quantum channel abstraction.

---

## What this document covers

* The quantum channel abstraction (`backend.noise.base`)
* The four implemented honest noise models
* Their mathematical definitions
* How to configure them
* What they do **not** claim

---

## Channel abstraction

A channel is an object that implements::

    rho_out = channel.apply(rho_in)

where both ``rho_in`` and ``rho_out`` are 2x2 density matrices (or pure-state
projectors). Every channel exposes:

* ``apply(rho)`` -- deterministic application
* ``probabilities`` -- the Pauli probability table (for Pauli channels)
* ``noise_type`` and ``noise_strength`` -- configuration metadata

The abstraction is deliberately minimal. It does **not** include:

* Threshold-based acceptance/rejection
* Attack detection
* Security scoring
* Statistical hypothesis testing

Those belong to later milestones.

---

## Depolarizing channel

### Mathematical definition

For a single qubit and parameter ``p`` in ``[0, 1]``::

    E(rho) = (1 - p) rho + p * I/2

Equivalently, as a Pauli channel::

    E(rho) = (1 - 3p/4) rho
           + (p/4) X rho X
           + (p/4) Y rho Y
           + (p/4) Z rho Z

### Reference points

* ``p = 0`` -- identity channel.
* ``p = 1`` -- completely depolarizing: ``E(rho) = I/2`` for every ``rho``.

### Implementation

`backend.noise.depolarizing.DepolarizingChannel`

Validated against Qiskit Aer ``depolarizing_error(p, 1)`` in the test suite.

### Limitations

This is a single-qubit depolarizing channel. It does not model correlated noise
across multiple qubits, non-Markovian effects, or coherent errors.

---

## Bit-flip channel

### Mathematical definition

For parameter ``p`` in ``[0, 1]``::

    E(rho) = (1 - p) rho + p X rho X

### Reference points

* ``p = 0`` -- identity.
* ``p = 1`` -- ``E(rho) = X rho X``.
* ``p = 1/2`` -- ``E(rho) = I/2`` for Z eigenstates; fixed point for X eigenstates.

### Implementation

`backend.noise.bit_flip.BitFlipChannel`

---

## Phase-flip channel

### Mathematical definition

For parameter ``p`` in ``[0, 1]``::

    E(rho) = (1 - p) rho + p Z rho Z

### Reference points

* ``p = 0`` -- identity.
* ``p = 1`` -- ``E(rho) = Z rho Z``.
* ``p = 1/2`` -- ``E(rho) = I/2`` for X eigenstates; fixed point for Z eigenstates.

### Implementation

`backend.noise.phase_flip.PhaseFlipChannel`

---

## Bit-phase-flip channel (Y channel)

### Mathematical definition

For parameter ``p`` in ``[0, 1]``::

    E(rho) = (1 - p) rho + p Y rho Y

### Reference points

* ``p = 0`` -- identity.
* ``p = 1`` -- ``E(rho) = Y rho Y``.
* ``p = 1/2`` -- ``E(rho) = I/2`` for X and Z eigenstates; fixed point for Y eigenstates.

### Implementation

`backend.noise.bit_phase_flip.BitPhaseFlipChannel`

---

## Parameter validation

Every channel rejects:

* ``p < 0`` or ``p > 1``
* Non-numeric values
* ``noise_type="none"`` with non-zero strength

Validation raises `NoiseValidationError` (a subclass of `ValueError`).

---

## Observable effect

Honest noise produces **measurable disturbance** in the verifier's quantum check:

* A noisy channel changes the received density matrix.
* The verifier measures in the basis derived from the message binding.
* The projective probability may drop below 1.0.
* The mismatch count rises.

None of these observations is interpreted as "attack" or "safe". They are raw
experimental outputs for later milestones.

---

## What is NOT claimed

* Does this simulator prove security that holds under every possible condition?
  **No.** It models specific noise processes under stated assumptions; it is
  not a proof of any kind.
* Are all possible channel errors represented? **No.** Only four single-qubit
  Pauli channels are implemented; many physical error models are absent.
* Does zero noise imply the protocol is secure? **No.** The reference protocol
  has no secret key; zero noise only means the quantum channel is ideal.
