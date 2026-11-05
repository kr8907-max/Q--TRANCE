# Evaluation Methodology

Milestone 5 — how the calibrated rule is measured against known attacks, and
what those measurements do and do not establish.

**The detector never sees a label. The evaluation layer is the only place ground
truth appears, and it appears only after the decision has already been made.**

---

## 1. Purpose and scope

This document describes `backend.evaluation`, the Milestone 5 measurement layer.

It answers one question: *given that the rule is fixed and was calibrated on
honest data only, what does it actually do on honest sessions and on known
attacks?*

In scope:

* a two-layer decision, with the label read only in the second layer;
* an explicit calibration / validation / final-evaluation split;
* explicit FAR and FRR definitions, and a fixed confusion-matrix convention;
* attack evaluation over six modelled attacks;
* a measured noise-robustness grid;
* the central discrimination experiment;
* eight reference curves, every point from a run;
* a benchmark that is reproducible by a documented command.

Out of scope, deliberately:

* attributing a cause to a session (the detector cannot, and this layer does not
  try to);
* no formal forgery bound is derived at this milestone.

---

## 2. The two-layer decision

| layer | question | input | module |
| --- | --- | --- | --- |
| **A — verification decision** | is this session statistically consistent with the calibrated honest model? | observable statistics only | `OperatingPoint.decide` (calibration layer) |
| **B — security evaluation** | how often was that answer right, on data with known ground truth? | Layer A's answers **and** ground truth | `backend.evaluation` |

Layer A runs without a label. Layer B compares Layer A's answers against labels.

The ordering is enforced, not merely documented. `decide_observable` takes
exactly two parameters — an operating point and observable statistics — and
`observable_statistics` takes exactly one. A test monkeypatches the decision
function with a spy that records access order and asserts that the decision is
computed **before** ground truth is touched, so a future refactor that reorders
them fails the suite.

---

## 3. Dataset roles and the leakage-prevention split

Every record carries an explicit role, and the model refuses the wrong one for
its purpose.

| role | contents | used for |
| --- | --- | --- |
| `CALIBRATION` | honest sessions only | the baseline, the confidence interval, the threshold, the operating point |
| `VALIDATION` | independent honest sessions plus controlled development attacks | development, robustness and discrimination work |
| `FINAL_EVALUATION` | fresh, independently seeded runs | the reported results |

The separation is structural:

* `CalibrationConfig`, `CalibrationObservation` and `build_calibration_dataset`
  refuse any role other than `CALIBRATION`;
* `EvaluationConfig` refuses the `CALIBRATION` role — an evaluation dataset is
  never a calibration dataset;
* `SeedAllocator` hands out disjoint seed blocks and `assert_disjoint_seeds`
  verifies the result, so no trial can be scored twice or appear on both sides
  of the split;
* the benchmark records every seed block it used in its provenance, so the
  allocation is auditable after the fact.

---

## 4. FAR and FRR

```
FAR  =  malicious trials accepted / malicious trials
FRR  =  honest trials rejected   / honest trials
```

Both are **empirical rates on a specific dataset**. They depend on the modelled
attacks, the modelled channel, the sample size and the error budget, and they do
not transfer to other conditions.

What counts as "malicious" is fixed by the experiment, not by the metric: every
trial the experiment injected an attack into. The modelled attacks are

```
forgery, impersonation, unauthorized_verification, replay,
intercept_resend, channel_tampering
```

Honest trials are never malicious. A trial the experiment left alone is recorded
with attack type `none` and is never counted on the malicious side.

**A FAR is not a forgery probability.** It is the share of malicious trials a
particular rule accepted on a particular dataset. It is reported with that scope
attached, and the report labels it as an empirical acceptance rate wherever it
appears.

---

## 5. The confusion-matrix convention

The positive class is **"the verification decision rejected the session"**. That
single choice fixes every derived metric:

| | actually malicious | actually honest |
| --- | --- | --- |
| **rejected** | `tp` | `fp` |
| **accepted** | `fn` | `tn` |

It follows that

```
FPR = fp / (fp + tn) = FRR        the honest rejection rate
FNR = fn / (fn + tp) = FAR        the malicious acceptance rate
```

**FPR is not FAR.** They are different quantities that happen to be numerically
equal to FRR and FAR respectively under this convention. Naming them correctly
matters, and the definitions string in the report says so explicitly.

Derived metrics:

| metric | definition | status |
| --- | --- | --- |
| `tpr` / `detection_rate` / `recall` | `tp / (tp + fn)` | reported |
| `specificity` / `tnr` | `tn / (tn + fp)` | reported |
| `fpr` | `fp / (fp + tn)` | reported, equals FRR |
| `fnr` | `fn / (fn + tp)` | reported, equals FAR |
| `precision` | `tp / (tp + fp)` | descriptive |
| `f1` | harmonic mean of precision and recall | **descriptive only** |

`f1` is not a cryptographic security metric, and a high `f1` can hide the
absence of any honest evidence: a rule that rejects everything has `recall = 1`
and can still show a respectable `f1` on a malicious-only population. A test
pins that case explicitly.

