# Observable Threat Detection Engine

Milestone 4 -- Protocol-aware, non-ML detection over observable experiment evidence.

**The M4 detector does not use attack ground truth and does not learn from attack labels.**

---

## 1. Purpose and scope

This document describes `backend.detection`, the Milestone 4 observable threat
detection engine.

The engine answers one question: *given the evidence a legitimate verifier can
actually observe, what can be established about this session?* It does **not**
answer "which attack was injected?", and it has no way to find out.

The engine converts observable experiment and protocol evidence into four things:

| stage | output | module |
| --- | --- | --- |
| normalized security measurements | `DetectionFeatures` | `backend.detection.features` |
| threat-specific evidence | `ThreatEvidence` findings | `backend.detection.evidence` |
| explainable findings | per-finding `explanation`, `evidence_items` | `backend.detection.engine` |
| one structured decision result | `DetectionResult` | `backend.detection.decision` |

In scope for Milestone 4:

* an observable input contract with no attack-facing field;
* a documented, explicit feature set;
* mismatch, disturbance and fidelity measurement;
* transcript/session integrity, replay, and authorization evidence;
* a structured evidence model and a categorical decision result;
* exact, sample-aware intervals on every reported rate.

Out of scope, deliberately, and named here so it is not mistaken for an
oversight:

* threshold calibration, ROC/PR analysis, FAR/FRR evaluation;
* hypothesis tests and multiple-comparison handling;
* machine learning of any kind;
* any single "security score" or threat number.

Those belong to Milestone 5.

---

## 2. The isolation rule

`backend.detection` must never import `backend.attacks`, must never read
`GroundTruthMetadata`, and must never look at an attack label, an attack
fraction, a noise strength or an oracle flag.

The detector may consume only:

* observable measurement data (per-state measurement outcomes);
* transcript and session information a legitimate verifier receives;
* the verifier's own structured result;
* authorization context (authorized identity sets, recorded flags);
* channel and measurement observations;
* the detector's own configured parameters.

The rule is enforced three independent ways:

1. **Structurally.** `ObservableDetectionInput` has no field that could carry an
   attack type, an attack fraction, a noise strength or an oracle label. There is
   nowhere to put one.
2. **Statically.** The test suite parses every file under `backend/detection`
   with `ast` and fails if any import names `backend.attacks` or
   `backend.simulation`, or if any identifier, attribute, keyword or constant is
   an attack label.
3. **At runtime.** A subprocess check asserts that `import backend.detection`
   does not put `backend.attacks` in `sys.modules`.

The adversarial test for the whole property is *attack-label independence*: the
same observable input is paired with two different hidden ground truths (one
honest, one malicious) and the detector output must be byte-identical. The test
also asserts that the two observables really are identical and that the two
ground truths really do differ, so the check cannot pass vacuously.

Why the adapter is duck-typed: `ObservableDetectionInput.from_observable` reads
attributes off whatever observable object it is handed. It deliberately does not
import `backend.simulation`, because importing that package runs its `__init__`,
which imports the experiment runner, which imports `backend.attacks`. A detector
that imported the simulator would transitively depend on the attack layer while
naming none of it.

---

## 3. Architecture and dependency direction

```
quantum  ->  protocol  ->  noise / attacks  ->  observable experiment data
                                                        |
                                                        v
                                                   detection
                                                        |
                                                        v
                                        future calibration / security analysis
```

Detection sits **below** calibration and depends on **nothing** above it in the
attack layer. The dependency direction is one-way and is asserted in tests: no
module in `backend.detection` imports anything outside `backend.detection`,
`backend.protocol` and the standard library.

Module map:

| module | responsibility |
| --- | --- |
| `models` | the observable input contract and shared models |
| `statistics` | exact binomial intervals for sampled rates |
| `mismatch` | `D_m = N_mismatch / N_valid` |
| `disturbance` | `D_v = N_disturbed / N_verification_states` |
| `fidelity` | `F = <psi\|rho\|psi>`, and its redundancy with `p_match` |
| `consistency` | transcript and session integrity, recomputed |
| `authorization` | signer and verifier authorization, kept separate |
| `replay` | the session/nonce/transcript reuse ledger |
| `features` | the documented observable feature set |
| `evidence` | the structured `ThreatEvidence` model |
| `decision` | the structured `DetectionResult` model |
| `engine` | the pipeline that wires them together |

