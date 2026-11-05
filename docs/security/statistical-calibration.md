# Statistical Calibration and Finite-Sample Analysis

Milestone 5 — how the detection threshold is derived, from honest data only, and
what the resulting numbers do and do not mean.

**Calibration consumes honest sessions and nothing else. No attack data enters a
baseline, a confidence interval, a threshold or an operating point.**

---

## 1. Purpose and scope

This document describes `backend.calibration` and `backend.security`, the
Milestone 5 calibration and finite-sample analysis layers.

The layers answer one question: *what does an honest session look like, and how
much mismatch can an honest channel produce before a verifier should stop
believing that the session is honest?*

In scope:

* one primary quantum verification statistic, selected and justified;
* an explicit null and alternative hypothesis;
* an honest-only calibration dataset with a recorded role;
* exact finite-sample confidence intervals with a verified primary citation;
* one reference threshold methodology, traceable to its inputs;
* an explicit multiple-comparison policy;
* exactly one reference operating point.

Out of scope, deliberately, and named here so it is not mistaken for an
oversight:

* deciding what counts as an attack (that is Milestone 3);
* measuring how the rule performs on attacks (that is the evaluation layer, and
  it is documented in `docs/security/evaluation-methodology.md`);
* any formal cryptographic forgery bound. None is derived at this milestone.

---

## 2. The four quantities that must not be conflated

Everything below is one of four different objects. They live in different layers,
they answer different questions, and a number from one must never be quoted as a
number from another.

| quantity | what it is | where it lives |
| --- | --- | --- |
| **empirical statistic** | an observed ratio, e.g. `N_mismatch / N_valid` on one session | `backend.calibration.baseline`, `backend.evaluation.metrics` |
| **confidence interval** | a statement about an unknown parameter, given a sample | `backend.calibration.confidence` |
| **classification threshold** | a decision rule derived from the interval and the sample size | `backend.calibration.thresholds` |
| **formal cryptographic security bound** | a proof-level bound on an adversary's advantage | **not produced at this milestone** |

In the report payload these four are recorded under the names
`confidence_interval`, `classification_threshold`,
`empirical_attack_acceptance_rate` and `formal_cryptographic_security_bound`, so
a machine-readable record of the distinction travels with every report rather
than living only in prose.

The fourth row is not a placeholder. The simulator does not establish a new
information-theoretic security proof, and no forgery bound is derived here.
Deriving one would be Milestone 6 work, and only if it is justified there.

A fifth object appears in the evaluation layer — the **empirical attack
acceptance rate** — and it is likewise a measurement on a specific dataset under
a specific modelled attack, not a probability an adversary is bounded by. See
`docs/security/evaluation-methodology.md`.

---

## 3. The primary quantum verification statistic

### 3.1 Selection

The reference implementation tests exactly one statistic:

```
D_m  =  N_mismatch / N_valid
```

recorded as `STATISTIC_MISMATCH_RATE = "mismatch_rate"` in
`backend/calibration/models.py`. `N_valid` is the number of usable verification
states in the session and `N_mismatch` the number whose measured outcome
disagreed with the outcome the protocol expected for the state that was prepared.

### 3.2 Why this statistic

| criterion | how `D_m` satisfies it |
| --- | --- |
| **verifier observability** | it is computed from the verifier's own measurement outcomes and the protocol's own expectation; it needs no secret, no oracle and no label |
| **physical meaning** | it is the per-state rate at which the received state fails to be the state that was sent — exactly the quantity a channel disturbance or an interception raises |
| **statistical behaviour** | each state contributes one Bernoulli indicator, so `N_mismatch` is Binomial with a per-state probability that is a property of the channel; this is what makes an exact finite-sample statement available |
| **finite-sample tractability** | it has a closed-form exact interval and a distribution-free concentration bound, both with primary citations (Section 5) |
| **interpretability** | "one state in a hundred came back wrong" is a sentence an operator can act on |
| **honest-noise robustness** | it is graded in the channel strength: the honest mismatch probability rises smoothly with noise instead of saturating, provided the measurement configuration is the one described in Section 4.3 |

