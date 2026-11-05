# Security Argument for SIH26141

Milestone 6 — Structured security argument for the reference prototype.

This document is a **conditional** argument: every claim is qualified by the
assumptions it depends on, and sections 7.11–7.13 make explicit what is *not*
established. A reader who skips those sections will misread the argument.

---

## 7.1 System scope

The system is a **reference prototype** of a quantum-digital-signature
construction using teleportation, Bell-state entanglement, Pauli corrections and
projective measurement. It is implemented in Qiskit and simulated with
qiskit-aer. The prototype includes:

- a quantum core (M1) that prepares states, performs teleportation and measures;
- a protocol layer (M2) that binds a message to a state sequence and produces a
transcript;
- a noise and attack simulation layer (M3) that models honest channels and six
attack families;
- an observable detection engine (M4) that produces structured evidence from
measurement outcomes without reading attack labels;
- a statistical calibration layer (M5) that derives a decision threshold from
honest-only data;
- a security analysis layer (M6) that records assumptions, interprets bounds and
assesses composition.

The construction is **not** a complete, formally proven QDS scheme. The organiser
requirement specifies primitives and goals, not a full security protocol.

---

## 7.2 Security objectives

The prototype's security objective is **threat detection and characterisation**
rather than cryptographic unforgeability. Specifically:

- identify whether an observed session is statistically consistent with a
calibrated honest model;
- characterise which threat families are visible to which layer;
- measure empirical false-rejection and false-acceptance rates on modelled
attacks;
- prevent overclaim by machine-checking every sentence against a forbidden-claim
list.

No objective claims information-theoretic security or unconditional security,
and none claims universal attack detection.

---

## 7.3 Threat model

The threat model includes six attack families, each modelled as a non-adaptive
transformation applied to the protocol material before verification:

1. **Forgery** — a transcript that claims a message the signer never signed.
2. **Impersonation** — a transcript that claims an unauthorised signer identity.
3. **Unauthorized verification** — a verifier identity not entitled to check the
session.
4. **Replay** — a previously issued transcript presented again.
5. **Intercept-resend** — an attacker measures a subset of states and forwards a
replacement.
6. **Channel tampering** — an attacker applies a Pauli operator to a subset of
states.

The attacker does **not** adapt to the verifier's measurement outcomes, does
**not** know the verifier's expected state sequence, and does **not** control
the channel outside the simulated fraction.

Adaptive attacks, side channels, hardware manipulation and denial of service are
outside the scope.

---

## 7.4 Trusted assumptions

The full assumption register lives in `backend/security/assumptions.py` and is
inspectable at runtime. The assumptions fall into nine categories:

A. **Simulator assumptions** — independence of draws, Born-rule sampling.
B. **Honest-channel assumptions** — the mismatch probability is homogeneous for
the depolarizing channel (exact) and approximately homogeneous for flip channels.
C. **Independence assumptions** — states within a session are independent; trials
across sessions are independent.
D. **Identical-distribution assumptions** — the per-state mismatch probability is
constant under depolarizing noise.
E. **Finite-sample assumptions** — a confidence interval is a statement about an
estimator, not a cryptographic security parameter.
F. **Measurement-model assumptions** — the meaning of "matched" is defined by the
configured measurement mode and travels with every observation.
G. **Protocol-binding assumptions** — the binding derivation, state-sequence
derivation and transcript canonicalisation are public and deterministic.
H. **Classical identity assumptions** — signer and verifier identity checks are
classical protocol controls, not quantum measurements.
I. **Attack observability assumptions** — attacks are non-adaptive; no attack
label reaches the verification decision.

Every assumption carries a status (exact, satisfied, approximate, not verified,
violated), an evidence string and the consequence of its violation. The register
is serialised into every report.

---

## 7.5 Observable evidence

The verifier observes:

- **Quantum evidence** — measurement outcomes for each verification state,
compared to the expected outcome. This produces mismatch counts, disturbance
rates and fidelity estimates.
- **Protocol evidence** — transcript integrity, binding consistency, signature
verification, nonce freshness.
- **Authorization evidence** — signer and verifier identity membership in the
authorised sets.
- **Temporal evidence** — whether a nonce has appeared before (replay
indication).

The detection engine (M4) produces eight evidence categories from these
observables. It never reads attack labels, ground truth or calibration results.

---

## 7.6 Statistical decision rule