Pipeline inside the engine:

```
ObservableDetectionInput
    -> consistency      protocol/session integrity, recomputed from the artifact
    -> authorization    signer and verifier membership tests, kept separate
    -> replay           session/nonce/transcript reuse against a registry
    -> features         the documented observable feature set
    -> findings         ThreatEvidence, one per established deviation
    -> decision         DetectionResult
```

Each computation happens exactly once, and the sub-analyses are passed into
`extract_features` rather than recomputed, so no two components can disagree
about the same number.

The engine is lightweight by construction: it never re-runs a circuit and never
touches the quantum simulator. It aggregates numbers the verifier already
computed.

---

## 4. The observable input contract

`ObservableDetectionInput` is the boundary. Its contract in one sentence: *if a
legitimate verifier cannot see it, it is not here.*

Fields, grouped by where the verifier got them:

**Identity** (read from the received transcript): `session_id`, `nonce`,
`protocol_version`, `message_binding`, `declared_transcript_hash`, `signer_id`,
`verifier_id`, `created_at`. All `None` when the transcript was absent or
unparseable.

**Verifier knowledge** (supplied independently, never read out of the
transcript): `message`, `verifier_context_id`, `expected_protocol_version`. A
transcript cannot talk the verifier into a different protocol, because the
expected version comes from the verifier.

**Authorization**: `authorized_signers`, `authorized_verifiers`, and the booleans
`reported_signer_authorized` / `reported_verifier_authorized` the verifier
recorded. The engine recomputes the membership tests and reports any disagreement
with the recorded flags.

**Transcript material**: `transcript_payload` and `transcript_parse_error`, so
the detector can recompute the canonical digest itself instead of trusting the
stored one.

**Measurement**: `states` (a tuple of `StateEvidence`), `declared_state_count`,
`measurement_mode`, `basis_counts`.

**Verification**: `verification`, the verifier's own structured outcome
(`VerificationEvidence`).

### What is deliberately absent

`ObservableExperimentData` carries three fields the detector must ignore even
though they sit in the observable half:

* `scenario_id` -- Milestone 3 scenario identifiers encode experiment parameters
  (for example `"base-attack-0.5"`). Reading one would be a label leak in
  disguise.
* `simulator_seed` -- not observable to a real verifier; it exists so a
  simulation can be replayed.
* `mean_channel_disturbance` -- a trace distance between the *ideal* received
  state and the actual one. A real verifier does not hold the ideal received
  state, so this number is a simulation artefact, not an observation. The engine
  instead derives disturbance from `probability_expected`, the projective match
  probability the verifier itself computes.

`runtime_seconds` is likewise ignored: it is a property of the machine, not of
the protocol.

There is no field for an attack type, an attack fraction, a noise strength, a
ground-truth flag or an oracle label, and there never will be one: adding one
would break the isolation this milestone exists to establish.

### Malformed input is a finding, not an exception

Any field may be missing or malformed. `DetectionInputError` is reserved for
*programming* errors in constructing input (for example a `match_tolerance`
outside `[0, 1]`). Untrusted or malformed protocol data never raises: it is
reported as a finding. `StateEvidence.usable` is the single definition of
"this record can contribute to a statistic", and unusable records are excluded
from denominators and counted.

---

## 5. Feature extraction

Every feature the engine uses is declared once, in `FEATURE_CATALOG`, with its
definition, source, mathematical meaning, units/range, and failure behaviour.
The catalog is data, not prose. The test suite asserts that every catalogued
feature exists on `DetectionFeatures`, and the documentation test asserts that
this document still names the same features -- so "documentation matches
implementation" is an executable property rather than a promise.

There is no composite score. No `security_score`, no weighted sum, no single
"threat number". A weighted sum would hide exactly the structure the evidence is
supposed to expose. Where two features are mathematically the same signal, the
redundancy is *stated* in `DetectionFeatures.redundancies`.

### The feature set

