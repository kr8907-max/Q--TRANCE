# Quantum Core — Mathematical Documentation (Milestone 1)

Scope: this document describes **only** the quantum-mechanical layer built in
Milestone 1. It is the foundation for the later *reference prototype*
construction. It makes **no** QDS security claim of any kind.

---

## 1. Single-qubit states

A pure single-qubit state is a unit vector in `C^2`:

    |psi> = alpha|0> + beta|1>,      |alpha|^2 + |beta|^2 = 1

Two vectors differing only by a unit-modulus scalar represent the same
physical state, so all eigenvalue assertions are phrased as `P|psi> = lambda|psi>`
rather than as amplitude comparisons.

### 1.1 Pauli operators

    I = [[1, 0], [0, 1]]     X = [[0, 1], [1, 0]]
    Y = [[0, -i], [i, 0]]    Z = [[1, 0], [0, -1]]

All four are Hermitian and unitary, and `X^2 = Y^2 = Z^2 = I`,
`XY = iZ`, `YZ = iX`, `ZX = iY` (cyclic).

### 1.2 The six Pauli eigenstates

| Ket | Vector | Operator | Eigenvalue |
|---|---|---|---|
| `|0>` | `(1, 0)^T` | `Z` | `+1` |
| `|1>` | `(0, 1)^T` | `Z` | `-1` |
| `|+>` | `(1, 1)^T / sqrt(2)` | `X` | `+1` |
| `|->` | `(1, -1)^T / sqrt(2)` | `X` | `-1` |
| `|+i>` | `(1, +i)^T / sqrt(2)` | `Y` | `+1` |
| `|-i>` | `(1, -i)^T / sqrt(2)` | `Y` | `-1` |

Properties used by the test suite:

* every state is normalized;
* `P|psi> = lambda|psi>` exactly, for the declared `P` and `lambda`;
* `<psi|Q|psi> = 0` for the two Pauli operators `Q != P`;
* states within one basis are orthogonal (`<0|1> = 0`, etc.);
* states across bases have `|<psi|phi>| = 1/sqrt(2)`, i.e. they are
  non-orthogonal. This non-orthogonality is the resource the later protocol
  layer will draw on.

---

## 2. The Bell state `|Phi+>`

    |Phi+> = (|00> + |11>) / sqrt(2)

Preparation circuit, on qubits `q_a` (control) and `q_b` (target):

    H(q_a)          ->  (|0> + |1>)|0> / sqrt(2)
    CX(q_a -> q_b)  ->  (|00> + |11>) / sqrt(2)

Verified properties:

* amplitudes are exactly `(1/sqrt(2), 0, 0, 1/sqrt(2))` in the computational
  basis, i.e. no cross terms;
* the state is normalized, `Tr(rho) = 1`, and pure, `Tr(rho^2) = 1`;
* the single-qubit reduced state is maximally mixed,
  `rho_A = Tr_B rho = I/2`, with purity `1/2`;
* the state does not factorise: `rho != rho_A (x) rho_B`.

---

## 3. Quantum teleportation

### 3.1 Qubit assignment

| Qubit | Role |
|---|---|
| `q0` | input / secret state `|psi>` |
| `q1` | Alice's half of the Bell pair |
| `q2` | Bob's half of the Bell pair (receives the correction) |

Classical bits: `c0` carries Alice's outcome on `q0` (call it `m0`),
`c1` carries her outcome on `q1` (call it `m1`), `c2` carries Bob's optional
final measurement.

### 3.2 Circuit

1. prepare `|psi>` on `q0`
2. `H(q1)`, `CX(q1, q2)` — create `|Phi+>` on `(q1, q2)`
3. `CX(q0, q1)`, `H(q0)` — rotate into the Bell basis
4. measure `q0 -> c0`, `q1 -> c1`
5. apply the Pauli correction to `q2` (Section 4)
6. optionally rotate `q2` into a chosen basis and measure it

### 3.3 Exact branch analysis

