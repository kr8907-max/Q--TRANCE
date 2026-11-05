# Milestone 5 report — Statistical calibration, finite-sample analysis and security evaluation

## Reference operating point

Exactly one operating point is defined. It is *specified*, not optimised:
no objective was maximised, so no claim of optimality is made.

| field | value |
| --- | --- |
| `name` | m5-reference |
| `statistic` | mismatch_rate |
| `state_count` | 500 |
| `measurement_mode` | sampled |
| `shot_count` | 1 |
| `threshold_rate` | 2.00% |
| `critical_count` | 10 |
| `p_upper` | 1.08% |
| `alpha` | 0.05 |
| `calibration_sessions` | 120 |
| `observed_calibration_frr` | 0.00% |

Honest channel: {"noise_strength": 0.02, "noise_type": "depolarizing"}

Calibration seed range: [0, 119]

## Measurement configuration

- measurement mode: `sampled`
- shots per state: 1
- reference honest channel: {"noise_strength": 0.02, "noise_type": "depolarizing"}

> the measurement mode decides whether the honest null is graded or degenerate, and the choice is therefore stated rather than left implicit. In 'projective-analytic' mode 'matched' means the received qubit is exactly the expected eigenstate, so any nonzero channel disturbance makes every state mismatch and the honest mismatch rate jumps from 0 to 1 with no interior for a finite-sample null. In 'sampled' mode with a large shot count the majority vote over many shots of a single qubit swamps small disturbance and the rate sits at 0 instead. 'sampled' mode with one shot per state is one measurement per qubit, which is what a verifier physically performs, and it gives a mismatch probability of 1 - p_match: a genuine interior null. This was established by measurement, not assumption; the three configurations were run over a noise sweep and their mismatch rates compared.

## Definitions

- FAR — FAR = malicious trials accepted / malicious trials: an empirical acceptance rate for the modelled attack experiment, not a cryptographic forgery probability
- FRR — FRR = honest trials rejected / honest trials: an empirical rejection rate measured on honest material
- the positive class is 'the verification decision rejected the session', so FPR equals FRR and FNR equals FAR

The four quantities that must not be conflated:

- **confidence_interval** — a statement about an unknown parameter, e.g. a Clopper-Pearson interval for the honest mismatch probability
- **classification_threshold** — a decision rule derived from that interval and the sample size, e.g. reject when the mismatch count exceeds a critical count
- **empirical_attack_acceptance_rate** — a measurement: the share of malicious trials the rule accepted, on a specific dataset under a specific modelled attack
- **formal_cryptographic_security_bound** — a proof-level bound on an adversary's advantage; NOT produced by this milestone and never to be read into the numbers above

## Multiple-comparison policy

- primary test: `mismatch_rate_against_calibrated_threshold`
- policy: SINGLE_PRIMARY_WITH_DIAGNOSTICS
- family-wise alpha: None (correction: None)
- reported as diagnostics only, never adjudicated: `verification_state_disturbance_rate`, `projective_match_probability`, `reconstruction_fidelity`, `minimum_fidelity`, `measurement_counts_by_basis`, `basis_distribution`, `per_basis_mismatch_rates`, `per_basis_disturbance_rates`, `state_count_consistency`, `transcript_validity`, `transcript_hash_validity`, `session_consistency`, `nonce_freshness_state`, `signer_authorization_validity`, `verifier_authorization_validity`, `cross_verifier_disagreement`

> exactly one statistic is tested; its level is the operating point's alpha, with no family to correct for
> every other Milestone 4 quantity is diagnostic evidence: reported, never adjudicated
> a joint acceptance region over several statistics is not implemented, because no honest-model derivation of one has been done

## Curves

Every point below comes from runs; none is interpolated or synthetic.

### `detection_probability_vs_attack_intensity`

- x: attack intensity (fraction of states); y: detection probability
- points: 5; total trials: 60

| x | y | trials |
| --- | --- | --- |
| 0 | 0 | 12 |
| 0.05 | 1 | 12 |
| 0.1 | 1 | 12 |
| 0.2 | 1 | 12 |
| 0.5 | 1 | 12 |

> the x axis is the attack fraction the experiment injected, not a threshold; the decision rule never sees it

### `frr_vs_honest_noise`

- x: honest noise strength; y: false-rejection rate
- points: 6; total trials: 72

