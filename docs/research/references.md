# SIH26141 — Research References

This document contains the primary research papers, security literature, and
technical documentation used in the design and implementation of the
SIH26141 Quantum-Inspired Cyber Threat Detection Framework.

The project distinguishes between:
- established results from the literature,
- implementation/documentation references,
- and engineering choices made specifically for this prototype.

---

## 1. Foundational Quantum Information

### [R1] Quantum Teleportation

C. H. Bennett, G. Brassard, C. Crépeau, R. Jozsa, A. Peres, and W. K. Wootters,
"Teleporting an Unknown Quantum State via Dual Classical and Einstein-Podolsky-Rosen Channels,"
Physical Review Letters, 70, 1895–1899 (1993).

DOI:
https://doi.org/10.1103/PhysRevLett.70.1895

Use in project:
- Fundamental quantum teleportation protocol.
- Bell-state entanglement.
- Bell measurement and classical correction.

---

### [R2] Quantum Digital Signatures without Quantum Memory

V. Dunjko, P. Wallden, and E. Andersson,
"Quantum Digital Signatures without Quantum Memory,"
Physical Review Letters, 112, 040502 (2014).

DOI:
https://doi.org/10.1103/PhysRevLett.112.040502

Use in project:
- Practical QDS design principles.
- Forgery and repudiation security.
- No-long-term-quantum-memory QDS architecture.
- Security assumptions and verification concepts.

---

### [R3] Experimental Realization of QDS without Quantum Memory

R. J. Collins, R. J. Donaldson, V. Dunjko, P. Wallden, P. J. Clarke,
E. Andersson, J. Jeffers, and G. S. Buller,
"Realization of Quantum Digital Signatures without the Requirement of Quantum Memory,"
Physical Review Letters, 113, 040502 (2014).

DOI:
https://doi.org/10.1103/PhysRevLett.113.040502

Use in project:
- Experimental/practical QDS realization.
- Nonorthogonal-state-based forgery resistance.
- Practical QDS implementation considerations.

---

### [R4] QDS Using QKD Components

P. Wallden, V. Dunjko, A. Kent, and E. Andersson,
"Quantum Digital Signatures with Quantum-Key-Distribution Components,"
Physical Review A, 91, 042304 (2015).

DOI:
https://doi.org/10.1103/PhysRevA.91.042304

Use in project:
- QKD-assisted QDS architecture.
- Security analysis.
- Forging probabilities.
- Practical implementation constraints.
- Finite-size considerations.

---

## 2. Quantum Teleportation and Qiskit Implementation

### [R5] IBM Quantum — Quantum Teleportation

IBM Quantum Learning,
"Quantum Teleportation."

URL:
https://quantum.cloud.ibm.com/learning/en/modules/computer-science/quantum-teleportation

Use in project:
- Current Qiskit teleportation implementation.
- Three-qubit circuit construction.
- Bell-pair preparation.
- Bell measurement.
- Classical feed-forward.
- Simulation workflow.

---

### [R6] Qiskit Quantum Teleportation Course

IBM Quantum,
"Quantum Teleportation — Basics of Quantum Information."

URL:
https://qiskit.qotlabs.org/learning/courses/basics-of-quantum-information/entanglement-in-action/quantum-teleportation

Use in project:
- Mathematical/circuit interpretation of teleportation.
- Bell-state conventions.
- Alice/Bob qubit assignment.
- Current Qiskit implementation guidance.

---

### [R7] Qiskit SDK Documentation

IBM Quantum,
"Qiskit SDK API Documentation."

URL:
https://docs.quantum.ibm.com/api/qiskit

Use in project:
- QuantumCircuit API.
- Quantum information primitives.
- Measurement and circuit construction.
- Version-specific implementation reference.

---

## 3. Project-Specific Research Inputs

### [R8] Official SIH26141 Problem Specification

Egreen Quanta LLP,
"Quantum-Inspired Cyber Threat Detection for Digital Signature Security,"
Smart India Hackathon Problem Statement 26141.

Local project file:
docs/research/SIH26141.pdf

Use in project:
- Authoritative project requirements.
- Required mathematical model.
- Bell-state entanglement.
- Quantum teleportation.
- Pauli corrections.
- Projective measurements.
- Threat detection.
- Attack simulation.
- Performance evaluation.
- Expected software deliverables.

---

### [R9] Consensus Research Synthesis

Project research synthesis prepared for SIH26141.

Local project file:
docs/research/consensus-research.md

Use in project:
- Literature mapping.
- Threat-model synthesis.
- Non-ML detection strategy.
- Candidate detection statistics.
- Finite-size analysis direction.
- Benchmarking methodology.
- Research gaps.

NOTE:
Claims from this synthesis must be traced back to primary literature before
being treated as established scientific facts.

---

## 4. Statistical Detection / Security Methodology

### [R10] Finite-Size QDS Security Analysis

*Same paper as [R4]* — P. Wallden, V. Dunjko, A. Kent, and E. Andersson,
"Quantum Digital Signatures with Quantum-Key-Distribution Components,"
Physical Review A, 91, 042304 (2015).

DOI:
https://doi.org/10.1103/PhysRevA.91.042304

Use in project:
- Finite-size security reasoning.
- Forgery probability analysis.
- Statistical parameter estimation.

Cited here under a second number because it is used for a second purpose (the
finite-size reasoning, rather than the architecture). It is one paper, not two.