| feature | definition | source | range / failure |
| --- | --- | --- | --- |
| `mismatch_rate` | `D_m = N_mismatch / N_valid` | per-state `matched` flags | `[0, 1]`, `None` when `N_valid = 0` |
| `measurement_counts_by_basis` | count of usable observations per basis | per-state `basis` | non-negative ints summing to `N_valid` |
| `basis_distribution` | counts per basis divided by `N_valid` | `measurement_counts_by_basis` | each in `[0, 1]`; empty when undefined |
| `verification_state_disturbance_rate` | `D_v = N_disturbed / N_verification_states` | per-state `probability_expected` | `[0, 1]`, `None` when no usable state |
| `projective_match_probability` | `mean_i probability_expected_i` | per-state `probability_expected` | `[0, 1]`, `None` when no usable observation |
| `reconstruction_fidelity` | `mean_i <psi_i\|rho_i\|psi_i>` | per-state `probability_expected` | `[0, 1]`, `None` when no usable observation |
| `state_count_consistency` | declared `state_count` equals observed state count | transcript `state_count`, observation list | `True` / `False` / `None` |
| `transcript_validity` | transcript parsed and satisfied every integrity check | declared transcript payload | `True` / `False` / `None` when no transcript |
| `transcript_hash_validity` | declared hash equals recomputed canonical digest | declared transcript payload | `True` / `False` / `None` when not encodable |
| `session_consistency` | protocol version is spoken and transcript is addressed here | declared version/verifier id, verifier context | `True` / `False` / `None` |
| `nonce_freshness_state` | whether the observed nonce was seen in an earlier event | replay registry and declared nonce | `True` (fresh) / `False` (reused) / `None` |
| `signer_authorization_validity` | presented signer is a member of the authorized signers | declared `signer_id`, authorization context | `True` / `False` / `None` |
| `verifier_authorization_validity` | presented verifier is a member of the authorized verifiers | declared `verifier_id`, authorization context | `True` / `False` / `None` |
| `cross_verifier_disagreement` | disagreement between two verifiers' observations of one session | a second verifier's observations | always `None` at Milestone 4 |

### Cross-verifier disagreement

The brief lists it as a possible feature. The Milestone 2 and 3 data model records
exactly one verifier identity per session, so no cross-verifier comparison is
possible. Rather than invent a value, the feature is reported as unavailable with
the reason attached. When the data model grows a second verifier view, this is the
single place to fill in.

### Basis statistics

Per-basis counts, mismatch counts/rates, disturbance counts/rates and the set of
disturbed bases are reported, because a disturbance concentrated in one basis is
structurally different from one spread evenly, and because explainability asks
which bases were affected.

---

## 6. Mismatch analysis

Given `N_valid` usable per-state observations and `N_mismatch` of them whose
observed outcome disagreed with the expected eigenvalue:

```
D_m = N_mismatch / N_valid
```

`N_valid` counts only records that are actually usable. Records that are missing
or malformed are counted separately (`n_missing`, `n_malformed`) and excluded
from the denominator. Folding them in as "matches" would understate the rate;
folding them in as "mismatches" would overstate it. Neither is honest.

Documented and tested failure behaviour:

| condition | behaviour |
| --- | --- |
| `N_valid == 0` | `mismatch_rate` is `None`, `defined` is `False`; no division is attempted |
| missing observations | counted in `n_missing`, excluded from the denominator, reported in `notes` |
| malformed observations | counted in `n_malformed`, excluded, reported |
| `N_valid > 0` | exact point estimate plus an exact Clopper-Pearson interval |

This module does not compare `D_m` against any threshold and does not decide
attack/no-attack. It produces a measurement. A reference expectation may be
supplied by the caller, in which case the *engine* -- not this module -- labels
the strength of the deviation.

`D_m` versus `D_v`: in the deterministic `"projective-analytic"` measurement mode,
"the outcome disagreed" and "the received state is not the expected eigenstate"
are the same event, so `D_m` and `D_v` coincide exactly. In `"sampled"` mode they
differ: `D_m` is a finite-shot outcome frequency while `D_v` is computed from the
analytic projective probability.

---

## 7. Verification-state disturbance

This statistic is called `verification_state_disturbance_rate` and nothing else.
It is **not** called "decoy disturbance", because no decoy-state protocol is
implemented anywhere in this project: there is no decoy intensity, no
signal/decoy ratio and no decoy analysis. Borrowing that vocabulary would suggest
a security argument the reference construction does not make.

