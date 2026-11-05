# M6 — Security Analysis: Finite-Size Threat Analysis and Security Boundaries

## 1. What M6 adds

Milestone 5 built statistical calibration, finite-sample analysis and empirical
evaluation. Milestone 6 adds the **interpretation and security-boundary layer**
on top of those numbers:

- **Threat-specific observability matrix** — what each of the six modelled
  attacks looks like to each layer (quantum, protocol, authorization, replay).
- **Conservative statistical separation** — the gap between an observed mismatch
  rate and the calibrated honest upper bound, with an explicit statement that
  this is evidence of inconsistency, not attribution.
- **Composition assessment** — a component-by-component evaluation that
  explicitly identifies unresolved dependencies and denies any formal
  composition theorem.
- **Structured security argument** — a 13-section document that states what is
  supported, what is unproven, and what future work would be needed for a formal
  security proof.

M6 does **not** add new quantum circuits, new attack families, or new
statistical methods. It interprets what M1–M5 built.

## 2. Threat-observability matrix

The matrix is in `backend/security/observability.py`. It has two sources:

1. **Structural code evidence.** Each attack module documents what it modifies.
   The four protocol-layer attacks do not touch `received_states`, so they
   produce no quantum disturbance.
2. **Measured M5 benchmark evidence.** `benchmarks/m5-reference.json` records
   the decision outcome for each attack under the calibrated threshold.

The headline result:

- **Quantum-visible:** intercept_resend and channel_tampering (detection rate
  100%, FAR 0%).
- **Classical-only:** forgery, impersonation, unauthorized_verification and
  replay (detection rate 0%, FAR 100%). Their protection requires binding
  checks, authorization bookkeeping and replay detection, not the mismatch-rate
  detector.

This is not a defect to be hidden; it is the honest classification of the
prototype's coverage.

## 3. Statistical separation and conservative gap

`backend/security/threat_bounds.py` provides:

- `threshold_exceedance(n_mismatch, n_valid, threshold)` — deterministic margin
  above or below the critical count.
- `statistical_separation(observed_rate, honest_upper)` — conservative gap
  `observed - upper`, with a conclusion that distinguishes "exceeds" from
  "within" from "at boundary".
- `honest_prediction(threshold)` — a prediction interval for a future honest
  observation, explicitly labelled as such (not a confidence interval).
- `exceedance_probability(n_mismatch, n_valid, p_upper)` — the p-value under
  the conservative honest model, explicitly not a cryptographic parameter.

None of these quantities is labelled a security bound. Every record and every
docstring states the distinction.

## 4. Composition assessment

`backend/security/composition.py` evaluates the six milestones as components:

| Component | Property evaluated | Security conclusion |
| --- | --- | --- |
| M1 — Quantum core | circuit correctness in simulation | no hardware validation; no security claim |
| M2 — Protocol | structural integrity and binding | no unforgeability (no secret key) |
| M3 — Noise/attacks | observable effects of modelled attacks | adaptive attacks not covered |
| M4 — Detection | evidence production without labels | not a decision mechanism |
| M5 — Calibration | calibrated rule with measured rates | no formal security proof |
| M6 — Analysis | assumption register and interpretation | no composition theorem claimed |

The assessment's central negative claim: **no formal composition theorem is
present**. The components do not automatically compose into a secure system, and
the document says so explicitly.

## 5. Assumption register (extended)

`backend/security/assumptions.py` was extended with two M6 assumptions:

- `protocol_binding_is_public_and_deterministic` — the binding and
  canonicalisation are public functions, documenting that the protocol provides
  integrity but not secrecy.
- `classical_identity_is_bookkeeping_not_quantum` — identity checks are
  deterministic membership tests, not quantum measurements, preventing the
  conflation of authorization with quantum evidence.

The register now covers all nine categories requested in the M6 brief.

## 6. What M6 does not claim

The following are explicitly **not** claimed:

- The prototype does not establish information-theoretic security.
- The prototype does not derive a formal forgery probability bound.
- The prototype does not detect all attacks: only six families were modelled.
- The prototype does not establish composable security.
- The prototype does not establish unconditional security.
- The prototype does not establish device-independent security.
- The prototype does not establish hardware security.
- Acceptance is not deterministic finite-shot acceptance.
- Quantum measurement alone does not provide an identity proof.

The forbidden-claim register in `backend/security/interpretation.py` lists the
claims that must not be made, and `check_statement` flags occurrences of them.
That check is a blunt substring guard-rail rather than a completeness guarantee:
the items above are what this milestone states it does not claim, and not every
one of them is pattern-matched by the checker.

## 7. Documentation

- `docs/security/SECURITY_ARGUMENT.md` — the full 13-section structured
  argument (system scope, threat model, assumptions, evidence, decision rule,
  finite-size treatment, threat coverage, classical-vs-quantum controls,
  composition boundary, what is supported, what is unproven, required future
  work).
- `docs/security/statistical-calibration.md` — M5 calibration methodology.
- `docs/security/evaluation-methodology.md` — M5 evaluation methodology.
- `docs/research/references.md` — verified primary citations, with a section on
  claims that are not transferred.

## 8. Tests

M6 added four test modules in `tests/security/`:

- `test_threat_bounds.py` — exceedance, separation, prediction, exceedance
  probability, structural guards.
- `test_observability.py` — matrix structure, classification consistency,
  measured evidence alignment, serialization.
- `test_composition.py` — component coverage, unresolved dependencies, absence
  of formal-theorem claims, rendering.
- `test_security_acceptance.py` — 18 acceptance criteria mapping the M6 brief
  to explicit tests.

All tests pass. The full security suite (`tests/security/`) reports 254 tests.

## 9. Reproducibility

All M6 results are derived from:

- committed code (`backend/security/`);
- committed M5 benchmark (`benchmarks/m5-reference.json`);
- deterministic seeded functions with no randomness of their own.

No new benchmark was run for M6. The observability matrix quotes the committed
M5 numbers directly.

## 10. Limitations

1. The observability matrix covers only the six modelled attacks.
2. The composition assessment is interpretive, not machine-proven.
3. The statistical separation is conservative but conditional on the
   calibration assumptions.
4. No hardware validation was performed.
5. Adaptive attacks are outside the scope.
6. The security argument is conditional on the assumption register; if an
   assumption is violated, the argument does not apply.
7. The noise robustness grid has one level (`high`, depolarizing eta=0.10) at
   which the honest false-rejection rate is 1.0. The detector rejects every
   honest session there, so its detection rate at that level is not usable
   evidence and that operating point is unusable. The usable levels are `none`,
   `low` and `medium`.