| x | y | trials |
| --- | --- | --- |
| 0 | 0 | 12 |
| 0.005 | 0 | 12 |
| 0.01 | 0 | 12 |
| 0.02 | 0 | 12 |
| 0.05 | 0.583333 | 12 |
| 0.1 | 1 | 12 |


### `far_vs_threshold`

- x: critical count; y: false acceptance rate
- points: 14; total trials: 168

| x | y | trials |
| --- | --- | --- |
| 0 | 1 | 12 |
| 1 | 1 | 12 |
| 2 | 1 | 12 |
| 3 | 1 | 12 |
| 4 | 1 | 12 |
| 5 | 1 | 12 |
| 6 | 1 | 12 |
| 7 | 1 | 12 |
| 8 | 1 | 12 |
| 9 | 1 | 12 |
| 10 | 1 | 12 |
| 11 | 1 | 12 |
| 12 | 1 | 12 |
| 13 | 1 | 12 |

> the reference operating point sits at critical count 10
> the x axis is a candidate critical count applied to measured mismatch counts; both axes come from the same two populations

### `detection_probability_vs_sample_size`

- x: sample size (usable observations); y: detection probability
- points: 5; total trials: 30

| x | y | trials |
| --- | --- | --- |
| 100 | 1 | 6 |
| 250 | 1 | 6 |
| 500 | 1 | 6 |
| 1000 | 1 | 6 |
| 2500 | 1 | 6 |

> each sample size has its own threshold, derived from its own calibration dataset; no threshold is reused across sizes
> trial counts differ between sizes, so a point at a large N rests on fewer trials than a point at a small N

### `fidelity_vs_attack_intensity`

- x: attack intensity (fraction of states); y: mean analytic fidelity
- points: 5; total trials: 60

| x | y | trials |
| --- | --- | --- |
| 0 | 0.99 | 12 |
| 0.05 | 0.957333 | 12 |
| 0.1 | 0.926137 | 12 |
| 0.2 | 0.85231 | 12 |
| 0.5 | 0.66415 | 12 |


### `mismatch_vs_noise`

- x: honest noise strength; y: mean mismatch rate
- points: 6; total trials: 72

| x | y | trials |
| --- | --- | --- |
| 0 | 0 | 12 |
| 0.005 | 0.00183333 | 12 |
| 0.01 | 0.00433333 | 12 |
| 0.02 | 0.0108333 | 12 |
| 0.05 | 0.0215 | 12 |
| 0.1 | 0.0545 | 12 |


### `honest_calibration_distribution`

- x: per-session mismatch rate; y: empirical cumulative probability
- points: 120; total trials: 14400