For each usable observation the verifier computes `probability_expected`: the
analytic projective probability that the received qubit yields the expected
eigenvalue of the expected basis. A verification state is disturbed when that
probability is strictly below `1 - tolerance`:

```
N_disturbed = |{ i : probability_expected_i < 1 - tolerance }|
D_v         = N_disturbed / N_verification_states
```

`tolerance` is the floating-point tolerance that defines "the received qubit *is*
the expected eigenstate" -- the same constant the Milestone 2 verifier uses
(`DEFAULT_MEASUREMENT_TOLERANCE`). It is a numerical definition, not a security
threshold: for a noiseless, untampered channel the projective probability is
exactly 1 and `D_v` is exactly 0.

### Saturation, and what it means

Because the reference expectation is *exact*, `D_v` is a **detection** indicator,
not a magnitude indicator. Any nonzero channel deviation -- a depolarizing
probability of 0.001 just as much as an intercept-resend attack on every state --
moves every projective probability strictly below 1, so `D_v = 1` in all of those
cases. That is a true statement about the mathematics, not a defect: it answers
"has the channel changed anything at all?", and it answers it sharply.

The *magnitude* of the deviation is carried by the fidelity (section 8), which
varies continuously and is where a reader should look for "how far from ideal".
Reporting both, and saying which one answers which question, is the point.

### Relationship to the mismatch rate

`D_v` and `D_m` are **not** presented as independent evidence, and the analysis
reports whether they coincide:

* `"projective-analytic"` mode: the outcome is deterministic, so "the outcome
  disagreed" is exactly "the state is disturbed". `D_v` and `D_m` are then the
  *same number computed from the same records*, and
  `DisturbanceAnalysis.identical_to_mismatch` is `True`. They are never counted as
  two signals.
* `"sampled"` mode: `D_m` is a finite-shot outcome frequency whereas `D_v` uses
  the analytic probability. They are genuinely different statistics, and the flag
  is `False`.

Either way the redundancy is stated, not hidden.

---

## 8. Fidelity

For a pure expected state `|psi>` and the received qubit `rho`:

```
F = <psi|rho|psi>
```

The Milestone 1 core proves (`backend/quantum/density.py`) that for a pure
expected state this is *identically* the projective match probability
`p_match = Tr(P_psi rho)`, not merely approximately equal. The verifier already
computes that quantity per state as `probability_expected`, so this module
recomputes no quantum state: it aggregates the value the verifier observed.

```
analytic_mean_fidelity = mean_i probability_expected_i
```

### Analytic fidelity versus sampled verification probability

Two different kinds of quantity are kept apart and never averaged together or
presented as two independent signals:

* **analytic fidelity from a state representation** -- `F = <psi|rho|psi>`, an
  exact number. Reported as `analytic_mean_fidelity` together with the minimum
  over the session.
* **empirical sampled verification probability** -- the frequency with which
  finite-shot measurement outcomes agreed with the expectation. Only meaningful
  in the `"sampled"` measurement mode; `None` otherwise. Reported as
  `sampled_match_frequency`.

### Redundancy, stated rather than hidden

Per state, `F_i == p_match_i == probability_expected_i`. Therefore:

* the mean analytic fidelity **is** the mean projective match probability -- one
  number, not two;
* `1 - analytic_mean_fidelity` is the mean per-state *mismatch probability*,
  which is **not** the mismatch rate `D_m`: `D_m` counts states whose fidelity
  fell below `1 - tolerance`, whereas `1 - mean(F)` averages the shortfall. They
  agree only in the extremes (all states exact, or all states fully depolarised),
  and the difference is reported in `FidelityAnalysis.notes`.

The detector reports fidelity once and points at the redundancy instead of
double-counting it as independent evidence.

---

## 9. Transcript and session integrity

These are **protocol integrity findings, not quantum findings**. An invalid
transcript hash, a broken message binding, an unexpected protocol version, a
state count that disagrees with the declared state list, or a declared state
sequence that the verifier's own derivation contradicts -- all of these are
properties of the artifact and of the protocol, and none of them is evidence
about a qubit. They are never reported as a quantum attack.

The detector recomputes everything it can:

* it does not trust `transcript_hash`: it recomputes the canonical digest from
  the declared payload and compares;