The primary decision statistic is the mismatch rate `D_m = N_mismatch / N_valid`.

The decision rule is:

    reject H0 when N_mismatch > k_crit(N)

where `k_crit(N)` is derived from an honest-only calibration by the
`honest-null-quantile-with-upper-confidence-bound` method:

    p_upper = Beta^{-1}(1 - alpha_cal; K + 1, T - K)
    k_crit(N) = min { k : P[Binomial(N, p_upper) <= k] >= 1 - alpha_eval }

`alpha_cal + alpha_eval = alpha` (default 0.05, split evenly).

This is a **consistency test**, not a security proof. A rejection means the
session is inconsistent with the calibrated honest model; it does not attribute
a cause.

---

## 7.7 Finite-size treatment

Two methods are reported:

- **Exact Clopper-Pearson binomial interval** (reference). Inverts the binomial
tail exactly. Coverage is at least the nominal confidence for every sample size.
- **Hoeffding concentration inequality** (cross-check). Valid under weaker
assumptions (no identical-distribution requirement) but uniformly looser.

Neither is a cryptographic security parameter. Every bound record carries
`is_cryptographic_security_bound=False` and constructing one with `True` raises.

For a measured count `K` over `N` valid trials:

- two-sided confidence interval: `[Beta^{-1}(alpha/2; K, N-K+1), Beta^{-1}(1-alpha/2; K+1, N-K)]`
- one-sided upper bound: `Beta^{-1}(1-alpha; K+1, N-K)`
- threshold exceedance margin: `(K - k_crit(N)) / N`
- honest prediction interval for a future count: the `alpha/2` and `1-alpha/2`
  quantiles of `Binomial(N, p_upper)`

---

## 7.8 Threat-by-threat coverage

The threat-observability matrix (`backend/security/observability.py`) records
what each attack looks like to each layer:

| Threat | Quantum disturbance | Protocol anomaly | Auth evidence | Replay evidence | Detector-visible | Classical control | Evaluated | Covered |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| forgery | no | yes | no | no | no | yes | yes | yes |
| impersonation | no | no | yes | no | no | yes | yes | yes |
| unauthorized_verification | no | no | yes | no | no | yes | yes | yes |
| replay | no | no | no | yes | no | yes | yes | yes |
| intercept_resend | yes | no | no | no | yes | no | yes | yes |
| channel_tampering | yes | no | no | no | yes | no | yes | yes |

**Critical distinction:** the four protocol-layer attacks produce **zero**
quantum-channel disturbance. The mismatch-rate detector sees none of them. Their
protection requires classical protocol controls (binding verification,
authorization bookkeeping, replay detection). The two channel attacks produce
observable quantum disturbance and are detected by the mismatch-rate test at the
measured rates in `benchmarks/m5-reference.json`.

---

## 7.9 Classical-vs-quantum controls

The prototype deliberately separates classical controls from quantum evidence:

- **Quantum layer** — detects channel disturbance (intercept_resend,
channel_tampering). It cannot detect protocol-layer attacks because they do not
modify the quantum states.
- **Protocol layer** — detects structural anomalies (forgery via binding
mismatch, replay via nonce reuse). It operates deterministically and needs no
calibration.
- **Authorization layer** — detects identity violations (impersonation,
unauthorized verification). It is a membership test, not a statistical inference.

Conflating these layers would be a category error: "the quantum detector found
nothing" does not mean "the session is secure", and "the protocol layer
accepted" does not mean "the channel was undisturbed".

---

## 7.10 Composition boundary

The composition assessment (`backend/security/composition.py`) evaluates each
milestone as a component and identifies its unresolved dependencies. The summary
is:

- **M1** (quantum core) — verified in simulation, no hardware validation.
- **M2** (protocol) — structural integrity, no unforgeability (no secret key).
- **M3** (noise/attacks) — modelled attacks produce observable effects in
simulation; adaptive attacks not covered.
- **M4** (detection) — evidence producer, not a decision mechanism.
- **M5** (calibration) — calibrated rule with measured empirical rates; no
formal security proof.
- **M6** (analysis) — documents what is known and what is not proven.

**No formal composition theorem is claimed.** The assessment explicitly states
that the components do not automatically compose into a secure QDS system, and
that a formal composition proof is absent.

---

## 7.11 What is experimentally supported

