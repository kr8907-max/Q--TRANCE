# Attack Models

Milestone 3 -- Adversarial channel and protocol attack scenarios.

---

## What this document covers

* The six attack scenarios implemented in `backend.attacks`
* What each attacker does and does not do
* Observable effects vs ground truth
* Reproducibility
* Limitations and honest security statements

---

## Separation of concerns

Every experiment result separates::

    ObservableExperimentData   <-- what a verifier/detector can see
    GroundTruthMetadata        <-- what the experiment configured (benchmarking only)

The future detection engine must be able to operate using **only**
`ObservableExperimentData`. Ground truth is for test validation and experiment
bookkeeping, not for runtime detection.

---

## Channel attacks

### Channel tampering

**What the attacker does.**
Applies a Pauli operator (``X``, ``Z``, ``XZ``, or random) to a configurable
fraction of the received qubits::

    rho  ->  P rho P

**Attacker knowledge.** The states as they arrive, and how many there are. Not
the verifier's expected sequence or the derived basis for each state.

**Observable effect.** Some states no longer pass the verifier's quantum check.
The mismatch count and channel disturbance rise with ``fraction``. A Pauli that
commutes with the measurement basis is invisible for that state.

**Limitations.** Single-qubit, non-adaptive, no entanglement with an ancilla.

### Intercept-resend

**What the attacker does.**
For a configurable fraction of states, Eve measures the qubit in a chosen basis
and re-prepares the eigenstate she obtained::

    Alice --(rho)--> Eve measures in B --> |b><b| --> Bob

**Attacker knowledge.** The qubit as it arrives. Not the protocol's basis
choice.

**Observable effect.** When Eve guesses the basis correctly, no disturbance.
When she guesses wrong, the re-prepared state is unbiased in the protocol's
basis and the verifier's measurement becomes a coin flip. The average
disturbance depends on the basis overlap.

**Limitations.** Individual attack (one qubit at a time), no quantum memory, no
adaptive basis choice based on earlier outcomes.

---

## Protocol-level attacks

### Forgery

**What the attacker does.** Attempts to produce a transcript for a message the
signer never signed.

* ``mode="rebind_only"`` -- rewrites the message hash and binding in an
  existing transcript, keeping the original state sequence. The verifier's
  independent reconstruction detects the mismatch.
* ``mode="full_forge"`` -- builds a complete, self-consistent transcript for a
  chosen message. Because the state-sequence derivation is public and
  deterministic, this **verifies successfully** against the reference protocol.

**Attacker knowledge.** Public canonicalization, public derivation, the message
to forge. No key (none exists in this construction).

**Observable effect.** ``rebind_only`` is rejected by the verifier's binding
check. ``full_forge`` is accepted, demonstrating that the reference protocol
provides binding and integrity but **not unforgeability**.

**Limitations.** No quantum forgery strategy; the attack is classical
manipulation of public data.

### Impersonation

**What the attacker does.** Replaces the ``signer_id`` in the transcript with
an unauthorized identity and re-seals the transcript.

**Attacker knowledge.** The transcript and the identity to present.

**Observable effect.** The verifier's authorization check fails because the
presented signer is not in the authorized signer list. The quantum evidence is
untouched.

**Limitations.** No credential system, no authentication, no certificates.

### Unauthorized verification

**What the attacker does.** Replaces the ``verifier_id`` with an unauthorized
party and re-seals the transcript.

**Observable effect.** The authorization check fails. Distinct from
impersonation: this is "Bob is not entitled to verify this session", not
"someone pretends to be Alice".

**Limitations.** Same as impersonation: no real identity system.

### Replay

**What the attacker does.** Re-presents a previously valid transcript unchanged.

**Observable effect.** The single event may verify perfectly, because the
content is still valid. The attack exists in the *stream* of events: the same
nonce appears more than once. M3 produces the stream; a later milestone would
need a nonce store to detect the repetition.

**Limitations.** No freshness window, no clock skew model, no nonce database.

---

## Attack composition

Noise and attack are independently configurable::

    ScenarioConfig(
        noise=NoiseConfig("depolarizing", 0.05),
        attack=AttackConfig("intercept_resend", 0.3, ...),
    )

The runner applies noise first, then the attack, then verifies. This models the
realistic case where a channel is both noisy and under attack.

---

## Reproducibility

Every simulation supports an explicit seed. Same::

* protocol input
* noise configuration
* attack configuration
* master seed

produces the same observable data. Different seeds may produce different
outcomes where sampling is involved (intercept-resend basis choices, attack
target selection).

---

## What is NOT claimed

* Is intercept-resend detected in every instance? **No.** The disturbance is
  measurable *under the stated assumptions*; a basis guess that matches the
  protocol's choice causes no disturbance for that state.
* Does this simulator prove security under arbitrary conditions? **No.** It
  produces evidence for later analysis; it is not a security proof of any kind.
* Are every possible attack included? **No.** Only six reference scenarios are
  modelled; many realistic attack strategies are not represented.
* Are these scenarios rigorous mathematical proofs of cryptographic
  properties? **No.** They are engineering simulations for generating
  experimental data, not proofs.