| x | y | trials |
| --- | --- | --- |
| 0 | 0.00833333 | 120 |
| 0.002 | 0.0166667 | 120 |
| 0.002 | 0.025 | 120 |
| 0.002 | 0.0333333 | 120 |
| 0.004 | 0.0416667 | 120 |
| 0.004 | 0.05 | 120 |
| 0.004 | 0.0583333 | 120 |
| 0.004 | 0.0666667 | 120 |
| 0.004 | 0.075 | 120 |
| 0.004 | 0.0833333 | 120 |
| 0.004 | 0.0916667 | 120 |
| 0.004 | 0.1 | 120 |
| 0.004 | 0.108333 | 120 |
| 0.004 | 0.116667 | 120 |
| 0.004 | 0.125 | 120 |
| 0.006 | 0.133333 | 120 |
| 0.006 | 0.141667 | 120 |
| 0.006 | 0.15 | 120 |
| 0.006 | 0.158333 | 120 |
| 0.006 | 0.166667 | 120 |
| 0.006 | 0.175 | 120 |
| 0.006 | 0.183333 | 120 |
| 0.006 | 0.191667 | 120 |
| 0.006 | 0.2 | 120 |
| 0.006 | 0.208333 | 120 |
| 0.006 | 0.216667 | 120 |
| 0.006 | 0.225 | 120 |
| 0.006 | 0.233333 | 120 |
| 0.006 | 0.241667 | 120 |
| 0.006 | 0.25 | 120 |
| 0.006 | 0.258333 | 120 |
| 0.006 | 0.266667 | 120 |
| 0.006 | 0.275 | 120 |
| 0.006 | 0.283333 | 120 |
| 0.008 | 0.291667 | 120 |
| 0.008 | 0.3 | 120 |
| 0.008 | 0.308333 | 120 |
| 0.008 | 0.316667 | 120 |
| 0.008 | 0.325 | 120 |
| 0.008 | 0.333333 | 120 |
| 0.008 | 0.341667 | 120 |
| 0.008 | 0.35 | 120 |
| 0.008 | 0.358333 | 120 |
| 0.008 | 0.366667 | 120 |
| 0.008 | 0.375 | 120 |
| 0.008 | 0.383333 | 120 |
| 0.008 | 0.391667 | 120 |
| 0.008 | 0.4 | 120 |
| 0.008 | 0.408333 | 120 |
| 0.008 | 0.416667 | 120 |
| 0.008 | 0.425 | 120 |
| 0.008 | 0.433333 | 120 |
| 0.008 | 0.441667 | 120 |
| 0.008 | 0.45 | 120 |
| 0.008 | 0.458333 | 120 |
| 0.01 | 0.466667 | 120 |
| 0.01 | 0.475 | 120 |
| 0.01 | 0.483333 | 120 |
| 0.01 | 0.491667 | 120 |
| 0.01 | 0.5 | 120 |
| 0.01 | 0.508333 | 120 |
| 0.01 | 0.516667 | 120 |
| 0.01 | 0.525 | 120 |
| 0.01 | 0.533333 | 120 |
| 0.01 | 0.541667 | 120 |
| 0.01 | 0.55 | 120 |
| 0.01 | 0.558333 | 120 |
| 0.01 | 0.566667 | 120 |
| 0.01 | 0.575 | 120 |
| 0.01 | 0.583333 | 120 |
| 0.012 | 0.591667 | 120 |
| 0.012 | 0.6 | 120 |
| 0.012 | 0.608333 | 120 |
| 0.012 | 0.616667 | 120 |
| 0.012 | 0.625 | 120 |
| 0.012 | 0.633333 | 120 |
| 0.012 | 0.641667 | 120 |
| 0.012 | 0.65 | 120 |
| 0.012 | 0.658333 | 120 |
| 0.012 | 0.666667 | 120 |
| 0.012 | 0.675 | 120 |
| 0.012 | 0.683333 | 120 |
| 0.012 | 0.691667 | 120 |
| 0.012 | 0.7 | 120 |
| 0.012 | 0.708333 | 120 |
| 0.012 | 0.716667 | 120 |
| 0.012 | 0.725 | 120 |
| 0.012 | 0.733333 | 120 |
| 0.012 | 0.741667 | 120 |
| 0.014 | 0.75 | 120 |
| 0.014 | 0.758333 | 120 |
| 0.014 | 0.766667 | 120 |
| 0.014 | 0.775 | 120 |
| 0.014 | 0.783333 | 120 |
| 0.014 | 0.791667 | 120 |
| 0.014 | 0.8 | 120 |
| 0.014 | 0.808333 | 120 |
| 0.014 | 0.816667 | 120 |
| 0.014 | 0.825 | 120 |
| 0.014 | 0.833333 | 120 |
| 0.014 | 0.841667 | 120 |
| 0.014 | 0.85 | 120 |
| 0.014 | 0.858333 | 120 |
| 0.016 | 0.866667 | 120 |
| 0.016 | 0.875 | 120 |
| 0.016 | 0.883333 | 120 |
| 0.016 | 0.891667 | 120 |
| 0.016 | 0.9 | 120 |
| 0.016 | 0.908333 | 120 |
| 0.016 | 0.916667 | 120 |
| 0.016 | 0.925 | 120 |
| 0.016 | 0.933333 | 120 |
| 0.018 | 0.941667 | 120 |
| 0.018 | 0.95 | 120 |
| 0.018 | 0.958333 | 120 |
| 0.018 | 0.966667 | 120 |
| 0.018 | 0.975 | 120 |
| 0.02 | 0.983333 | 120 |
| 0.02 | 0.991667 | 120 |
| 0.02 | 1 | 120 |

> this is the honest null as measured, not as assumed; it is an ECDF rather than a histogram so that no bin width is chosen after seeing the data

### `threshold_operating_curve`

- x: critical count; y: honest false-rejection rate
- points: 14; total trials: 168

| x | y | trials |
| --- | --- | --- |
| 0 | 1 | 12 |
| 1 | 1 | 12 |
| 2 | 1 | 12 |
| 3 | 0.916667 | 12 |
| 4 | 0.416667 | 12 |
| 5 | 0.333333 | 12 |
| 6 | 0.166667 | 12 |
| 7 | 0.0833333 | 12 |
| 8 | 0.0833333 | 12 |
| 9 | 0.0833333 | 12 |
| 10 | 0 | 12 |
| 11 | 0 | 12 |
| 12 | 0 | 12 |
| 13 | 0 | 12 |