Starting from `|psi>_0 (x) |Phi+>_{12}` and applying steps 2–3, and grouping
the resulting state by Alice's outcome `(m0, m1)`, Bob's qubit is left in

| `(m0, m1)` | Bob's uncorrected state | probability |
|---|---|---|
| `(0, 0)` | `|psi>` | `1/4` |
| `(0, 1)` | `X|psi>` | `1/4` |
| `(1, 0)` | `Z|psi>` | `1/4` |
| `(1, 1)` | `XZ|psi>` = `-ZX|psi>` | `1/4` |

This table is reproduced numerically by `uncorrected_branch_states`, which is
an exact statevector computation with no sampling.

### 3.4 Which branches the correction actually repairs

A branch whose Pauli happens to be diagonal on the particular input is already
correct with no feed-forward at all, so "the correction matters" cannot be
asserted per branch uniformly. For an input that is an eigenstate of Pauli `P`,
the uncorrected branch `Q|psi>` equals `|psi>` up to a global phase exactly when
`Q` commutes with `P` (for a single Pauli `Q`, that means `Q = P` or `Q = I`).
Every other branch is damaged:

| input | damaged `(m0, m1)` | surviving `(m0, m1)` |
|---|---|---|
| `|0>`, `|1>` | `(0, 1)`, `(1, 1)` | `(0, 0)`, `(1, 0)` |
| `|+>`, `|->` | `(1, 0)`, `(1, 1)` | `(0, 0)`, `(0, 1)` |
| `|+i>`, `|-i>` | `(0, 1)`, `(1, 0)` | `(0, 0)`, `(1, 1)` |

The `(1, 1)` branch applies `XZ = -iY`; because `Y` commutes with itself but
not with `X` or `Z`, that branch is harmless for a `Y` eigenstate and damaged for
an `X` or `Z` eigenstate. For `|+i>` and `|-i>` both damaged branches are
**maximally** wrong: the uncorrected state is orthogonal to `|psi>`, so the
protocol returns the wrong state with certainty, not merely with high
probability.

"Damaged" is defined as fidelity `< 1 - 1e-6`, because a global phase is
invisible to fidelity and a statevector-level check is required to see it (see
Section 4). `tests/quantum/test_teleport.py::test_damaged_branch_set_matches_the_pauli_algebra`
pins the whole table for all six input states.

---

## 4. Pauli correction convention

The correction is fixed as

    U(m0, m1) = Z**m0 . X**m1          (matrix product; Z on the left)

| `(m0, m1)` | `U` | gates appended |
|---|---|---|
| `(0, 0)` | `I` | *(none)* |
| `(0, 1)` | `X` | `x` |
| `(1, 0)` | `Z` | `z` |
| `(1, 1)` | `ZX` | `x` then `z` |

**Why the circuit order matters.** Circuit order reverses matrix-product
order, so appending `x` then `z` yields the operator `Z . X`. Appending them
the other way yields `X . Z`, and since `XZ = -ZX` that is the correct
operator only up to a global phase of `-1`. A fidelity- or probability-based
check cannot see the difference; a phase-sensitive statevector comparison in
the `(1, 1)` branch can. The test suite asserts both that the correct order
recovers `|psi>` exactly and that the reversed order does not.

**Why this table works.** Since `(ZX)(XZ) = I`, `X^2 = I` and `Z^2 = I`,
applying `U(m0, m1)` to the corresponding row of the table above returns
`|psi>` exactly in all four branches. Verified for all six input states and
all four branches.

---

## 5. Qiskit bit ordering

For an `n`-qubit `Statevector`, Qiskit indexes amplitudes little-endian:

    i = sum_k b_k * 2**k        (qubit 0 is the least significant bit)

For `circuit.measure([q0, q1], [c0, c1])` the returned count string is ordered
by **classical-bit index with the highest clbit leftmost**, so `s[0]` is `c1`
and `s[1]` is `c0`. Therefore `m0 = s[1]` and `m1 = s[0]`.