### 3.3 Alternatives considered

The quantities below are all exposed by the Milestone 4 detector. Each is
recorded under a fixed name so the diagnostic set is inspectable:

* **Reconstruction fidelity** `F`, recorded as `reconstruction_fidelity` and
  `minimum_fidelity`. Physically meaningful and reported, but it is a continuous
  quantity with no exact finite-sample distribution, and it is monotone in `D_m`
  for the reference channel, so it would add no discriminating power to the
  decision while adding an approximation. Retained as a diagnostic.
* **Verification-state disturbance rate**, recorded as
  `verification_state_disturbance_rate`. Distinguishes a disturbed state from a
  matched one without reference to the measurement outcome. It is a *superset*
  signal: it fires on honest noise as readily as on an attack, and in the
  reference configuration it saturates at 1.0 for any nonzero noise (Section
  4.3). Retained as a diagnostic, and used as the structural descriptor in the
  discrimination experiment.
* **Per-basis mismatch rates**, recorded as `per_basis_mismatch_rates` and
  `per_basis_disturbance_rates`. Three separate tests would multiply the
  comparison count and require a multiple-comparison correction for no measured
  benefit. Retained as diagnostics.
* **Measurement-level observables**, recorded as
  `projective_match_probability`, `measurement_counts_by_basis` and
  `basis_distribution`. These describe *how* the measurement was made rather than
  whether the session is honest, and they are the quantities that expose the
  measurement-mode degeneracy of Section 4.3. Retained as diagnostics, and used
  as evidence when the measurement configuration is described.
* **Transcript, replay and authorization checks**, recorded as
  `transcript_validity`, `transcript_hash_validity`, `session_consistency`,
  `nonce_freshness_state`, `state_count_consistency`,
  `signer_authorization_validity`, `verifier_authorization_validity` and
  `cross_verifier_disagreement`. These are classical protocol controls, not
  quantum evidence. They are reported separately and are not part of the
  statistical decision (Section 11).

All alternatives are retained as **diagnostic evidence**: reported, never
adjudicated. `DIAGNOSTIC_METRICS` in `backend/calibration/multiple_testing.py`
is the authoritative list of all sixteen.

---

## 4. Hypotheses and the null model

### 4.1 The hypotheses

```
H0 (honest)      the session's per-state mismatch probability is consistent with
                 the calibrated honest channel
H1 (not honest)  the session's per-state mismatch probability exceeds what the
                 calibrated honest channel can produce
```

The test is **one-sided**, because the decision it supports is one-directional:
"is the mismatch rate *too high*?" A rate that is unusually *low* is not
evidence of an attack and is not rejected.

**`H0` is not "the mismatch rate is zero".** An honest channel is noisy, and the
null has to permit the noise the channel actually produces. If `H0` were "zero
mismatch", every honest session on a real channel would be rejected, and the
false-rejection rate would be 100%. The null is therefore *the calibrated honest
channel*, and it is measured rather than assumed (Section 5).

### 4.2 What the binomial assumption requires

The exact interval of Section 5.1 assumes that the mismatch indicators are
independent and share one probability. Neither is a theorem about the system;
both are properties of the model, and the project records which ones hold:

* **independent** — the states in a session are prepared and measured
  independently, and the channel acts on each state separately. This holds by
  construction of the reference model.
* **identically distributed** — the per-state mismatch probability must be the
  same for all six signature states. This holds **exactly** for the depolarizing
  channel and for no noise at all, because depolarizing noise treats every state
  alike. It holds only **approximately** for the bit-flip, phase-flip and
  bit-phase-flip channels, whose disturbance depends on the state and the
  measurement basis.
* Where it is only approximate, the result is a **Poisson-binomial** rather than
  a binomial, and the exact interval is an approximation. The project records
  this as an `APPROXIMATE` assumption with a stated consequence rather than
  silently using the exact formula; see
  `backend/security/assumptions.py` and `reference_assumptions()`.