---

### Note on claims that are *not* transferred

Several results in this bibliography are adjacent to the project rather than
directly about it, and the project deliberately transfers no security claim from
them.

- **[R1] teleportation.** Establishes that the teleportation primitive works and
  what the Pauli corrections must be. It says nothing about forgery or about
  detecting a disturbed channel, and nothing of the kind is inferred from it.
- **[R5]–[R7] implementation references.** Establish how to build and simulate
  the circuits. A simulator is not a proof of information-theoretic security, and
  no security property is read out of the implementation.
- **[R2], [R3], [R4]/[R10] QDS papers.** Establish that the QDS construction and
  its security analysis are sound in their own settings, with their own
  assumptions. **No forgery probability, no security parameter and no
  composability claim is transferred from them to this reference prototype.**
  [R10] is cited for its *method* of reasoning about finite samples, not as a
  bound that transfers.
- **[R11]–[R13] statistical references.** Establish the validity of the interval,
  the concentration bound and the multiple-testing correction used here. They are
  statements about estimators, not about adversaries, and the project states that
  distinction wherever the numbers appear.

Consequently this milestone derives **no formal forgery bound**. The empirical
acceptance rates it reports are measurements of one fixed rule on modelled
attacks, and they are labelled as such.

---

### [R11] Statistical Thresholding — Concentration Bound

W. Hoeffding,
"Probability Inequalities for Sums of Bounded Random Variables,"
Journal of the American Statistical Association, 58(301), 13–30 (1963).

DOI:
https://doi.org/10.1080/01621459.1963.10500830

JSTOR:
https://www.jstor.org/stable/2282952

Use in project:
- The one-sided and two-sided Hoeffding bounds used by
  `backend/security/finite_size.py`.
- A distribution-free concentration radius for the honest mismatch rate, used as
  a *sanity* bound alongside the exact interval rather than instead of it.

Assumptions this bound requires (stated in code and in the methodology docs):
- the observations are independent;
- each observation is bounded in an interval of known width (here `[0, 1]`,
  because each state contributes a Bernoulli mismatch indicator);
- the sample size is fixed in advance and not chosen after seeing the data.

Scope limit recorded in the project:
- The Hoeffding radius is a statement about estimating the honest mismatch
  probability. It is **not** a cryptographic security parameter, and the project
  never presents it as one. It is also looser than the exact Clopper-Pearson
  interval, which is why Clopper-Pearson is the reference interval and Hoeffding
  is reported for comparison.

---

### [R12] Exact Binomial Confidence Interval

C. J. Clopper and E. S. Pearson,
"The Use of Confidence or Fiducial Limits Illustrated in the Case of the Binomial,"
Biometrika, 26(4), 404–413 (1934).

DOI:
https://doi.org/10.1093/biomet/26.4.404

JSTOR:
https://www.jstor.org/stable/2331986

Use in project:
- The reference confidence interval for the honest mismatch probability, in
  `backend/calibration/confidence.py` and `backend/security/finite_size.py`.
- One-sided and two-sided intervals, computed from the Beta quantile function
  exactly as the paper's inversion prescribes.

Assumptions this interval requires:
- the mismatch count is Binomial with a fixed number of independent trials of
  equal probability. For the depolarizing channel the per-state mismatch
  probability is identical across the six signature states, so this holds
  exactly; for the bit-flip, phase-flip and bit-phase-flip channels it is only
  approximately true, and the project records that as an APPROXIMATE assumption
  rather than an EXACT one.

Scope limit recorded in the project:
- The interval describes an unknown parameter. It is not a decision rule, and it
  is not a security bound; the threshold derived from it is a separate object.

---

### [R13] Multiple-Comparison Correction

S. Holm,
"A Simple Sequentially Rejective Multiple Test Procedure,"
Scandinavian Journal of Statistics, 6(2), 65–70 (1979).

JSTOR:
https://www.jstor.org/stable/4615733

Use in project:
- The step-down correction implemented in
  `backend/calibration/multiple_testing.py`.
- It is implemented and tested so that the alternative policy can be reasoned
  about, and it is **not used** by the reference operating point. The reference
  policy performs one test and reports everything else as diagnostic evidence,
  which is why no family-wise claim is made in the report.

Rationale recorded in the project:
- Running several independent tests at `alpha = 0.05` and reporting the result as
  a 5% error rate inflates the family-wise error rate. The reference policy
  avoids the inflation by construction rather than by correction. Where a
  corrected family is genuinely required, the policy object supports it and names
  the correction explicitly.

---

## 5. Reference Policy

The project follows these rules:

1. Primary research papers are preferred over secondary summaries.
2. Security claims must be supported by the paper actually cited.
3. A simulator is not itself a proof of information-theoretic security.
4. Engineering decisions specific to this prototype must be identified as such.
5. Qiskit implementation details should follow current official documentation.
6. Experimental benchmark values must come from our own reproducible simulations,
   not copied from literature.
7. No machine-learning method is used as the primary threat detector.

---

## 6. Reference Status

Legend:

FOUNDATIONAL
    Established theoretical foundation.

PRIMARY QDS
    Directly relevant to quantum digital signatures.

IMPLEMENTATION
    Used to implement or validate the software.

SECURITY / STATISTICS
    Used for threshold, finite-size, or security analysis.

PROJECT SOURCE
    Official SIH or project-specific material.