* it does not trust `message_binding`: it recomputes it from `protocol_version`,
  `session_id`, `nonce` and the message the verifier holds;
* it does not trust the declared state sequence: it derives the sequence itself
  from the binding it recomputed, exactly as the Milestone 2 verifier does.

This mirrors the verifier deliberately. Where the verifier *rejects*, the
detector *explains*, and the two must not disagree about the facts.

Checks performed:

| check | evidence category when it fails |
| --- | --- |
| transcript could not be parsed | `TRANSCRIPT_INTEGRITY` |
| `transcript_hash` != recomputed canonical digest | `TRANSCRIPT_INTEGRITY` |
| transcript content not canonically encodable | `TRANSCRIPT_INTEGRITY` |
| `message_binding` != recomputed binding | `TRANSCRIPT_INTEGRITY` |
| protocol version not one this detector speaks | `CONSISTENCY_ANOMALY` |
| transcript addressed to a different verifier | `CONSISTENCY_ANOMALY` |
| declared `state_count` != declared state list length | `CONSISTENCY_ANOMALY` |
| declared `state_count` != observed state count | `CONSISTENCY_ANOMALY` |
| `state_sequence_metadata` != independently derived metadata | `CONSISTENCY_ANOMALY` |
| declared state sequence != independently derived sequence | `SIGNATURE_VERIFICATION_ANOMALY` |
| verifier rejected with no detector explanation | `CONSISTENCY_ANOMALY` |

Every parse step is guarded. A payload that is not an object, a binding that is
not a hex digest, a state list of the wrong shape -- each produces a recorded
violation or an "unavailable" result. This module never raises on untrusted data,
because malformed evidence is a finding to be reported, not an exception to be
thrown at the caller.

### Forgery-related evidence

Forgery evidence rests on **observable verification inconsistency**, not on
measurement deviation. It is emitted as `SIGNATURE_VERIFICATION_ANOMALY` when the
declared state sequence does not match the sequence the detector derives
independently from the message binding -- i.e. the declared signature does not
correspond to this message.

Not every mismatch is called forgery. A measurement mismatch is a quantum/channel
observation; a hash or binding failure is a transcript-integrity observation. The
categories are deliberately orthogonal, and the engine does not upgrade one into
another.

---

## 10. Replay detection

Replay is not a quantum property.

A replayed transcript may carry perfectly undisturbed qubits, a valid hash, a
valid binding and a correct state sequence -- that is precisely what makes replay
worth modelling. Every single-event observable can be clean. What makes the event
a replay is that **the session identity was consumed before**.

The detector therefore derives replay evidence from the protocol/session identity
it can observe -- the session identifier, the nonce and the transcript identity --
and never from quantum disturbance. Claiming a measurement disturbance "detects
replay" would be an unsupported attribution.

`ReplayRegistry` is a small in-memory ledger of consumed identities. It is
deliberately not a database and not persisted: Milestone 4 needs a clean,
deterministic, testable abstraction, and Milestone 5 or later can put a store
behind the same interface.

Properties the interface guarantees:

* **deterministic** -- the same sequence of calls produces the same evidence. No
  clocks, no randomness, no hash-ordering dependence.
* **testable** -- `check` is *pure*: it reports what *would* happen and mutates
  nothing. `observe` records and returns the evidence that applied *before* the
  record. The two are separated so a test can ask "is this a replay?" without
  changing the answer for the next question.
* **resettable for experiments** -- `reset` empties the ledger, so a sweep can
  give each scenario a clean history.
* **safe under malformed input** -- a missing or non-string identifier simply
  cannot be checked. It is reported as unavailable rather than being coerced into
  a value that might accidentally match, and it is never recorded.

`nonce_reused`, `session_reused` and `transcript_reused` are reported
**separately**, because they are different observations: a fresh session that
reuses an old nonce is not the same event as a whole transcript being
resubmitted, and collapsing them would lose that distinction.

`ThreatDetectionEngine.detect` is side-effect free by default (`consume=False`),
so the same input always yields the same result. A caller that wants to record
the event asks for it explicitly.

---

## 11. Authorization and impersonation

These are different attack surfaces and must not be merged into one "identity
mismatch":

| check | question |
| --- | --- |
| **signer authorization** | "someone claims to be Alice" |
| **verifier authorization** | "Bob is not entitled to check this session" |