Hoeffding's bound (Section 5.2) requires only independence, not identical
distribution, which is why it is reported alongside the exact interval even
though it is looser.

### 4.3 The measurement configuration, and why it is stated

The measurement mode decides whether the honest null is *graded* or *degenerate*,
so it is a recorded part of the calibration rather than an implementation detail.

| configuration | honest mismatch rate | why |
| --- | --- | --- |
| `projective-analytic` | jumps 0 → 1 | "matched" means the received qubit *is* the expected eigenstate, so any nonzero disturbance makes every state mismatch. There is no interior for a finite-sample null to describe. |
| `sampled`, large `shot_count` | ≈ 0 | the majority vote over many shots of one qubit swamps small disturbance |
| **`sampled`, `shot_count = 1`** | `1 - p_match` | one measurement per state, which is what a verifier physically performs. This is the reference configuration. |

This was established **by measurement, not assumption**: the three
configurations were run over a noise sweep and their mismatch rates compared.
The reference configuration is `sampled` with `shot_count = 1` on a depolarizing
channel at `eta = 0.02`.

---

## 5. Finite-sample methods

Two methods are implemented. One sets the threshold; the other is reported as a
cross-check.

### 5.1 Exact Clopper-Pearson binomial interval — the reference method

For `k` mismatches in `n` usable observations, at confidence `c` with
`alpha = 1 - c`, the exact interval inverts the binomial tail:

```
two-sided lower   L = 0                                          if k = 0
                  L = Beta^{-1}(alpha/2;     k,     n - k + 1)    otherwise
two-sided upper   U = 1                                          if k = n
                  U = Beta^{-1}(1 - alpha/2; k + 1, n - k)        otherwise

one-sided upper   U = 1                                          if k = n
                  U = Beta^{-1}(1 - alpha;   k + 1, n - k)        otherwise
one-sided lower   L = 0                                          if k = 0
                  L = Beta^{-1}(alpha;       k,     n - k + 1)    otherwise
```

`Beta^{-1}` is the inverse regularised incomplete beta function, evaluated with
`scipy.stats.beta.ppf`. Coverage is **at least** the nominal confidence for every
sample size, including very small ones: Clopper-Pearson is conservative and never
anti-conservative, which is the property that matters here, because an
*under*-estimated upper bound is a threshold that rejects honest sessions.

**Primary citation.**

> C. J. Clopper and E. S. Pearson, "The Use of Confidence or Fiducial Limits
> Illustrated in the Case of the Binomial", *Biometrika* **26**(4), 404–413
> (1934). DOI: 10.1093/biomet/26.4.404. JSTOR: 2331986.

**Assumptions.** Each usable state contributes one Bernoulli mismatch indicator;
the indicators are independent; they share a common probability within the pooled
sample. The third is exact for the reference depolarizing channel and
approximate for the flip channels (Section 4.2).

### 5.2 Hoeffding's concentration inequality — a cross-check, not the method

```
one-sided   p  <=  p_hat + sqrt( ln(1/alpha) / (2n) )
two-sided   |p - p_hat|  <=  sqrt( ln(2/alpha) / (2n) )
```

**Primary citation.**

> W. Hoeffding, "Probability Inequalities for Sums of Bounded Random Variables",
> *Journal of the American Statistical Association* **58**(301), 13–30 (1963).
> DOI: 10.1080/01621459.1963.10500830. JSTOR: 2282952.

**Assumptions.** The indicators are independent; each is bounded in `[0, 1]`,
which is automatic for a `0`/`1` variable; identical distributions are **not**
required, so the bound also covers the Poisson-binomial case.

**Why it does not set the threshold.** Hoeffding is valid under weaker
assumptions but is uniformly looser than the exact interval. Setting the
threshold from it would cost false rejections for no benefit. It is reported so
that a reader can see that the exact interval is the tighter of the two and by
how much.

