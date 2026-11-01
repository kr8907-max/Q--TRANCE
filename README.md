# Q-TRACE

## Quantum Threat & Reliability Analysis for Cryptographic Evidence

**Q-TRACE is a quantum-simulation-backed, model-based statistical framework for analyzing
observable threats and protocol inconsistencies in teleportation-based digital-signature
verification.**

> **Research/prototype disclaimer.** Q-TRACE is a research/prototype framework. Its
> experimental results are configuration-dependent and should not be interpreted as a formal
> proof of information-theoretic security or cryptographic unforgeability.

| | |
|---|---|
| **Problem statement** | SIH26141 — *Quantum-Inspired Cyber Threat Detection for Digital Signature Security* |
| **Hackathon** | Smart India Hackathon 2026 (problem sponsor: Egreen Quanta LLP) |
| **Reference protocol id** | `RQDS-TP-1.0` (a project reference construction — **not** a standard, **not** the official Egreen Quanta protocol) |
| **API** | FastAPI, versioned under `/api/v1` |
| **Frontend** | React 18 + TypeScript + Vite console, branded **Q-TRACE** |

![Python](https://img.shields.io/badge/python-3.13-blue.svg)
![Qiskit](https://img.shields.io/badge/qiskit-2.5.2-6929c4.svg)
![FastAPI](https://img.shields.io/badge/fastapi-0.141.1-009688.svg)
![React](https://img.shields.io/badge/react-18-61dafb.svg)

*Version badges are read from `requirements.txt` and `frontend/package.json`. There is **no CI
pipeline** in this repository, so no build/test-status badge is shown — adding one would be fake.*

---

## 1. What Is Q-TRACE?

Q-TRACE simulates a small digital-signature conversation that uses quantum teleportation, then
deliberately subjects it to honest noise and to modelled attackers. It keeps only the evidence a
real verifier could actually observe, and asks a careful statistical question: *is the observed
disturbance larger than honest noise alone would produce?* The answer is produced by exact
finite-sample statistics on counts — never by a trained model.

Q-TRACE is a:

- **quantum-simulation-backed** framework (density-matrix / statevector simulation on Qiskit + Qiskit-Aer),
- **model-based** framework (explicit Pauli channels, explicit attack models),
- **statistical** framework (exact Clopper–Pearson intervals, an honest-null threshold),
- **observable-evidence** framework (the detector sees only what a verifier could see),
- **threat-detection** framework for teleportation-based signature verification.

**It is not a machine-learning classifier.** There is no neural network, random forest, SVM,
deep-learning model, trained classifier, or learned threshold anywhere in the codebase; the
dependency manifest states that no ML dependency is present *by design*.

---

## 2. Problem We Are Solving

Digital signatures give us authenticity, integrity and non-repudiation. Almost every deployed
scheme (RSA, DSA, ECDSA) is *computationally* secure: it is safe only as long as certain math
problems stay hard. A large fault-tolerant quantum computer running **Shor's algorithm** would
break those problems. That is why quantum-resistant signature research — including **Quantum
Digital Signatures (QDS)**, whose security rests on quantum mechanics rather than on hard math —
matters.

Q-TRACE addresses the SIH26141 ask: build a *quantum-inspired threat-detection* layer for
digital-signature security. It models how a teleportation-based signature behaves, how honest
noise and attackers disturb it, and how to detect that disturbance from observable evidence.

> **Background only.** Shor's algorithm, RSA, DSA and ECDSA appear here purely as motivation and
> context. **None of them is implemented in this repository.** There is no factorisation code and
> no classical public-key cryptography; the reference protocol holds no key material at all.

---

## 3. Core Idea

**Plain English.** The sender turns a message into a short list of tiny quantum objects (qubits)
chosen from six well-known states, and teleports each one to the receiver using a shared
entangled pair. Anyone who secretly measures or tampers with a qubit in transit disturbs it in a
way the receiver can notice when measuring in the basis the protocol specifies. Q-TRACE simulates
this conversation, adds honest noise and simulated attackers, and uses plain statistics on the
resulting counts to decide whether what it sees is inconsistent with honest behaviour.

**Technically.** The end-to-end pipeline is:

```
Message
  -> Session / Binding            (SHA-256 canonical binding; CSPRNG session_id + nonce)
  -> Quantum-State Generation     (deterministic six-state Pauli sequence from the binding)
  -> Bell-State Teleportation     (|Phi+> pair; 2 classical Bell bits per state)
  -> Noise / Attack Simulation    (honest Pauli channel and/or a modelled attack)
  -> Measurement                  (Born rule in the derived basis)
  -> Observable Evidence          (only verifier-visible quantities)
  -> Statistical Detection        (mismatch rate + exact binomial interval; categorical findings)
  -> Calibration                  (honest-null threshold k_crit(N))
  -> Evaluation                   (FAR / FRR / detection; curves; robustness; discrimination)
  -> Security Interpretation      (assumptions, observability, composition, claim checker)
```

The single most important design rule: **ground truth never reaches the detector.** The simulator
knows whether an attack happened; the detector must infer it from evidence alone (see §10).

---

## 4. What the System Actually Implements

Every row below is verified against the current source.

| Component | What it does | Status |
|---|---|---|
| Six Pauli eigenstates | Exact eigenstate table for Z/X/Y bases (`backend/quantum/states.py`) | Implemented |
| Bell-state preparation | `|Phi+> = (|00>+|11>)/sqrt(2)` via H + CX (`backend/quantum/bell.py`) | Implemented |
| Quantum teleportation | 3-qubit circuit with Bell measurement (`backend/quantum/teleport.py`) | Implemented |
| Pauli corrections | Feed-forward `U = Z^m0 * X^m1` (`backend/quantum/correction.py`) | Implemented |
| Density-matrix / statevector simulation | Born rule, projectors, fidelity, trace distance (`backend/quantum/density.py`) | Implemented |
| Projective measurement | Basis rotation to Z + Aer shot execution (`backend/quantum/measure.py`) | Implemented |
| Channel noise | 5 Pauli channels applied analytically (`backend/noise/`) | Implemented |
| Attack simulation | 6 attack models with observable/ground-truth split (`backend/attacks/`) | Implemented |
| Message binding | SHA-256 canonical named-field binding (`backend/protocol/binding.py`) | Implemented |
| Session / nonce logic | CSPRNG session id + nonce; lifecycle (`backend/protocol/session.py`) | Implemented |
| Transcript verification | Hash-sealed canonical transcript; independent reconstruction (`backend/protocol/{transcript,verifier}.py`) | Implemented |
| Authorization | Deterministic membership test on declared identities (`backend/detection/authorization.py`) | Implemented (classical) |
| Replay handling | In-memory nonce/session/transcript ledger (`backend/detection/replay.py`) | Implemented (classical, in-memory) |
| Observable-evidence detection | Label-free detector over observable input (`backend/detection/`) | Implemented |
| Mismatch-rate statistics | `D_m = N_mismatch / N_valid` + exact Clopper–Pearson (`backend/detection/{mismatch,statistics}.py`) | Implemented |
| Calibration | Honest-null quantile threshold, split alpha (`backend/calibration/`) | Implemented |
| Finite-size analysis | Hoeffding cross-check; finite-size bounds flagged non-cryptographic (`backend/security/finite_size.py`) | Implemented |
| Evaluation | Benchmark harness, metrics, curves, robustness, discrimination (`backend/evaluation/`) | Implemented |
| Security interpretation | Assumptions, observability, composition, claim checker (`backend/security/`) | Implemented |
| FastAPI backend | App factory, `/api/v1` routes, Pydantic, in-memory store (`backend/api/`) | Implemented |
| React/TS/Vite frontend | Seven-page Q-TRACE console (`frontend/`) | Implemented |
| Secret-key signing / unforgeability | No key material exists; unforgeability not claimed | **Not implemented (by design)** |
| Hardware quantum execution | All quantum behaviour is simulated (Aer) | **Not implemented** |

---

## 5. Architecture

```
                        +---------------------------+
                        |   Q-TRACE web console     |   React 18 + TS + Vite (frontend/)
                        |  (Q-TRACE branding)       |
                        +-------------+-------------+
                                      |  HTTP (JSON)
                        +-------------v-------------+
                        |        FastAPI app        |   backend/api/  (create_app factory)
                        |  /health /ready /version  |   operational routes at ROOT
                        |      /api/v1/...          |   business routes versioned
                        +-------------+-------------+
                                      |
        +-----------+-----------+-----+------+-----------+-----------+
        |           |           |            |           |           |
  +-----v----+ +----v-----+ +---v-----+ +----v-----+ +---v-----+ +---v--------+
  | Sessions | |Simulation| |Detection| |Calibration| |Evaluation| | Security  |
  | /Verify  | |          | |         | |           | |          | | Analysis  |
  +-----+----+ +----+-----+ +---+-----+ +----+------+ +---+------+ +----+------+
        |           |           |            |           |           |
        +-----------+-----------+-----+------+-----------+-----------+
                                      |
                        +-------------v-------------+
                        |  Quantum / Protocol /     |   backend/quantum, backend/protocol,
                        |  Noise / Attacks /        |   backend/noise, backend/attacks,
                        |  Statistics layers        |   backend/simulation
                        +-------------+-------------+
                                      |
                        +-------------v-------------+
                        |  Evidence + Results       |   observable data, findings,
                        |  (ground truth kept       |   metrics; ground truth confined
                        |   OUT of the detector)    |   to the evaluation layer
                        +---------------------------+
```

**Dependency direction is one-way and enforced by tests:**
`backend.quantum -> backend.protocol -> backend.noise -> backend.attacks -> backend.simulation`,
with detection/calibration/evaluation/security layered above and `backend.api` as the outer
boundary. `backend.detection` is forbidden (by AST test) from importing `backend.attacks`,
`backend.noise` or `backend.simulation`.

**Where ground truth lives — and where it may not flow.** Each simulation run produces two
objects: `ObservableExperimentData` (verifier-visible) and `GroundTruthMetadata`
(`is_malicious`, `attack_type`, `attack_fraction`, noise settings, seed). Only the observable
half may reach the detector; the ground-truth half is readable only by the evaluation layer and,
deliberately, by the separate `/api/v1/simulations/evaluation` route.

---

## 6. Quantum Model

- **Six Pauli eigenstates** — the protocol alphabet: `|0>,|1>` (Z), `|+>,|->` (X), `|+i>,|-i>` (Y),
  with protocol ids `Z+,Z-,X+,X-,Y+,Y-`.
- **Bell state** — the shared entangled resource is `|Phi+>`:

  `|Phi+> = (|00> + |11>) / sqrt(2)`

- **Teleportation** — q0 holds the signature state, q1/q2 the Bell pair. Sequence: initialise q0;
  H(q1), CX(q1,q2); CX(q0,q1); H(q0); measure q0 and q1 (the **Bell measurement**), yielding two
  **classical correction bits** `(m0, m1)`; conditionally correct q2.
- **Pauli correction** — the by-product Pauli per branch is undone by

  `U(m0,m1) = Z^m0 * X^m1`

  implemented as genuine Qiskit classical feed-forward. Without it, Bob's bit is wrong in two of
  four branches; with it, all four branches recover the state exactly.
- **Density matrices** — mixed (post-noise) states are density matrices `rho` with `Tr rho = 1`.
- **Projective measurement** — the probability of the expected outcome is the Born rule with
  projector `P_psi = |psi><psi|`:

  `p_match = Tr(P_psi * rho)`   and   `F = <psi| rho |psi>`

  **These two are the same quantity** for a pure expected state (`p_match == F`, identically).
  The code states this and forbids reporting them as two independent pieces of evidence.
- Measuring in the wrong basis yields probability exactly `0.5` — the physical source of
  detectable disturbance.

---

## 7. Protocol / QDS Reference Model

- **Session creation** — `session_id` (128-bit) and `nonce` (256-bit) are drawn from the OS
  CSPRNG (`secrets`); they are unpredictable, unique and never derived from the message. Protocol
  lifecycle in this layer is exactly `CREATED -> SIGNED`.
- **Message binding** — a domain-separated, canonical named-field SHA-256:

  `message_binding = SHA256( canonical{ domain, protocol_version, session_id, nonce, message } )`

- **State sequence** — the binding seeds a counter-mode SHA-256 stream; nibbles are
  rejection-sampled (`nibble < 12`, `index = nibble mod 6`) into an **unbiased** sequence over the
  six-state alphabet. The derivation is a pure function of `(binding, count)`.

  > **Engineering construction.** This hash→state mapping is explicitly a *project/reference
  > engineering choice*, not a security construction and not a standardised QDS encoding. The
  > source says so verbatim (`backend/protocol/encoding.py`).
- **Transcript** — a 15-field canonical record sealed by `transcript_hash = SHA256(canonical
  payload)`. States are recorded symbolically (which eigenstate), never as amplitudes.
- **Signing** — derives the sequence, teleports each state (recording the two public Bell bits),
  seals the transcript.
- **Verification** — the verifier **never trusts the signer**: it recomputes the hash and binding,
  independently re-derives the state sequence, compares against the declared states, and measures
  each received qubit in the derived basis. Every verification appends the caveat that reference
  verification establishes *binding and consistency, not unforgeability*.

> **This repository does not claim a formal cryptographic QDS security proof or a formal
> unforgeability proof.** There is no secret signing key, no forgery game and no advantage
> computation; a keyless full forgery verifies successfully, and the project demonstrates this
> honestly rather than hiding it.

---

## 8. Noise Model

All honest channels are single-qubit Pauli channels applied analytically to density matrices:
`E(rho) = p_I*rho + p_X*X rho X + p_Y*Y rho Y + p_Z*Z rho Z`.

| Name | Form | Simple explanation | Role in experiments |
|---|---|---|---|
| `none` (identity) | `p_I = 1` | no noise | honest baseline |
| `depolarizing` | `p_I = 1-3p/4`, `p_X=p_Y=p_Z=p/4` | blend the state toward total randomness | the reference calibrated channel; state-independent disturbance `T = p/2` |
| `bit_flip` | `p_X = p` | random bit flip | basis-dependent disturbance (invisible on X eigenstates) |
| `phase_flip` | `p_Z = p` | random phase flip | invisible on Z eigenstates / to Z-basis measurement |
| `bit_phase_flip` | `p_Y = p` | random bit+phase flip | invisible on Y eigenstates |

For depolarizing strength `eta`, every reference state has match probability `1 - eta/2`, so one
projective measurement mismatches with probability `eta/2`. This is the honest null's non-zero
mean and the bridge from a physical parameter to the detection statistic.

---

## 9. Attack Models

Six attacks are implemented. They fall into two fundamentally different detection regimes.

**Quantum-channel attacks** (disturb the qubits; detected via elevated mismatch rate):

| Attack | Attacker changes | Unchanged | Evidence |
|---|---|---|---|
| `intercept_resend` | measures each intercepted qubit in a basis and re-prepares the eigenstate obtained | transcript, identities | wrong-basis guesses give `p_match = 0.5` → elevated `D_m` |
| `channel_tampering` | applies a coherent Pauli `P rho P†` to a fraction of states | transcript, identities | anticommuting Pauli gives `p_match = 0` → elevated `D_m` |

**Classical protocol attacks** (leave the quantum evidence untouched; detected — if at all — by
classical controls, **not** by quantum mismatch):

| Attack | Attacker changes | Unchanged | Evidence |
|---|---|---|---|
| `forgery` | re-binds or fully forges a transcript using the *public* derivation | the quantum channel | binding / state-sequence re-derivation (integrity) |
| `impersonation` | presents an unauthorized `signer_id` | quantum channel | authorization membership test |
| `unauthorized_verification` | presents an unauthorized `verifier_id` | quantum channel | authorization membership test |
| `replay` | re-presents an identical valid transcript (changes nothing) | everything | in-memory nonce/session ledger (cross-event state) |

> **Do not assume quantum mismatch detects everything.** Measured on the committed reference
> benchmark, the quantum statistic detects the two channel attacks at rate **1.0 (FAR 0.0)** and
> detects the four protocol attacks at rate **0.0 (FAR 1.0)** — the latter are the responsibility
> of classical controls.

---

## 10. Observable Evidence

**GROUND TRUTH** is what the simulator used: `is_malicious`, `attack_type`, `attack_fraction`,
noise settings, seed, and `scenario_id` (which encodes the fraction). **OBSERVABLE EVIDENCE** is
what a legitimate verifier could see: per-state basis / expected bit / `probability_expected` /
`matched`, mismatch counts, basis counts, mean channel disturbance, verification flags and
authorization observations.

The detector **must not** receive attack labels, attack fractions, or simulator-only hidden
metadata — otherwise it could "cheat" instead of detecting. The architecture preserves this
separation and it is enforced by tests in three ways:

- **Structural** — the detector's input type has no attack/noise/seed field at all.
- **Static** — an AST scan forbids `backend.detection` from importing `backend.attacks`,
  `backend.noise` or `backend.simulation`, and from naming ground-truth identifiers.
- **Runtime + behavioural** — a fresh interpreter importing the detector leaves those modules
  unloaded; and two scenarios with byte-identical observables but different ground truth must
  produce identical detector output.

---

## 11. Detection Engine

The detector is **deterministic, model-based statistical consistency detection** — not machine
learning.

- **Primary statistic** — the empirical verification mismatch rate `D_m = N_mismatch / N_valid`,
  tested against a calibrated threshold. Malformed records are excluded from the denominator; a
  zero denominator yields *undefined*, not zero.
- **Fidelity / projective match** — per state `F = p_match = probability_expected`; the mean
  fidelity **is** the mean projective match probability (one quantity, reported once).
- **Basis-wise evidence** — per-basis counts, distributions and mismatch rates (diagnostic).
- **Transcript / integrity evidence** — the detector recomputes the transcript hash, binding,
  protocol version, session addressing, state counts and declared-vs-derived sequence; it trusts
  none of them from the transcript.
- **Authorization evidence** — a membership test on declared signer/verifier identities
  (explicitly *not* proof of identity).
- **Replay evidence** — a pure membership test against the in-memory consumed-identity ledger.
- **Decision logic** — categorical, not a score: findings group into integrity / authorization /
  quantum families and the overall status is `CLEAR`, a single-family violation, or
  `MULTIPLE_FINDINGS`. There is **no security score** and no cause attribution ("noise and
  undetectable manipulation produce identical observations").

Every reported rate carries an exact Clopper–Pearson binomial interval, because `1/8` and
`1000/8000` are the same number but very different evidence.

---

## 12. Statistical Calibration

- **Honest reference data** — calibration consumes honest-only sessions; the role is enforced at
  the configuration type.
- **Null model** — `H0: N_mismatch ~ Binomial(N, p0)`, with `p0 = eta/2` for depolarizing `eta`.
- **Clopper–Pearson (implemented)** — exact binomial inversion via the Beta quantile; conservative,
  never anti-conservative.
- **Hoeffding (implemented)** — `epsilon = sqrt(ln(m/alpha) / (2n))`, used only as a *cross-check*
  (uniformly looser); it never sets the threshold.
- **alpha** — reference `alpha = 0.05`, **split** (not doubled) into `calibration_alpha = 0.025`
  and `evaluation_alpha = 0.025`.
- **Threshold derivation** — `p_upper` = one-sided Clopper–Pearson upper bound on the honest
  pooled rate; `k_crit(N) = min{k : P[Binom(N, p_upper) <= k] >= 1 - alpha_eval}`;
  `theta(N) = k_crit / N`; reject when `N_mismatch > k_crit`.
- **Sample-size dependence** — the threshold is valid only at the sample size, measurement mode,
  shot count and channel it was derived for; applying it elsewhere raises an error.
- **Calibration / evaluation split** — disjoint seed blocks with an explicit disjointness
  assertion.
- **Multiple-comparison policy** — exactly **one** primary test (`SINGLE_PRIMARY_WITH_DIAGNOSTICS`);
  Holm–Bonferroni is implemented but deliberately unused ("with one test there is no family to
  correct for").

**Reference operating point** (from the committed artifact `benchmarks/m5-reference.json`):
`N = 500`, `sampled`, 1 shot/state, depolarizing `eta = 0.02`, `alpha = 0.05`, 120 calibration
sessions (seeds 0–119), pooled rate `0.010`, `p_upper = 0.010828629491245854`, `k_crit = 10`,
`theta = 0.02`, observed calibration FRR `0.0`.

---

## 13. Evaluation and Benchmarks

- **Profiles** — `smoke` (seconds; "every number is too small to interpret") and `reference`
  (minutes; synchronous). Reproduced by `benchmarks/run_reference_benchmark.py`, which writes the
  committed `m5-reference.json` / `.md`.
- **Attack populations** — six attack types; the two fractional attacks receive a non-zero
  fraction, the four protocol attacks use fraction 0.
- **Metrics** — positive class is "the decision **rejected** the session"; FAR / FRR / detection
  rate / specificity plus descriptive precision/recall/F1/accuracy. Undefined rates are `None`,
  never `0.0`. ROC/PR curves are deliberately **not** produced.
- **Reproducibility** — session ids, nonces and timestamps derived deterministically from each
  trial seed; disjoint seed blocks; a transpile cache (compiled circuits only, never outcomes).
- **Sample-size analysis, robustness, discrimination** — per-size recalibration over
  `N = 100…2500` (5000/10000 declared but not simulated: above the 4096 protocol cap); a
  noise-level robustness grid; and a matched-marginals discrimination experiment.

**Measured results (committed artifact, 12 trials per attack):**

| Attack | detection_rate | FAR |
|---|---|---|
| intercept_resend (fraction 0.2) | 1.0 | 0.0 |
| channel_tampering (fraction 0.2) | 1.0 | 0.0 |
| forgery / impersonation / unauthorized_verification / replay | 0.0 | 1.0 |

Honest FRR by noise: `0.0` (none/low/medium), `1.0` (high, `eta = 0.10`) — i.e. the operating
point is conditional on its calibrated channel. Reference run provenance: runtime
`1504.86 s`, 479 scenarios, cache hit-rate `0.99998`.

---

## 14. Security Interpretation

- **Assumptions** — a 14-entry register, each with status `exact / satisfied / approximate /
  not-verified / violated` and a consequence-if-violated. "Approximate" is *not* a synonym for
  "satisfied".
- **Observability** — a per-threat matrix recording quantum disturbance, detector visibility,
  whether a classical control is required, and measured detection/FAR.
- **Finite-size interpretation** — finite-size quantities are confidence intervals, classification
  thresholds and empirical acceptance rates. A fourth kind, "formal cryptographic security bound",
  is explicitly **not produced**; constructing one labelled as such raises an error.
- **Composition** — per-component assessments; `formal_composition_theorem_present = False`.
- **Claim checker** — an in-repo guard that rejects forbidden claims ("information-theoretically
  secure", "formal forgery bound", "detects all quantum attacks", "the threshold is optimal",
  "FAR is the forgery probability") and banned terminology (e.g. "decoy"/"decoy-state").

**Demonstrated experimentally:** honest FRR at/below alpha at the calibrated channel; detection of
the two channel attacks; non-detection of the four protocol attacks by the quantum statistic;
robustness and sample-size behaviour. **Not proven:** unforgeability, non-repudiation,
transferability, any forgery bound, information-theoretic/composable security, adaptive-attack
resistance, hardware behaviour, or generalisation beyond the reference configuration.

---

## 15. Limitations

These are intentional scope boundaries of a research prototype, not bugs.

| Limitation | Note |
|---|---|
| Simulation-only validation | No quantum hardware; Aer simulator only |
| No formal QDS security proof | Reference construction, not a proven scheme |
| No formal forgery bound | No secret key, no forgery game |
| No universal attack coverage | Six attack families modelled |
| No coherent / adaptive adversary | Individual attacks only; no quantum memory |
| Classical identity / replay controls | Membership test + in-memory ledger; lost on restart |
| Sample-size-dependent thresholds | Invalid at another N / mode / channel |
| Finite-shot stochastic behaviour | Sampled outcomes vary with shot count |
| Noise/attack discrimination limits | intercept–resend @0.05 not separable from honest noise at matched marginals |
| No formal composition theorem | Components assessed, not composed |

---

## 16. Frontend

The console is **React 18 + TypeScript + Vite** with recharts and a single permanent dark theme.
Navigation is state-based (no router library): a `FrontPage` gate, then a seven-view workspace.

| Page | Purpose | What you do | Backend capability used |
|---|---|---|---|
| Dashboard (`Console`) | Operational overview | Read readiness, counts, reference operating point, empirical detection/FAR | `GET /api/v1/sessions`, `/calibration/reference`, `/security/observability`, `/health`, `/ready`, `/version` |
| Session Studio | Drive the signing lifecycle | Create → Sign → Verify → Expire a session | `POST/GET /api/v1/sessions`, `/{id}/sign`, `/{id}/expire`, `POST /api/v1/verify` |
| Simulation Bench | Build a noise/attack scenario | Set noise + attack, run, inspect per-state probabilities | `POST /api/v1/simulations` (or `/simulations/evaluation`) |
| Detection Console | Run the detector | Paste/accept observable evidence, run | `POST /api/v1/detect` |
| Calibration Lab | Derive an honest-only threshold | Configure and run a calibration | `POST /api/v1/calibration/run`, `GET /calibration/{id}`, `/calibration/reference` |
| Evaluation Center | Benchmark the detector | Run smoke/reference profile, inspect metrics | `POST /api/v1/evaluation/run`, `GET /evaluation/{id}`, `/artifact` |
| Security Argument | Read the security posture | Browse assumptions / observability / composition; test the claim checker | `GET /api/v1/security/*`, `POST /api/v1/security/analyze` |

**Normal demo sequence:** Session → Simulation → Detection → Calibration → Evaluation → Security
Argument. Simulation Bench offers a "Send observable data to detector" handoff that carries
**only observable fields, never ground truth**.

---

## 17. Technology Stack

Verified from `requirements.txt` and `frontend/package.json`.

| Layer | Technology | Version |
|---|---|---|
| Language | Python (CPython) | 3.13.5 |
| Quantum SDK | Qiskit | 2.5.2 |
| Simulator | Qiskit-Aer | 0.17.2 |
| Numerics | NumPy | 2.5.3 |
| Scientific | SciPy | 1.18.1 |
| Symbolic | SymPy | 1.14.0 |
| Tests (backend) | pytest | 9.1.1 |
| Web framework | FastAPI | 0.141.1 |
| ASGI toolkit | starlette | 1.6.0 |
| Validation | pydantic | 2.13.5 |
| Server | uvicorn | 0.53.0 |
| Async | anyio | 4.14.2 |
| Test HTTP | httpx2 | 2.12.0 |
| UI | React / react-dom | ^18.3.1 |
| UI language | TypeScript | ^5.7.2 |
| Build | Vite | ^5.4.11 |
| Charts | recharts | ^2.15.0 |
| Icons | lucide-react | ^0.469.0 |
| Frontend tests | vitest | ^3.2.7 |

No machine-learning dependency is present, by design.

---

## 18. Repository Structure

```
backend/
  quantum/      # M1: eigenstates, Bell, teleportation, correction, density, measure, cache
  protocol/     # M2: binding, canonical, encoding, session, signer, verifier, transcript
  noise/        # honest Pauli channels
  attacks/      # M3: six attack models + observable/ground-truth split
  simulation/   # M3: scenario, seed, runner, results
  detection/    # M4: features, mismatch, fidelity, disturbance, consistency, auth, replay, engine
  calibration/  # M5: baseline, confidence, thresholds, multiple_testing, operating_points
  evaluation/   # M5: benchmark, harness, datasets, metrics, curves, robustness, discrimination
  security/     # M6: assumptions, observability, composition, finite_size, interpretation
  api/          # M7: FastAPI app factory, routes/, schemas/, services/, store
frontend/       # M8: React/TS/Vite console (src/pages, components, api, state, lib)
tests/          # mirrors backend packages + api integration/wiring suites
docs/           # api/, protocol/, security/, research/ (incl. SIH26141.pdf, references.md)
benchmarks/     # m5-reference.json, m5-reference.md, run_reference_benchmark.py
pyproject.toml  # project metadata + pytest configuration
requirements.txt# pinned backend dependencies
```

---

## 19. Installation (Windows-first)

Prerequisite: **Python 3.13** on `PATH`.

```powershell
# 1. clone and enter
git clone <this-repository>
cd SIH26141

# 2. create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate

# 3. install backend dependencies (pinned in requirements.txt)
pip install -r requirements.txt

# 4. install frontend dependencies
cd frontend
npm install
cd ..
```

Dependencies are pinned in `requirements.txt` (backend) and `frontend/package.json` (frontend);
`pyproject.toml` carries project metadata and pytest configuration only.

---

## 20. Run the Backend

```powershell
.venv\Scripts\activate
uvicorn backend.api.app:create_app --factory --reload --port 8000
```

(Equivalent: `python -m uvicorn backend.api.app:create_app --factory --reload --port 8000`.)

- **Base URL:** `http://127.0.0.1:8000`
- **Operational routes (at ROOT, not under /api/v1):**
  - `GET /health` — liveness + versions + in-memory counts
  - `GET /ready` — component-import + store readiness probe
  - `GET /version` — version inventory
- **Interactive API docs (Swagger):** `http://127.0.0.1:8000/docs` (ReDoc at `/redoc`,
  OpenAPI JSON at `/openapi.json`)

> Do **not** call `/api/v1/health` — operational routes are unversioned at the root by design.

---

## 21. Run the Frontend

```powershell
cd frontend
npm install
npm run dev
```

- **Local URL:** `http://localhost:5173` (whitelisted by the backend CORS default).
- **API base URL:** configured via `frontend/.env` — copy `frontend/.env.example`:

  ```
  VITE_API_BASE_URL=http://127.0.0.1:8000
  ```

- The console calls operational endpoints at the root and business endpoints under `/api/v1`.
  If the backend is offline the FrontPage still renders; the connection probe reports offline.

---

## 22. API Overview

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Liveness + versions + counts |
| GET | `/ready` | Readiness probe |
| GET | `/version` | Version inventory |
| POST | `/api/v1/sessions` | Create a signing session |
| GET | `/api/v1/sessions` | List sessions |
| GET | `/api/v1/sessions/{id}` | Fetch a session |
| POST | `/api/v1/sessions/{id}/sign` | Sign → transcript + hash |
| POST | `/api/v1/sessions/{id}/expire` | Expire a session |
| POST | `/api/v1/verify` | Verify a transcript |
| POST | `/api/v1/simulations` | Run a scenario (observable only) |
| POST | `/api/v1/simulations/evaluation` | Run a scenario (includes ground truth) |
| POST | `/api/v1/detect` | Run the detector on observable evidence |
| POST | `/api/v1/calibration/run` | Derive an honest-only threshold |
| GET | `/api/v1/calibration/reference` | Reference methodology + operating point |
| GET | `/api/v1/calibration/{id}` | Retrieve a calibration |
| POST | `/api/v1/evaluation/run` | Run a benchmark profile |
| GET | `/api/v1/evaluation/{id}` | Retrieve an evaluation summary |
| GET | `/api/v1/evaluation/{id}/artifact` | Retrieve the full artifact |
| GET | `/api/v1/security/assumptions` | Assumption register |
| GET | `/api/v1/security/observability` | Threat-observability matrix |
| GET | `/api/v1/security/composition` | Composition assessment |
| POST | `/api/v1/security/analyze` | Claim checker |

Errors use a universal envelope `{ "error": { code, message, request_id, details } }` with status
codes 400 / 404 / 409 / 413 / 422 / 500.

---

## 23. Quick Demo (5–10 minutes)

1. **Session Studio** — create a session: message `transfer 100 units to account 7`, signer
   `alice`, verifier `bob`, `state_count` 16. Click **Sign**, then **Verify**. *Show:* the
   transcript + `transcript_hash`, and verification accepted with the structural caveat. *Say:*
   "verification is consistency and binding, not unforgeability — there is no secret key."
2. **Simulation Bench (honest)** — `sampled`, `shot_count` 1, noise `depolarizing` strength
   `0.02`, attack `none`. Run. *Show:* per-state `P(expected) ≈ 0.99`, small mismatch count.
3. **Simulation Bench (channel tampering)** — same, but attack `channel_tampering`, fraction
   `0.2`. Run. *Show:* targeted states drop to `P(expected) = 0`; mismatch rises.
4. **Detection Console** — use "Send observable data to detector", run. *Show:* honest → clear /
   low; tampered → a quantum-family finding with observed-vs-expected evidence and a confidence
   interval. *Say:* "the detector saw only observable evidence — no attack label was passed."
5. **Calibration Lab** — run a small honest calibration. *Show:* `k_crit`, `p_upper`, `theta` and
   the sample-size validity warning.
6. **Evaluation Center** — run the `smoke` profile. *Show:* per-attack bars and confusion
   matrices. *Say:* "smoke numbers are too small to interpret; the committed reference artifact is
   the citable result."
7. **Security Argument** — open the Claim Checker and submit "The system is 100% secure against
   all attacks." *Show:* it is rejected as FORBIDDEN, while an honest empirical sentence is
   ALLOWED.

---

## 24. Example Scenarios

Payloads conform to the current `SimulationRequest` schema
(`backend/api/schemas/simulation.py`). `fraction` must be `0` for non-fractional attacks.

<details>
<summary>Honest / no attack</summary>

```json
{
  "scenario_id": "honest-demo",
  "message": "transfer 100 units to account 7",
  "signer_id": "alice",
  "verifier_id": "bob",
  "state_count": 16,
  "shot_count": 1,
  "random_seed": 7,
  "measurement_mode": "sampled",
  "noise": { "noise_type": "depolarizing", "noise_strength": 0.02 },
  "attack": { "attack_type": "none", "fraction": 0.0, "seed": 0 }
}
```
</details>

<details>
<summary>Channel tampering (quantum-channel attack)</summary>

```json
{
  "scenario_id": "tamper-demo",
  "message": "transfer 100 units to account 7",
  "signer_id": "alice",
  "verifier_id": "bob",
  "state_count": 16,
  "shot_count": 1,
  "random_seed": 7,
  "measurement_mode": "sampled",
  "noise": { "noise_type": "depolarizing", "noise_strength": 0.02 },
  "attack": { "attack_type": "channel_tampering", "fraction": 0.2, "seed": 3,
              "parameters": { "pauli": "X" } }
}
```
</details>

<details>
<summary>Intercept–resend (quantum-channel attack)</summary>

```json
{
  "scenario_id": "ir-demo",
  "message": "transfer 100 units to account 7",
  "signer_id": "alice",
  "verifier_id": "bob",
  "state_count": 16,
  "shot_count": 1,
  "random_seed": 7,
  "measurement_mode": "sampled",
  "noise": { "noise_type": "none", "noise_strength": 0.0 },
  "attack": { "attack_type": "intercept_resend", "fraction": 0.5, "seed": 3,
              "parameters": { "eve_basis": "random" } }
}
```
</details>

<details>
<summary>Impersonation / replay (classical protocol attacks)</summary>

```json
{
  "scenario_id": "impersonation-demo",
  "message": "transfer 100 units to account 7",
  "signer_id": "alice",
  "verifier_id": "bob",
  "state_count": 16,
  "shot_count": 1,
  "random_seed": 7,
  "measurement_mode": "sampled",
  "noise": { "noise_type": "none", "noise_strength": 0.0 },
  "attack": { "attack_type": "impersonation", "fraction": 0.0, "seed": 0,
              "parameters": { "presented_signer": "eve" } }
}
```

```json
{
  "scenario_id": "replay-demo",
  "message": "transfer 100 units to account 7",
  "signer_id": "alice",
  "verifier_id": "bob",
  "state_count": 16,
  "shot_count": 1,
  "random_seed": 7,
  "measurement_mode": "sampled",
  "noise": { "noise_type": "none", "noise_strength": 0.0 },
  "attack": { "attack_type": "replay", "fraction": 0.0, "seed": 0,
              "parameters": { "mode": "re_present" } }
}
```
</details>

---

## 25. Testing

- **Framework:** pytest (backend), vitest (frontend).
- **Layout:** `tests/{quantum, protocol, detection, calibration, evaluation, security, api}`
  mirror the backend packages.
- **Run everything:** `pytest -q`  ·  **API suite only:** `pytest tests/api -q`
- **Frontend:** `cd frontend && npm test`
- **Guard tests:** architecture/layering guards per package; detection label-independence
  (structural + static AST + runtime + behavioural); calibration/evaluation role and seed-block
  disjointness; reproducibility (determinism and transpile-cache neutrality).
- **Warnings-as-errors:** not configured in `pyproject.toml` (no `-W error` policy).
- **Mutation testing:** not present in this repository.
- **Counts (measured on this checkout):** 1,546 backend test functions; 1,848 collected in the
  project venv *excluding* the API suite (httpx absent at measurement time); 31 frontend vitest
  tests passing. Coverage is not configured.

---

## 26. Performance / Reproducibility

- **Seeds** — a domain-separated SHA-256 KDF derives per-component sub-seeds from one master seed;
  identical `(circuit, shots, seed)` triples reproduce identical Aer counts.
- **Profiles** — `smoke` and `reference`; the reference profile is reproduced by
  `benchmarks/run_reference_benchmark.py`.
- **Runtime (actual artifact)** — reference run: `1504.86 s`, 479 scenarios, Python 3.13.5.
- **Cache** — an opt-in transpilation cache stores compiled circuits only (never outcomes);
  reference-run hit-rate `0.99998`; the benchmark leaves it disabled afterwards.
- No runtime or performance figure in this project is estimated or extrapolated.

---

## 27. Security and Research Integrity

**What Q-TRACE demonstrates**

- Correct, reproducible quantum primitives (eigenstates, `|Phi+>`, teleportation with
  feed-forward, Born-rule measurement).
- `p_match == F` for a pure expected state (one overlap quantity, reported once).
- Label-free detection enforced structurally, statically and behaviourally.
- Exact finite-sample calibration and an honest-null, sample-size-specific threshold.
- Detection of the two quantum-channel attacks at rate 1.0 / FAR 0.0 at the reference
  configuration, and honest non-detection of the four protocol attacks by the quantum statistic.

**What Q-TRACE does NOT claim**

- No formal QDS / information-theoretic security.
- No universal security and no universal attack detection.
- No formal forgery bound or forgery probability.
- No cryptographic guarantees beyond what the implementation establishes (binding + structural
  integrity; no unforgeability).
- No hardware validation; no official/standardised QDS protocol status.

Empirical benchmark results are **configuration-dependent** (sample size, measurement mode, shot
count, channel) and do not transfer to other configurations.

---

## 28. Research Background

- **Quantum teleportation** — Bennett et al. (1993): teleport an unknown qubit with one EPR pair
  and two classical bits. Q-TRACE implements exactly this primitive in simulation.
- **QDS** — memory-free and QKD-component QDS literature (Dunjko–Wallden–Andersson 2014; Collins
  et al. 2014; Wallden et al. 2015) motivates the design; no security claim is transferred.
- **Quantum-safe / classical signature context** — Shor's algorithm threatens RSA/DSA/ECDSA; this
  is background motivation only (none implemented here).
- **Finite-sample statistics** — Clopper–Pearson (1934), Hoeffding (1963), Holm (1979): statements
  about estimators, not about adversaries.

---

## 29. References

Primary bibliography is the repository's own (`docs/research/references.md`):

- [R1] Bennett et al., "Teleporting an Unknown Quantum State…", PRL 70, 1895 (1993).
- [R2] Dunjko, Wallden, Andersson, "QDS without Quantum Memory", PRL 112, 040502 (2014).
- [R3] Collins et al., "Realization of QDS without… Quantum Memory", PRL 113, 040502 (2014).
- [R4]/[R10] Wallden, Dunjko, Kent, Andersson, "QDS with QKD Components", PRA 91, 042304 (2015).
- [R8] Egreen Quanta LLP, SIH Problem Statement 26141 (`docs/research/SIH26141.pdf`).
- [R9] Consensus Research Synthesis (`docs/research/consensus-research.md`).
- [R11] Hoeffding, JASA 58(301), 13 (1963).
- [R12] Clopper & Pearson, Biometrika 26(4), 404 (1934).
- [R13] Holm, Scand. J. Statist. 6(2), 65 (1979).

Full citations and DOIs are in `docs/research/references.md`.

---

## 30. Contributing / Development

- **Branches** — work happens on `milestone-*` branches (e.g. `milestone-6-security-analysis`,
  `milestone-7-backend-api`) merged into `main` via pull requests; follow the same pattern.
- **Tests** — run `pytest -q` (and `npm test` in `frontend/`) before proposing a change; add
  tests next to the layer you touch.
- **Code organization** — respect the one-way dependency stack; keep each milestone's concerns in
  its own package.
- **No backend/domain leakage** — `backend.api` must not import Qiskit; services delegate to
  domain entry points.
- **No hidden ground truth in detection** — never add an attack/noise/label field to detector
  input; the separation tests will (and should) fail.

---

## 31. License

The repository contains a `LICENSE` file, but it is **currently empty (0 bytes)** — no license
terms have been populated yet. Until it is filled in, no license is granted by this repository;
treat the code as all-rights-reserved and contact the maintainers before reuse. (This README
reports the file's actual state rather than guessing a license.)