The following claims are supported by the committed benchmark
`benchmarks/m5-reference.json` and the test suite:

- Under the calibrated honest depolarizing channel at eta=0.02, with N=500,
  sampled mode and one shot per state, the empirical false-rejection rate was
  0.0% over 120 calibration sessions.
- Under the same configuration, the modelled intercept_resend attack at
  fraction=0.20 was rejected in 12/12 trials (detection rate 100.0%, FAR 0.0%).
- Under the same configuration, the modelled channel_tampering attack at
  fraction=0.20 was rejected in 12/12 trials (detection rate 100.0%, FAR 0.0%).
- The four protocol-layer attacks (forgery, impersonation, unauthorized
  verification, replay) were accepted in 12/12 trials each (FAR 100.0%), because
  they produce no quantum-channel disturbance.
- The noise robustness grid shows detection of channel attacks at all four noise
  levels (none, low, medium, high), but that figure is only meaningful where the
  operating point is usable. At `high` noise (depolarizing eta=0.10) the honest
  false-rejection rate is **1.0**, so every honest session is rejected as well;
  the detection rate of 1.0 at that level is vacuous and the operating point is
  unusable there. Honest FRR is 0.0 at `none`, `low` and `medium`, so the
  detector is usable at those three levels only.
- The discrimination experiment compared each channel attack against honest
  noise. For intercept_resend the two populations **were** matched (comparable
  marginal mismatch rates) and the comparison reports them as **not**
  distinguishable on `basis_mismatch_dispersion` under the current observable
  model. For channel_tampering the two populations were **not** matched — the
  committed record states that their marginal mismatch rates are not comparable,
  so that comparison does not isolate structural information — and a separation
  on `basis_mismatch_dispersion` is recorded there.

These are **empirical measurements on modelled attacks**, not cryptographic
security bounds.

---

## 7.12 What remains unproven

The following claims are **not** established by this prototype:

- **No formal information-theoretic security proof.** The simulator reproduces a
  model; it does not prove a property of the world.
- **No formal forgery bound.** FAR is an empirical acceptance rate on a
  specific dataset, not a probability that an adversary forges.
- **No universal attack detection.** Only six attack families were modelled.
  Nothing was shown about attacks outside this set.
- **No hardware or device validation.** All results are from simulation.
- **No deterministic finite-shot acceptance.** The sampled measurement mode is
  probabilistic; acceptance is a finite-shot outcome, not a deterministic
  property.
- **No identity proof from quantum measurement alone.** Quantum measurement
  verifies consistency with a model, not the identity of the sender.
- **No automatic security composition theorem.** The components were evaluated
  individually; no proof was given that they compose into a secure system.
- **No side-channel analysis.** Timing, power, and implementation attacks are
  outside the scope.
- **No adaptive attack analysis.** All modelled attacks are fixed before the run.

---

## 7.13 Required future work for a formal security proof

A formal security proof would require at minimum:

1. **A complete QDS security definition** — unforgeability, non-repudiation and
transferability, with composability if the scheme is to be used in a larger
protocol.
2. **A secret key or equivalent binding mechanism** — the reference protocol has
no secret key, so it provides integrity but not unforgeability.
3. **A formal channel model** — the current model is a product channel with
stationary noise; a formal proof would need a channel model that captures all
relevant adversarial behaviour.
4. **Adaptive attack analysis** — the proof would need to bound an adversary's
advantage when the attack can adapt to the verifier's public parameters.
5. **Hardware validation** — a simulator cannot establish properties of physical
hardware; a formal proof would need to account for device imperfections.
6. **A composition theorem** — proving that the independently evaluated
components (quantum core, protocol, detection, calibration) compose securely
when combined.
7. **No finite-size security parameter is derived here** — deriving one would
require a relationship between sample size, error budget and adversarial
advantage that holds for all admissible attacks, not just the six modelled ones.

None of this work is claimed to have been done at this milestone.

---

## References

The primary citations used in this argument are:

- **[R11] Hoeffding (1963)** — concentration inequalities.
- **[R12] Clopper & Pearson (1934)** — exact binomial confidence intervals.
- **[R13] Holm (1979)** — multiple-comparison correction (implemented, unused).

No security claim is transferred from the QDS literature ([R2]–[R4]/[R10]) or
the teleportation literature ([R1]). See `docs/research/references.md` for the
full list and the "claims that are not transferred" note.