### 5.3 What these bounds are not

Neither is a cryptographic security parameter, and neither is a forgery bound.
The sample size `n` is the number of usable verification states, which is an
**experimental design value**: it can be raised by the operator, it is public,
and it is not a secret. These bounds are not a cryptographic security parameter;
a property of an adversary's power is a different object. Every bound record
carries `is_cryptographic_security_bound = False`, and constructing one with
`True` raises.

For reference, the sample size that a Hoeffding radius of `0.005` at 95%
two-sided confidence would require is

```
n = ceil( ln(2 / 0.05) / (2 * 0.005^2) ) = 73778
```

(one-sided: `59915`). That is a statement about how many observations a
distribution-free `±0.005` estimate costs — not a security parameter.

---

## 6. The reference threshold methodology

`REFERENCE_THRESHOLD_METHOD = "honest-null-quantile-with-upper-confidence-bound"`.
In full:

1. From an honest-only calibration dataset, form the pooled per-state mismatch
   count `K` out of `T` usable observations.
2. Bound the honest per-state mismatch probability from above with the exact
   one-sided Clopper-Pearson bound at confidence `1 - alpha_cal`:

   ```
   p_upper = Beta^{-1}(1 - alpha_cal; K + 1, T - K)
   ```

3. For a session of `N` usable observations, take the `1 - alpha_eval` quantile
   of the honest null evaluated at that bound:

   ```
   k_crit(N) = min { k : P[ Binomial(N, p_upper) <= k ] >= 1 - alpha_eval }
   theta(N)  = k_crit(N) / N
   ```

4. Reject `H0` when

   ```
   N_mismatch > k_crit(N)
   ```

`k_crit` itself is still accepted; the test is strict.

### 6.1 Why this construction

* **Not "5% mismatch means attack".** No threshold is written into the detector.
  The threshold is an output of a stated procedure applied to stated data, and
  `ThresholdResult` records the procedure, the data, the error budget and the
  resulting count.
* **The error budget is split, not doubled.** Two sources of randomness enter:
  the finite calibration sample fixes `p_upper`, and the session under test is
  itself a finite sample. Spending `alpha` on each would bound the total
  false-rejection probability only by roughly `2 * alpha`. The configuration
  splits the budget instead, `alpha_cal + alpha_eval = alpha`, evenly by default.
* **It is conservative, and the project says so.** `p_upper` is already an upper
  bound and the quantile is taken at that bound, so the realised false-rejection
  rate is expected to fall *below* `alpha`. That is measured, not assumed: the
  operating point records the honest rejection rate it actually observed.

### 6.2 Alternatives considered

| alternative | why it is not the reference method |
| --- | --- |
| honest-distribution quantile at the point estimate | uses `pooled_rate` instead of an upper bound; less conservative, and its level is only *nominal* because the point estimate is itself random. Available, and not used. |
| Neyman-Pearson operating point | requires a specified alternative and its likelihood ratio. The project has no defensible single alternative — attacks differ in kind, and choosing one would silently privilege it. Deferred. |
| explicit target-FAR calibration | requires malicious data to calibrate against, which the calibration/evaluation split forbids. This is what the *evaluation* layer measures afterwards, not what calibration optimises. |

---

## 7. Sample size is load-bearing

`k_crit(N)` is a quantile of a distribution whose mean grows like `N` while its
spread grows like `sqrt(N)`. Therefore

```
theta(N) = k_crit(N) / N  ->  p_upper   as N grows
```

A threshold derived at `N = 100` is **not** valid at `N = 10_000`.
`ThresholdResult.rejects` refuses to apply a threshold at a size it was not
derived for, rather than silently mis-sizing the test, and
`derive_threshold_table` derives one threshold per size from a single
calibration dataset so the whole declared design range is covered.