This is stated as *verified on Qiskit 2.5.2 / Aer 0.17.2 / CPython 3.13.5*,
not as a universal constant. `tests/quantum/test_bit_ordering.py` pins it with
a permuted qubit-to-clbit mapping; with the identity mapping both candidate
conventions agree and the experiment would be inconclusive.

Consequence for branch extraction: reshape the eight little-endian amplitudes
to `A[b0, b1, b2]` and take `A[m0, m1, :]` as Bob's uncorrected branch state.

---

## 6. Basis measurements

A measurement in the Pauli `P` basis applies `R_P` with
`R_P P R_P^dag = Z` and then measures in the computational basis. The
resulting bit `b` corresponds to the eigenvalue `(-1)**b` of `P`.

| Basis | `R_P` | gates | algebraic check |
|---|---|---|---|
| `Z` | `I` | *(none)* | `Z = Z` |
| `X` | `H` | `h` | `H X H = Z` |
| `Y` | `Sdg . H` | `sdg`, `h` | `(H Sdg) Y (H Sdg)^dag = Z` |

The alternative Y sequence `h` then `s` is **not** equal to `sdg` then `h`.
Algebraically it realises `S . H`, which conjugates `Y` to `X` rather than to
`Z`. Physically it maps the Y eigenstates onto the X eigenstates
(`|+i> -> |+>`, `|-i> -> |->`), so the following computational-basis
measurement returns a 50/50 split instead of a deterministic outcome, while
still looking plausible. The test suite asserts the correct form works and
that the wrong form fails.

---

## 7. Projective measurement and fidelity

For a pure expected state `|psi>`:

    P_psi    = |psi><psi|
    P_perp   = I - P_psi
    p_match  = Tr(P_psi rho)
    p_mismatch = 1 - p_match

For a **pure** expected state the analytic fidelity is `F = <psi|rho|psi>`,
and therefore

    p_match  ==  F        identically

These are **the same quantity computed two ways**, not two independent
signals. In this codebase they are deliberately exposed as a pair — the
analytic value from `rho`, and the same quantity estimated from finite shot
counts — so the estimator can be checked against the analytic value. They
must never be reported as independent evidence.

---

## 8. State representations

Four distinct representations are kept apart on purpose:

| Representation | Type | Meaning |
|---|---|---|
| amplitude vector | `numpy.ndarray` | exact complex amplitudes |
| `Statevector` | Qiskit | pure state, exact |
| `DensityMatrix` | Qiskit | possibly mixed state, exact |
| count dictionary | `dict[str, int]` | finite-shot sampled outcomes |

There is no single vague "quantum state" object that hides these distinctions.
Conversion between representations is explicit.

---

## 9. Finite sampling and tolerance policy

Sampled assertions never use an arbitrary percentage band. Every sampled test
uses a **Clopper–Pearson exact binomial interval** computed from the observed
counts at a stated confidence (`tests/quantum/statutil.py`).

`assert_expected_probability(k, n, p, confidence)` asserts that the
analytically expected probability `p` lies inside the exact interval for `k`
successes in `n` trials. Under the null hypothesis that the true probability
is `p`, this fails with probability at most `1 - confidence`; the default
confidence is `0.999`.

Exact (non-sampled) assertions use `numpy.allclose` with an explicit absolute
tolerance, typically `1e-10` to `1e-12`.

---

## 10. Reproducibility

`run_counts` transposes each circuit for the Aer CPU backend with a fixed
transpiler seed and forwards an explicit simulator seed. Given the same
circuit, shots and simulator seed, the returned counts are identical; this is
asserted by the test suite. No module uses uncontrolled global randomness.

If `seed_simulator` is omitted, the Aer backend seeds itself from OS entropy,
so a caller that needs reproducibility must pass an explicit seed. Every
sampled test in the suite does.

---

## 11. What this layer does not do

The quantum core performs no signing, no verification, no attack simulation,
no noise modelling, no threshold calibration, and no security decision. It
imports nothing from `protocol/`, `attacks/`, `detection/`, `security/`,
`api/` or `frontend/`. It makes no claim about the security of any protocol
built on top of it.