> the reference operating point sits at critical count 10
> the x axis is a candidate critical count applied to measured mismatch counts; both axes come from the same two populations

## Attack evaluation

> every trial the experiment injected an attack into: forgery, impersonation, unauthorized verification, replay, intercept-resend and channel tampering. Honest trials are never malicious.

| attack | fraction | malicious trials | detection rate | FAR | FRR |
| --- | --- | --- | --- | --- | --- |
| `forgery` | 0 | 12 | 0.00% | 100.00% | n/a |
| `impersonation` | 0 | 12 | 0.00% | 100.00% | n/a |
| `unauthorized_verification` | 0 | 12 | 0.00% | 100.00% | n/a |
| `replay` | 0 | 12 | 0.00% | 100.00% | n/a |
| `intercept_resend` | 0.2 | 12 | 100.00% | 0.00% | n/a |
| `channel_tampering` | 0.2 | 12 | 100.00% | 0.00% | n/a |

## Noise robustness

| noise level | honest FRR | none | low | medium | high |
| --- | --- | --- | --- | --- | --- |
| none | 0.00% | n/a | n/a | n/a | n/a |
| low | 0.00% | n/a | n/a | n/a | n/a |
| medium | 0.00% | n/a | n/a | n/a | n/a |
| high | 100.00% | n/a | n/a | n/a | n/a |

## Sample-size study

| N | critical count | threshold rate | honest FRR | detection |
| --- | --- | --- | --- | --- |
| 100 | 5 | 5.00% | 0.00% | 100.00% |
| 250 | 7 | 2.80% | 0.00% | 100.00% |
| 500 | 13 | 2.60% | 0.00% | 100.00% |
| 1000 | 20 | 2.00% | 0.00% | 100.00% |
| 2500 | 48 | 1.92% | 0.00% | 100.00% |

## Discrimination experiment

Comparing honest noise with a malicious channel attack at comparable marginal mismatch rates.

### channel_tampering at fraction 0.05

- honest marginal mismatch rate: 0.0231667
- malicious marginal mismatch rate: 0.0338333
- marginal gap: 0.0106667 (matched: False)
- descriptor: `basis_mismatch_dispersion`
- distinguishable: **True**
- verdict: distinguishable on [basis_mismatch_dispersion]: the malicious population's range lies outside the honest population's range, which the marginal mismatch rate alone does not reveal
- honest rejection rate: 58.33%
- malicious rejection rate: 100.00%

### intercept_resend at fraction 0.05

- honest marginal mismatch rate: 0.0231667
- malicious marginal mismatch rate: 0.0195
- marginal gap: 0.00366667 (matched: True)
- descriptor: `basis_mismatch_dispersion`
- distinguishable: **False**
- verdict: Not distinguishable under the current observable model.
- honest rejection rate: 58.33%
- malicious rejection rate: 50.00%

## Limitations

- The construction is a reference prototype. The organiser requirement specifies primitives and goals, not a complete formal QDS protocol, and nothing here should be read as a specification of one.
- Replay and identity checks are classical protocol controls. They are authorization bookkeeping, not quantum evidence, and they are reported separately for that reason.
- Quantum measurement does not prove identity. A verified session is consistent with a calibrated honest model; it is not a proof of who sent it.
- The simulator does not establish a new information-theoretic security proof, and no formal forgery bound is derived at this milestone. Deriving one is Milestone 6 work, and only if it is justified there.
- Acceptance in the sampled measurement mode is a finite-shot outcome, not a deterministic property. The mode travels with every observation so the two are never conflated.
- The statistical test is a consistency test against a calibrated honest model. A rejection is evidence of inconsistency with that model, not attribution of a cause.
- FAR and FRR are empirical rates measured on the reported dataset. They depend on the modelled attacks, the modelled channel, the sample size and the error budget, and they do not transfer to other conditions.
- The threshold is defined for one sample size. Applying it at another sample size is a category error, and the code raises rather than allowing it.
- The multiple-comparison policy is one primary test with the remaining statistics reported as diagnostics. No joint acceptance region was derived, so no combined family-wise claim is made.
- No machine learning is used anywhere. There is no learned threshold, no trained classifier and no anomaly model, so no result depends on a fitted model that could not be inspected.

## Provenance