The design sample sizes are `100, 250, 500, 1000, 2500, 5000, 10000`. They are
**design values, not constants in the detector logic**. Note that a threshold is
a binomial quantile of the calibrated null and needs no simulation, so it is
exact at *every* design size — including `5000` and `10000`, which are above the
reference protocol's maximum signature length of `4096` states and therefore
cannot be *evaluated*. The benchmark reports those two as declared-but-unsimulated
rather than pretending a run happened at them, and it does **not** widen the
protocol bound to make a benchmark reachable. See
`backend/evaluation/benchmark.py::partition_sample_sizes`.

---

## 8. The honest null as measured

The calibration dataset is honest-only and carries an explicit role:

| field | meaning |
| --- | --- |
| `dataset_role` | `CALIBRATION`; the model refuses any other role |
| protocol version | which protocol the session ran |
| noise configuration | noise type and strength the honest channel used |
| `state_count` | usable observations per session |
| statistic | which statistic the observation refers to |
| random seed | the seed that produced the session |
| experiment identifier | which experiment the session belongs to |
| timestamp | when it was recorded |

`CalibrationObservation` holds `n_valid`, `n_mismatch` and the derived rate, and
**has no field that could carry an attack label, an attack type or a
ground-truth flag**. The honest-only property is therefore structural rather than
a matter of discipline: the layer has nowhere to put a label. This is enforced
statically — `tests/calibration/test_architecture.py` parses every module in the
package and fails if any of them imports `backend.attacks` or
`backend.simulation`, or names a ground-truth identifier.

`estimate_baseline` pools the sessions, computes the pooled rate, the exact
interval and a homogeneity diagnostic that reports whether the per-session rates
are consistent with one common probability. Where they are not, the pooled
interval is an approximation and the diagnostic says so.

---

## 9. The reference operating point

Exactly one operating point is defined: `m5-reference`, built by
`build_reference_operating_point`. It is **specified, not optimised** — no
objective was maximised, so no claim of optimality is made.

It records, and is traceable to:

| recorded | value / source |
| --- | --- |
| statistic | `mismatch_rate` |
| threshold methodology | `honest-null-quantile-with-upper-confidence-bound` |
| error budget | `alpha = 0.05`, split evenly: `alpha_cal = alpha_eval = 0.025` |
| sample size | the calibration dataset's session size; overridable, and the threshold is then *re-derived* for that size |
| calibration conditions | noise type, noise strength, measurement mode, `shot_count` |
| calibration provenance | session count, total usable observations, total mismatches, pooled rate, dataset role |
| calibration fingerprint | a digest of the calibration configuration |
| resulting threshold | `p_upper`, `k_crit`, `theta` |
| observed calibration FRR | the honest rejection rate on the calibration data itself, **labelled as a fitted quantity** rather than an independent estimate |
| seed range | the seeds the calibration used |

`OperatingPoint.decide` is the whole of Layer A of the decision. Its recorded
`decision_basis` states that one primary statistical test was performed and that
no other statistic enters the decision.

---

## 10. The error budget and its direction

`alpha` is the **permitted false-rejection rate**, so the direction is:

```
smaller alpha  ->  larger p_upper quantile level  ->  larger k_crit  ->  fewer rejections
```

This is the opposite of the intuition that "a stricter test rejects more". A
stricter test in the sense of "fewer false rejections" is *more* permissive
towards the observed data; it rejects only larger mismatch counts. The
implemented tests pin this direction explicitly rather than leaving it to be
rediscovered.

---

## 11. The multiple-comparison policy

**Running several independent tests at `alpha = 0.05` and reporting the result as
a 5% error rate inflates the family-wise error rate.** For `k` independent tests
at level `alpha` the family-wise error rate is

```
FWER = 1 - (1 - alpha)^k
```

which is `0.4013` at `k = 10, alpha = 0.05` — eight times the nominal level.

The reference policy is therefore `SINGLE_PRIMARY_WITH_DIAGNOSTICS`:

* **one primary statistical test** — `mismatch_rate_against_calibrated_threshold`;
* **everything else is diagnostic evidence** — reported, never adjudicated.