They concern different fields (`transcript.signer_id` versus
`transcript.verifier_id` and the verifier's own identity), they are decided by
different bookkeeping, and conflating them would hide one of the surfaces. The
engine emits one finding per violated check, each naming the role:

* **SCENARIO 1** -- an unauthorized signer produces `SIGNER_AUTHORIZATION`.
* **SCENARIO 2** -- an unauthorized verifier produces `VERIFIER_AUTHORIZATION`.

The evidence is a **membership test on declared identifiers**: the identity the
artifact presents, against the set the verification system authorises. It is
deterministic and needs no threshold.

It is *not* proof of identity. Nothing in this project authenticates anybody:
there is no credential, no certificate and no key, so `signer_id` is a name. A
quantum measurement cannot establish identity. This module says which name was
presented and whether that name was authorized, and stops there.

The engine recomputes the membership test rather than trusting a pre-computed
boolean, and reports when the two disagree -- a disagreement between the
verifier's recorded flag and the recomputed result is itself evidence that the
bookkeeping and the artifact do not line up.

---

## 12. Channel and quantum measurement anomaly evidence

These two categories carry the statistical (measurement) evidence, and the engine
is careful not to present one signal as two.

* `CHANNEL_ANOMALY` is emitted whenever the **state-level** evidence deviates: at
  least one verification state is disturbed, the fidelity is below the reference
  expectation, or specific bases are affected. Its evidence includes the
  disturbance rate, the disturbed-state count, the verification-state count, the
  mean fidelity, the affected bases and the per-basis disturbance rates.
* `QUANTUM_MEASUREMENT_ANOMALY` is emitted only when the **outcome-level**
  evidence deviates *and* is not already fully described by the state-level
  evidence -- which happens in the `"sampled"` measurement mode, where the
  finite-shot outcome frequency is a genuinely different statistic.

In the deterministic `"projective-analytic"` measurement mode the two are the
same event, so only `CHANNEL_ANOMALY` is emitted and the redundancy is recorded
in `features.redundancies`. In `"sampled"` mode both may be emitted, because the
statistics genuinely differ.

Both findings derive their evidence from mismatch, disturbance, per-basis
statistics, fidelity and basis anomalies. There is **no** branch anywhere that
says "intercept-resend implies attack". The engine cannot know that, and does not
pretend to. The finding text states what deviated and by how much, and explicitly
says that the evidence is consistent with a channel that changed the qubits, with
honest noise, or with tampering, and that the detector does not distinguish those
causes.

---

## 13. The evidence model

`ThreatEvidence` is what the engine emits. It is designed so a reader can answer,
without re-running anything:

* **what** was observed (`observed_values`, `evidence_items`);
* **against what** it was compared (`comparison_values`), when a comparison was
  available at all;
* **how strong** the evidence is (`strength`, `severity`, `calibration`);
* **whether it blocks** (`blocking`);
* **where it came from** (`source_metrics`, `session_reference`, `timestamp`);
* **what it means**, in one sentence (`explanation`).

Fields: `finding_id`, `category`, `severity`, `calibration`, `blocking`,
`strength`, `evidence_items`, `observed_values`, `comparison_values`,
`explanation`, `source_metrics`, `session_reference`, `timestamp`, `notes`.

`finding_id` is assigned deterministically from the category and the position
within that category (`{CATEGORY}-{NN}`), so identical observable input produces
identical findings down to their identifiers.

### Categories

| category | meaning |
| --- | --- |
| `TRANSCRIPT_INTEGRITY` | the received transcript artifact is not internally consistent or not bound to this message |
| `REPLAY` | a session identity that had already been consumed was presented again |
| `SIGNER_AUTHORIZATION` | the presented signer identity is not among the authorized signers |
| `VERIFIER_AUTHORIZATION` | the presented verifier identity is not among the authorized verifiers |
| `QUANTUM_MEASUREMENT_ANOMALY` | observed verification outcomes disagree with the expected eigenvalues more often than the reference accounts for |
| `CHANNEL_ANOMALY` | received states deviate from the reference expectations supplied for them |
| `SIGNATURE_VERIFICATION_ANOMALY` | the declared signature does not correspond to this message |
| `CONSISTENCY_ANOMALY` | a protocol/session invariant failed, or the verifier's rejection is unexplained |

### Severity taxonomy

Deterministic categories -- the invariant either held or it did not -- carry a
fixed, documented severity:

| category | severity | why |
| --- | --- | --- |
| `TRANSCRIPT_INTEGRITY` | `HIGH` | the artifact cannot be trusted |
| `CONSISTENCY_ANOMALY` | `MODERATE` | a protocol invariant failed |
| `SIGNATURE_VERIFICATION_ANOMALY` | `HIGH` | the declared signature does not match independent derivation |
| `REPLAY` | `HIGH` | a consumed identity was reused |
| `SIGNER_AUTHORIZATION` | `CRITICAL` | an unauthorized identity acted as signer |
| `VERIFIER_AUTHORIZATION` | `CRITICAL` | an unauthorized identity acted as verifier |

Statistical categories carry `UNCALIBRATED` unless the caller supplied a
reference expectation, in which case severity is derived from the exact binomial
interval -- a documented, sample-aware rule, never an absolute threshold.

`UNCALIBRATED` is a first-class value, not a placeholder. It means "the evidence
is real and reported, but no calibrated rule maps it to a severity yet". Every
statistical finding defaults to it.

### Blocking

The deterministic categories block: the session must not be treated as
acceptable. The statistical categories do not -- an uncalibrated anomaly is
reported, not enforced.

---

## 14. The decision model

`DetectionResult` answers three questions and refuses to answer a fourth:

1. *Is the protocol/session structure valid?* -- `protocol_valid`.
2. *What was observed?* -- `findings` and `features`.
3. *Which family of problems, if any, applies?* -- `overall_status`.
4. *(refused) How dangerous is this, on a scale?* -- there is no security score.

The status names which *family* of findings fired and never how close a number
came to a limit:

| findings present | overall status |
| --- | --- |
| none | `CLEAR` |
| exactly one family | that family's status |
| two or more families | `MULTIPLE_FINDINGS` |

Family mapping:

* integrity (`TRANSCRIPT_INTEGRITY`, `CONSISTENCY_ANOMALY`,
  `SIGNATURE_VERIFICATION_ANOMALY`, `REPLAY`) -> `INTEGRITY_VIOLATION`;
* authorization (`SIGNER_AUTHORIZATION`, `VERIFIER_AUTHORIZATION`) ->
  `AUTHORIZATION_VIOLATION`;
* quantum (`QUANTUM_MEASUREMENT_ANOMALY`, `CHANNEL_ANOMALY`) ->
  `QUANTUM_ANOMALY`.

`protocol_valid` covers the protocol/session integrity axis only. Authorization is
a **policy** axis, not a protocol-structure property -- a session can be
structurally perfect and still be attempted by an unauthorized party -- so an
authorization finding is reported through the findings and the overall status but
does not make `protocol_valid` false.

The `explanation` is one paragraph and never attributes an attack. It states what
was observed and, for measurement anomalies, that no cause is attributed.

`DetectionResult.diagnostic_statistics()` exposes the statistics and their exact
intervals with **no decision attached**: `mismatch_rate`, `mismatch_interval`,
`disturbance_rate`, `disturbance_interval`, `mean_fidelity`, `minimum_fidelity`,
`sample_size`, `disturbance_sample_size`, `measurement_mode`, `redundancies`, and
an explicit `multiple_testing_handling: "not implemented at Milestone 4"`. It is
the interface Milestone 5 will calibrate.

---

## 15. Statistical methodology

Every rate the engine reports is accompanied by an **exact Clopper-Pearson
binomial interval** at a stated confidence level. That is the only statistical
machinery in Milestone 4.

A bare proportion hides how much information the sample carries: `1/8` and
`1000/8000` are the same number and very different evidence. The interval carries
the sample-size context, so no arbitrary "within 5%" band is ever needed.

For `k` successes in `n` trials the interval at confidence `c` is the exact
interval `[L, U]` with:

```
alpha = 1 - c
L = 0                                          if k = 0
L = Beta^{-1}(alpha/2;   k,     n - k + 1)     otherwise
U = 1                                          if k = n
U = Beta^{-1}(1-alpha/2; k + 1, n - k)         otherwise
```

It is *conservative*: the true coverage is at least `c`, so a false "the
reference lies outside the interval" conclusion happens with probability at most
`1 - c`.

The default confidence is `0.999` -- a 1-in-1000 description error budget,
matching the project's existing sampled-test policy (`tests/quantum/statutil.py`).
The two implementations are cross-checked against each other in the test suite
rather than assumed to agree.

A zero denominator yields an explicitly undefined estimate rather than a division
error or a fabricated zero, because "no observations" and "no observed
occurrences" are different statements.

### The multiple-testing problem

Milestone 4 runs **no hypothesis tests**. It reports diagnostic statistics and the
mathematical relationships between them.

It deliberately does **not** implement "five independent tests at alpha = 0.05",
which the architecture review identified as a defect. Running five unadjusted
tests over one session inflates the family-wise error rate far beyond the nominal
level, and no single test here is the primary verification statistic.

Choosing the primary verification statistic, deciding joint/multiple-comparison
handling, calibrating thresholds and evaluating FAR/FRR all belong to
Milestone 5. `DetectionResult.diagnostic_statistics()` is the clean interface
prepared for that work.

Where a caller *does* supply a reference expectation, severity is derived from
the interval the engine already reports:

* observed rate does not exceed the reference -> `LOW` (no anomaly finding is
  emitted for it in the first place);
* reference lies strictly below the interval's lower bound -> `HIGH`: the sample
  is inconsistent with the reference at the stated confidence;
* otherwise -> `MODERATE`: the point estimate exceeds the reference but the
  sample does not exclude it.

This rule adds no new constant and no absolute threshold.

---

## 16. Limitations, deferred work, and usage

### Known limitations

* **No calibrated thresholds.** Every statistical finding defaults to
  `UNCALIBRATED`. Until a caller supplies a reference expectation, an anomaly is
  reported and not adjudicated.
* **No cause attribution.** Honest noise, an intercept-resend attack, tampering
  and an unexplained disturbance are indistinguishable at this layer, and the
  engine does not try to tell them apart. The same observable data produces the
  same result whatever caused it.
* **Disturbance saturates.** Because the reference expectation is exact, `D_v` is
  1 whenever *any* deviation is present. Magnitude lives in the fidelity.
* **No cross-verifier comparison.** The M2/M3 data model records one verifier
  identity per session, so `cross_verifier_disagreement` is always unavailable.
* **Authorization is a membership test, not authentication.** Identifiers are
  names; nothing in this project issues credentials or keys.
* **No unforgeability claim.** The reference construction is not a standardized
  QDS protocol and this engine inherits that.
* **Replay needs history.** Without a `ReplayRegistry`, replay evidence is
  reported as unavailable rather than assumed absent.
* **No completeness claim.** The detector reports what it can establish from the
  evidence supplied. It makes no statement about attacks that leave no observable
  trace.

### Deferred to Milestone 5

Threshold calibration; ROC/PR analysis; FAR/FRR evaluation; selection of the
primary verification statistic; joint and multiple-comparison handling; any
security score. The engine exposes `diagnostic_statistics()` and the
`DetectorParameters` reference fields as the interfaces for that work.

### Usage

```python
from backend.detection import (
    ObservableDetectionInput,
    DetectorParameters,
    ReplayRegistry,
    detect,
)

# Build the contract from observable evidence only.
detection_input = ObservableDetectionInput.from_observable(
    observable, transcript=transcript, message=message, verifier_context=context
)
detection_input = ObservableDetectionInput.with_authorization(
    detection_input, observable.authorization
)

registry = ReplayRegistry()
result = detect(
    detection_input,
    parameters=DetectorParameters(),   # no reference expectations => UNCALIBRATED
    replay_registry=registry,
    consume=True,                      # opt in to recording the event
)

result.overall_status                 # CLEAR / INTEGRITY_VIOLATION / ...
result.protocol_valid                 # protocol/session integrity axis
result.findings                       # tuple[ThreatEvidence, ...]
result.diagnostic_statistics()        # statistics for future calibration
result.to_dict()                      # JSON-serialisable, no security score
```

`ThreatDetectionEngine` is reusable across sessions and holds the parameters and
the optional replay registry. `detect(...)` is a convenience wrapper that builds
one engine per call.