**An empty denominator yields `None`, never `0.0`.** A detection rate over an
empty malicious population is undefined, not zero, and the code distinguishes
"no trials" from "zero trials succeeded" everywhere.

---

## 6. Attack evaluation

Each modelled attack gets its own population, at a declared intensity, on the
reference channel, with its own seed block. The evaluation asks one question per
attack:

> under the modelled `X` attack, what is the probability that the observable
> detector reaches the defined rejection criterion?

It does **not** assume each attack is identified by a unique quantum statistic,
and it does not attribute a cause. Several attacks may look alike to the
detector; that is a result, not a failure.

The rule the report repeats: the verification decision remains the single
calibrated test on `D_m`; the per-attack numbers are properties of *this* rule
on *this* modelled attack.

---

## 7. Noise robustness

Two things are measured, in this order:

1. **honest channel, increasing noise** — how the false-rejection rate moves as
   the honest channel degrades. A detector that only works on a perfect channel
   is not a detector.
2. **noise plus attack** — whether an attack is still detected when it sits on
   top of a noisy honest channel. This is the case that matters, because a real
   channel is never noiseless.

The grid is declared, not hand-picked, and no level is chosen after seeing the
numbers:

| level | depolarizing strength |
| --- | --- |
| `none` | 0.0 |
| `low` | 0.005 |
| `medium` | 0.02 (the reference channel) |
| `high` | 0.10 |

A zero level is mandatory: without it there is no reference point, and a rise in
the false-rejection rate could not be attributed to noise at all.

Nothing here assumes detection degrades gracefully. If it collapses at `high`
noise, that is what the result says. The honest rate and the detection rate live
in separate mappings keyed by level, and the matrices are namespaced
`honest:<level>` and `<level>:<attack>` so an honest matrix can never be
confused with, or silently overwrite, a malicious one at the same level.

---

## 8. The central discrimination experiment

The question the milestone exists to answer honestly:

> a detector that looks only at the marginal mismatch rate sees one number per
> session. Two very different worlds can produce the same number — an honest
> channel that is noisy, which disturbs every state a little, and a malicious
> channel attack that disturbs a few states completely. Can the observable
> evidence tell them apart?

The procedure, per attack type:

1. run honest populations over a noise sweep and malicious populations over an
   intensity sweep;
2. **match the marginals** — select the honest/malicious pair whose mean `D_m`
   are closest, so the comparison is at comparable marginal disturbance;
3. compute a fixed, non-learned **structural descriptor** for both populations —
   by default the per-basis mismatch dispersion `max_basis_rate - min_basis_rate`,
   which is large when a disturbance concentrates in some measurement bases and
   small when it is spread evenly;
4. report whether the descriptor ranges separate, alongside what the calibrated
   marginal rule does to the same two populations.

The four descriptors the experiment can use are `basis_mismatch_dispersion` (the
default), `mean_fidelity`, `minimum_fidelity` and `disturbance_rate`. Each maps a
record to one observable number, none is learned, and none is part of the
verification decision.

The criterion is **non-overlap of the descriptor ranges**. It is deliberately
conservative: ranges are sensitive to a single outlier, so this criterion fails
to declare a separation more readily than a mean comparison would. That is the
right direction to err in — the claim being tested is "the observable evidence
can tell these apart", and a conservative test that still succeeds is stronger
evidence than a permissive one that barely does.

When the ranges overlap, the verdict is the fixed literal sentence:

> **Not distinguishable under the current observable model.**

That is a real result, not a failure to be hidden. The project reports it when
it occurs.

Three things this experiment does not do:

* it does not attribute a cause to a session;
* it does not train anything;
* it does not claim the descriptor is a detector. The descriptor is a
  diagnostic, and the verification decision remains the single calibrated test
  on `D_m`. What the experiment shows is whether a *future* observable would
  carry additional information — a statement about the model, not about a
  running detector.

A pair whose marginals are both exactly zero is skipped: it has a gap of zero
and would always win, but it compares two undisturbed populations and therefore
demonstrates nothing. A zero-intensity attack is likewise excluded from the
default sweep, because at fraction `0` the attack *is* the honest baseline.

---

## 9. The reference curves

Every point below comes from runs performed by the benchmark. None is
interpolated, synthesised or copied.

| # | curve | x | y |
| --- | --- | --- | --- |
| 1 | `detection_probability_vs_attack_intensity` | attack fraction | share of malicious trials rejected |
| 2 | `frr_vs_honest_noise` | honest noise strength | honest false-rejection rate |
| 3 | `far_vs_threshold` | critical count | malicious acceptance rate |
| 4 | `detection_probability_vs_sample_size` | sample size `N` | share of malicious trials rejected |
| 5 | `fidelity_vs_attack_intensity` | attack fraction | mean reconstruction fidelity |
| 6 | `mismatch_vs_noise` | honest noise strength | observed mismatch rate |
| 7 | `honest_calibration_distribution` | per-session mismatch rate | empirical cumulative probability |
| 8 | `threshold_operating_curve` | critical count | honest rejection rate |