There is no family to correct for, so the policy declares no family-wise level
and no correction, and `MultipleComparisonPolicy.validate()` raises if one is
supplied for it. `describe_diagnostics` marks every diagnostic with
`part_of_decision: false`, and the policy fails at construction if the primary
test is also listed as a diagnostic.

A `CORRECTED_FAMILY` policy exists, with Bonferroni and Holm–Bonferroni
corrections implemented and tested, so the alternative can be reasoned about. It
is **not used** by the reference operating point.

Holm's procedure is cited in `docs/research/references.md` [R13].

---

## 12. The security interpretation layer

`backend.security.interpretation` exists to stop the numbers being quoted as
something they are not. It provides:

* `check_statement` / `check_statements` — classify a sentence as allowed or
  forbidden, with reasons;
* `render_measurement_statement` — assemble a statement that carries every
  required qualifier;
* `build_interpretation_result` — the four-quantity distinction as a payload.

**Allowed**, because every number is attributed to a condition, a sample size and
a dataset:

> At `N = 5000` under calibrated honest noise `eta = 0.02`, empirical FRR was
> 0.8%, while modelled intercept-resend detection at `gamma = 0.20` was 94.1%.

**Forbidden**, and detected as forbidden:

* Never write "This proves the protocol is information-theoretically secure."
* Never write "This is a formal forgery bound."
* Never write "The framework detects all quantum attacks."
* Never write "The detector is secure."
* Never write "The simulator establishes security."
* Never write "FAR is the forgery probability."
* Never write "The results generalise to other conditions."

The checker is **negation-aware**: a sentence that *discloses* a limitation —
"no formal forgery bound is derived" — is allowed, because it is the opposite of
an overclaim. This matters, because the report itself states its own limitations
and must pass its own checker. The check is pinned by a test that runs the
report through the checker, so the guard cannot silently stop working.

Banned terminology is never excused by negation: the term "decoy-state" is not
used anywhere in this project, and the checker flags it in any context.

---

## 13. What calibration refuses to do

* It refuses a non-`CALIBRATION` dataset role, in the config, in the observation
  and in the dataset builder.
* It refuses to derive a threshold from a calibration dataset with no usable
  observations — a threshold cannot be invented from an empty sample.
* It refuses to apply a threshold at a sample size it was not derived for.
* It refuses a threshold methodology other than the reference one, naming the
  alternatives as considered and not used.
* It refuses a `CORRECTED_FAMILY` policy without a named correction, and a
  single-test policy that claims a family-wise level.
* It never imports `backend.attacks`, `backend.simulation` or
  `backend.evaluation`.

---

## 14. Limitations

* The construction is a reference prototype. The organiser requirement specifies
  primitives and goals, not a complete formal QDS protocol.
* The honest null is a *model*, calibrated on a modelled channel. It is not a
  claim about any physical device.
* The binomial assumption is exact only for the depolarizing channel. For the
  flip channels the exact interval is an approximation, and the assumption
  register records that as `APPROXIMATE` with its consequence.
* `alpha` is a *permitted* false-rejection rate for the specified procedure. The
  realised rate is expected to be lower and is measured, not assumed.
* Confidence intervals, thresholds and empirical rates are not security bounds.
  No formal forgery bound is derived at this milestone.
* The calibration/evaluation split prevents leakage within the reference
  experiment. It does not make the reference experiment a substitute for an
  independent evaluation on real hardware.
* No machine learning is used anywhere: no learned threshold, no trained
  classifier, no anomaly model.

---

## 15. Where the numbers are

No number in this document is quoted from a stored result. The measured
calibration and evaluation figures come from a reproducible run of
`benchmarks/run_reference_benchmark.py`, which writes
`benchmarks/m5-reference.json` and `benchmarks/m5-reference.md`. That payload
records the profile, the protocol version, the Python and platform versions, the
seed blocks, the number of scenarios run and the measured runtime, so a reader
can tell what produced the numbers and re-run it.

The methodology in this document is what the code implements; the numbers are
what the code measured.