```json
{
  "platform": "Windows-11-10.0.26200-SP0",
  "profile": "m5-reference",
  "profile_description": "the recorded reference benchmark: one reference operating point, the eight reference curves, the attack evaluation, the noise grid and the discrimination experiment",
  "profile_notes": [
    "trial counts are derived from a declared state budget rather than hand-picked; the quantity that costs time is trials x state_count, and holding it bounded keeps the study affordable while covering every simulatable design sample size",
    "the reference channel is depolarizing at eta=0.02 with one measurement shot per state, which is the configuration in which the honest mismatch probability has a genuine interior value",
    "the two largest design sample sizes (5000 and 10000) are above the reference protocol's maximum signature length of 4096 states, so they are declared as design values and have their thresholds derived exactly from the calibrated null, but they are not simulated: the protocol bound is not widened to make a benchmark reachable"
  ],
  "profile_parameters": {
    "attack_fraction": 0.2,
    "attack_fractions": [
      0.0,
      0.05,
      0.1,
      0.2,
      0.5
    ],
    "attack_types": [
      "forgery",
      "impersonation",
      "unauthorized_verification",
      "replay",
      "intercept_resend",
      "channel_tampering"
    ],
    "calibration_sessions": 120,
    "description": "the recorded reference benchmark: one reference operating point, the eight reference curves, the attack evaluation, the noise grid and the discrimination experiment",
    "discrimination_attack_fractions": [
      0.05,
      0.1,
      0.2,
      0.5
    ],
    "discrimination_noise_strengths": [
      0.0,
      0.005,
      0.01,
      0.02,
      0.05
    ],
    "discrimination_trials": 12,
    "evaluation_trials": 12,
    "measurement_mode": "sampled",
    "name": "m5-reference",
    "noise_strengths": [
      0.0,
      0.005,
      0.01,
      0.02,
      0.05,
      0.1
    ],
    "noise_type": "depolarizing",
    "notes": [
      "trial counts are derived from a declared state budget rather than hand-picked; the quantity that costs time is trials x state_count, and holding it bounded keeps the study affordable while covering every simulatable design sample size",
      "the reference channel is depolarizing at eta=0.02 with one measurement shot per state, which is the configuration in which the honest mismatch probability has a genuine interior value",
      "the two largest design sample sizes (5000 and 10000) are above the reference protocol's maximum signature length of 4096 states, so they are declared as design values and have their thresholds derived exactly from the calibrated null, but they are not simulated: the protocol bound is not widened to make a benchmark reachable"
    ],
    "reference_noise_strength": 0.02,
    "robustness_attack_fraction": 0.2,
    "robustness_levels": [
      [
        "none",
        0.0
      ],
      [
        "low",
        0.005
      ],
      [
        "medium",
        0.02
      ],
      [
        "high",
        0.1
      ]
    ],
    "robustness_trials": 8,
    "sample_size_design": [
      100,
      250,
      500,
      1000,
      2500,
      5000,
      10000
    ],
    "sample_size_plan": [
      {
        "calibration_sessions": 24,
        "calibration_states": 2400,
        "evaluation_states_per_arm": 600,
        "state_count": 100,
        "trials": 6
      },
      {
        "calibration_sessions": 24,
        "calibration_states": 6000,
        "evaluation_states_per_arm": 1500,
        "state_count": 250,
        "trials": 6
      },
      {
        "calibration_sessions": 12,
        "calibration_states": 6000,
        "evaluation_states_per_arm": 3000,
        "state_count": 500,
        "trials": 6
      },
      {
        "calibration_sessions": 6,
        "calibration_states": 6000,
        "evaluation_states_per_arm": 6000,
        "state_count": 1000,
        "trials": 6
      },
      {
        "calibration_sessions": 3,
        "calibration_states": 7500,
        "evaluation_states_per_arm": 15000,
        "state_count": 2500,
        "trials": 6
      }
    ],
    "sample_size_simulated": [
      100,
      250,
      500,
      1000,
      2500
    ],
    "sample_size_unreachable": [
      5000,
      10000
    ],
    "seed_base": 0,
    "shot_count": 1,
    "state_count": 500,
    "total_planned_states_lower_bound": 380100
  },
  "protocol_version": "RQDS-TP-1.0",
  "python": "3.13.5",
  "runtime_note": "measured with time.perf_counter around the whole run; no runtime figure in this project is estimated",
  "runtime_seconds": 1504.8553420000244,
  "scenario_count": 479,
  "seed_blocks": [
    {
      "count": 120,
      "first_seed": 0,
      "label": "calibration"
    },
    {
      "count": 24,
      "first_seed": 100001,
      "label": "sample-size-calibration-100"
    },
    {
      "count": 6,
      "first_seed": 200002,
      "label": "sample-size-honest-100"
    },
    {
      "count": 6,
      "first_seed": 300003,
      "label": "sample-size-attack-100"
    },
    {
      "count": 24,
      "first_seed": 400004,
      "label": "sample-size-calibration-250"
    },
    {
      "count": 6,
      "first_seed": 500005,
      "label": "sample-size-honest-250"
    },
    {
      "count": 6,
      "first_seed": 600006,
      "label": "sample-size-attack-250"
    },
    {
      "count": 12,
      "first_seed": 700007,
      "label": "sample-size-calibration-500"
    },
    {
      "count": 6,
      "first_seed": 800008,
      "label": "sample-size-honest-500"
    },
    {
      "count": 6,
      "first_seed": 900009,
      "label": "sample-size-attack-500"
    },
    {
      "count": 6,
      "first_seed": 1000010,
      "label": "sample-size-calibration-1000"
    },
    {
      "count": 6,
      "first_seed": 1100011,
      "label": "sample-size-honest-1000"
    },
    {
      "count": 6,
      "first_seed": 1200012,
      "label": "sample-size-attack-1000"
    },
    {
      "count": 3,
      "first_seed": 1300013,
      "label": "sample-size-calibration-2500"
    },
    {
      "count": 6,
      "first_seed": 1400014,
      "label": "sample-size-honest-2500"
    },
    {
      "count": 6,
      "first_seed": 1500015,
      "label": "sample-size-attack-2500"
    },
    {
      "count": 12,
      "first_seed": 1600016,
      "label": "attack-forgery"
    },
    {
      "count": 12,
      "first_seed": 1700017,
      "label": "attack-impersonation"
    },
    {
      "count": 12,
      "first_seed": 1800018,
      "label": "attack-unauthorized_verification"
    },
    {
      "count": 12,
      "first_seed": 1900019,
      "label": "attack-replay"
    },
    {
      "count": 12,
      "first_seed": 2000020,
      "label": "attack-intercept_resend"
    },
    {
      "count": 12,
      "first_seed": 2100021,
      "label": "attack-channel_tampering"
    },
    {
      "count": 12,
      "first_seed": 2200022,
      "label": "intensity-0"
    },
    {
      "count": 12,
      "first_seed": 2300023,
      "label": "intensity-0.05"
    },
    {
      "count": 12,
      "first_seed": 2400024,
      "label": "intensity-0.1"
    },
    {
      "count": 12,
      "first_seed": 2500025,
      "label": "intensity-0.2"
    },
    {
      "count": 12,
      "first_seed": 2600026,
      "label": "intensity-0.5"
    },
    {
      "count": 12,
      "first_seed": 2700027,
      "label": "noise-0"
    },
    {
      "count": 12,
      "first_seed": 2800028,
      "label": "noise-0.005"
    },
    {
      "count": 12,
      "first_seed": 2900029,
      "label": "noise-0.01"
    },
    {
      "count": 12,
      "first_seed": 3000030,
      "label": "noise-0.02"
    },
    {
      "count": 12,
      "first_seed": 3100031,
      "label": "noise-0.05"
    },
    {
      "count": 12,
      "first_seed": 3200032,
      "label": "noise-0.1"
    },
    {
      "count": 12,
      "first_seed": 3300033,
      "label": "reference-honest"
    },
    {
      "count": 12,
      "first_seed": 3400034,
      "label": "reference-attack"
    },
    {
      "count": 1,
      "first_seed": 3500035,
      "label": "robustness"
    },
    {
      "count": 1,
      "first_seed": 3600036,
      "label": "discrimination"
    }
  ],
  "transpile_cache": {
    "enabled_during_run": true,
    "max_entries": 64,
    "note": "the cache stores compiled circuits keyed by a canonical circuit digest; it never stores outcomes. It is off by default and is proven result-preserving by tests/quantum/test_cache.py. The cache is disabled again once the run finishes, so enabled=False here would be wrong to read as 'the cache was not used'.",
    "stats": {
      "enabled": true,
      "entries": 6,
      "evictions": 0,
      "hit_rate": 0.9999842146803473,
      "hits": 380094,
      "lookups": 380100,
      "max_entries": 64,
      "misses": 6
    }
  }
}
```