Curve 7 is an **ECDF rather than a histogram**, so that no bin width is chosen
after seeing the data.

Curves 3 and 8 are the two sides of the same trade-off: as the critical count
falls, the honest rejection rate falls and the malicious acceptance rate rises.
Both are reported so neither can be quoted alone.

ROC and PR curves are deliberately absent. They would require sweeping a
threshold across a continuum and reporting a single summary number, which
invites reading an area-under-curve as a security property. The threshold is
specified, not optimised, so there is no curve to summarise.

Each sample size gets **its own threshold**, derived from its own calibration
dataset; no threshold is reused across sizes. A threshold is a binomial quantile
of the calibrated null and needs no simulation, so the exact threshold table
covers the whole declared design range, including sizes the protocol cannot
simulate.

---

## 10. The reference operating point, as measured

Exactly one operating point is defined. Its calibration is documented in
`docs/security/statistical-calibration.md`; what this layer reports about it is:

* the honest false-rejection rate it actually produced, **labelled as fitted**
  because it is measured on the same data the threshold was derived from;
* the detection rate and FAR per attack type, each with its scope attached;
* the operating point on the FAR/FRR trade-off curve;
* its behaviour across the noise grid.

The point is **specified, not optimised**. No objective was maximised, so no
claim of optimality is made.

---

## 11. The multiple-comparison policy in evaluation

The policy is the one described in
`docs/security/statistical-calibration.md`: **one primary test, everything else
diagnostic**. In the evaluation layer this has a specific consequence:

* the reported detection rates and FARs are **measurements of one fixed rule**,
  not a family of tests;
* no combined family-wise claim is made anywhere in the report;
* `describe_diagnostics` marks each of the sixteen Milestone 4 quantities with
  `part_of_decision: false`, so a reader can see at a glance which number the
  decision rests on.

If several tests were ever genuinely required, the correct move is to declare a
`CORRECTED_FAMILY` policy with a family-wise budget — implemented, tested, and
not used — rather than to add uncorrected tests.

---

## 12. Reproducibility

The benchmark is run by a documented command:

```
PYTHONPATH=. .venv/Scripts/python.exe benchmarks/run_reference_benchmark.py
```

It writes `benchmarks/m5-reference.json` and `benchmarks/m5-reference.md`.

Reproducibility is claimed only where it was measured:

* a trial is a pure function of its seed and its scenario, so the same seed
  reproduces the same observable evidence **and the same decision** — a
  reproducible statistic with a drifting decision would be worse than none;
* running the whole pipeline twice produces identical reports, with the measured
  runtime the only differing field;
* the benchmark runs with the explicit transpile cache enabled, and the cached
  and uncached runs are compared field by field. The cache stores compiled
  circuits, never outcomes; it is off everywhere else in the project; and it is
  declared in the provenance rather than left implicit.

The provenance records the profile, the protocol version, the Python and
platform versions, the seed blocks, the number of scenarios run and the measured
runtime, so a reader can tell what produced the numbers.

---

## 13. The security interpretation layer

`backend.security.interpretation` exists to stop these numbers being quoted as
something they are not. The allowed and forbidden phrasings, the negation-aware
checker and the banned-terminology list are documented in
`docs/security/statistical-calibration.md` §12.

The rule in one line: **state what was measured, on what, at what size, under
what modelled conditions — and never promote a measurement to a proof.**

---

## 14. What is not claimed

* **No cause attribution.** A rejection is evidence of inconsistency with the
  calibrated honest model, not attribution of a cause.
* **No formal forgery bound.** The numbers here are empirical acceptance rates
  for modelled experiments. A formal derivation would be Milestone 6 work, and
  only if it is justified there.
* **No security proof from the simulator.** A simulator does not establish an
  information-theoretic security proof.
* **No transfer.** FAR and FRR depend on the modelled attacks, the modelled
  channel, the sample size and the error budget, and they do not transfer to
  other conditions.
* **No quantum identity proof.** Quantum measurement does not prove identity. A
  verified session is consistent with a calibrated honest model; it is not a
  proof of who sent it. Replay and identity checks are classical protocol
  controls, reported separately, and are not quantum evidence.
* **No machine learning.** There is no learned threshold, no trained classifier
  and no anomaly model.

---

## 15. Limitations

The report carries a fixed `limitations` list, and it is not generated from the
results, because limitations do not stop applying when a result looks good:

1. the construction is a reference prototype, not a formal protocol specification;
2. replay and identity checks are classical protocol controls;
3. quantum measurement does not prove identity;
4. the simulator establishes no new information-theoretic security proof and no
   formal forgery bound is derived;
5. acceptance in the sampled mode is a finite-shot outcome, not a deterministic
   property;
6. the test is a consistency test, not an attribution;
7. FAR and FRR are empirical and do not transfer;
8. a threshold is defined for one sample size, and applying it at another is a
   category error the code refuses;
9. the multiple-comparison policy is one primary test with diagnostics, and no
   joint acceptance region was derived;
10. no machine learning is used anywhere.

All ten appear in the rendered report, next to the numbers they qualify.
