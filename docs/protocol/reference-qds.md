# Reference QDS Protocol Engine — Milestone 2

> **Status statement.** This milestone implements a **modular reference protocol
> construction used for simulation, attack modelling and threat-detection
> research.**
>
> It is **not** the official Egreen Quanta protocol, **not** a standardized QDS
> protocol, and **not** formally proven information-theoretically secure. It is
> also not a complete formal QDS protocol: the SIH specification calls for a
> teleportation-based QDS-oriented framework but does not fully specify one, so
> what follows is a reference construction that establishes the protocol
> semantics later milestones will attack and evaluate.

---

## 1. Scope

This document describes `backend/protocol`, the Milestone 2 protocol layer.

In scope:

* a strongly typed signing session;
* a canonical message/session binding;
* a deterministic derivation of a reference signature-state sequence;
* a signer that teleports that sequence using the verified M1 quantum core;
* a canonical, hashable, strictly validated transcript;
* a verifier that **reconstructs** its expectations instead of trusting the
  signer;
* a structured verification result.

Out of scope for M2 (and deliberately absent from the code): attacks, channel
tampering, noise models, QDS threat detection, threshold calibration, replay
detection, impersonation detection, machine learning, API and frontend.

The quantum primitives themselves are documented separately in
`docs/protocol/quantum-core.md` (Milestone 1).

---

## 2. Why this is a reference prototype

Three things are true at once and must not be blurred:

1. **The quantum core is verified.** Every primitive the protocol calls
   (eigenstates, Bell state, teleportation, corrections, basis measurements,
   fidelity) is independently tested in M1.
2. **The protocol is a construction, not a specification.** The mapping from a
   message to a state sequence, the transcript schema and the verification
   policy are engineering choices made here. They are documented, isolated and
   replaceable — not derived from a standard.
3. **No security proof exists.** Nothing in this document should be read as a
   claim that a signature produced by this code is unforgeable, that the
   construction is equivalent to any published QDS protocol, or that it is
   information-theoretically secure.

The purpose of the prototype is to be *correct, explicit, modular, auditable,
testable and replaceable* so that later milestones can attack it meaningfully.

---

## 3. Entities

| Entity | Module | Role |
|---|---|---|
| `Session` | `models.py` | the message plus the metadata bound to it |
| `SignatureState` | `models.py` | one symbolic element of the signature sequence |
| `TeleportationBranch` | `models.py` | Alice's two public Bell bits for one state |
| `Transcript` | `models.py` | the canonical artifact the verifier receives |
| `SigningResult` | `models.py` | session + transcript returned by the signer |
| `VerifierContext` | `models.py` | what the verifier knows independently |
| `VerificationResult` | `models.py` | structured outcome with diagnostics |

Two named parties exist, `signer_id` and `verifier_id`. M2 models *who* they are
and *which session* they share; it does not model unauthorized verification,
impersonation or identity theft. Those behaviours belong to a later milestone,
and the fields exist so that milestone has something to exercise.

---

## 4. Session model

A session is a frozen dataclass with the following fields:

| Field | Type | Notes |
|---|---|---|
| `session_id` | `str` | 128-bit CSPRNG value, lowercase hex (32 chars) |
| `nonce` | `str` | 256-bit CSPRNG value, lowercase hex (64 chars) |
| `message` | `str` | NFC-normalised message text |
| `message_hash` | `str` | SHA-256 of the message bytes |
| `signer_id`, `verifier_id` | `str` | validated identifiers |
| `protocol_version` | `str` | `RQDS-TP-1.0` |
| `state_count` | `int` | length of the signature sequence |
| `state_sequence_metadata` | `dict` | *how* to derive the sequence, not the sequence |
| `created_at` | `str` | UTC ISO-8601, second resolution |
| `status` | `SessionStatus` | `created` → `signed` |

The session deliberately holds **no key material**, and it is **not** the source
of truth for the state sequence. The sequence is derived on demand from the
binding, so a session object cannot smuggle a precomputed sequence past the
verifier.

### Two kinds of randomness

| Purpose | Source | Reproducible |
|---|---|---|
| `session_id`, `nonce` | `secrets` (OS CSPRNG) | **No**, by design |
| simulator seed | plain `int`, default `0` | **Yes**, by design |

The cryptographic identifiers are never derived from the simulator seed, and the
seed is never derived from the identifiers. They are independent channels. The
seed exists so that a *simulation* is reproducible; it carries no security
meaning. `create_session` accepts `session_id_factory`, `nonce_factory` and
`clock` injection points so that a test — and only a test — can make a session
deterministic.

---

## 5. Message binding

```
message_hash    = SHA256( utf8( NFC(message) ) )

message_binding = SHA256( canonical_bytes({
    "domain"           : "rqds-tp-1.0/message-binding",
    "protocol_version" : <protocol_version>,
    "session_id"       : <session_id>,
    "nonce"            : <nonce>,
    "message"          : <message>,
}) )
```

**Why not concatenate.** A naive `protocol_version + session_id + nonce +
message` is ambiguous: `("ab", "cd")` and `("abc", "d")` produce identical byte
strings, so characters could be moved between fields without changing the
digest. The canonical object encoding gives every field an explicit name and an
explicit boundary, and `sort_keys=True` fixes the order. This is asserted by
`tests/protocol/test_binding.py::test_field_boundaries_are_unambiguous`, which
is exactly the case a concatenation implementation would fail.

**Domain separation.** The `domain` tag ensures a binding digest cannot collide
with a digest computed for another purpose from the same field values.

**Determinism.** The binding is a pure function of its four keyword-only
arguments: no clock, no randomness, no global state.

The binding commits to the raw message, not to `message_hash`. `message_hash` is
recorded separately as a convenience and integrity field.

---

## 6. State alphabet

The alphabet is exactly the six Pauli eigenstates implemented and tested in M1.
The canonical order is taken from `backend.quantum.states.EIGENSTATE_LABELS`, so
it cannot drift from the quantum core:

| Index | Identifier | Ket | Basis | Eigenvalue |
|---|---|---|---|---|
| 0 | `Z+` | `\|0>` | Z | +1 |
| 1 | `Z-` | `\|1>` | Z | −1 |
| 2 | `X+` | `\|+>` | X | +1 |
| 3 | `X-` | `\|->` | X | −1 |
| 4 | `Y+` | `\|+i>` | Y | +1 |
| 5 | `Y-` | `\|-i>` | Y | −1 |

States are identified symbolically. **Floating-point amplitudes never appear in
a transcript**: the canonical encoder rejects `float` outright, so an amplitude
vector cannot be serialized by accident. The quantum simulation constructs the
corresponding state through `backend.quantum` when it needs one.

---

## 7. State-sequence derivation

This mapping is an **engineering choice** for the reference prototype. It is
isolated in `backend/protocol/encoding.py` and is replaceable without touching
the signer, the verifier or the transcript format. It makes no security claim.

```
seed       = bytes.fromhex(message_binding)                 # 32 bytes
block_k    = SHA256( seed || utf8("rqds-tp-1.0/state-stream") || uint32_be(k) )
stream     = nibbles(block_0) || nibbles(block_1) || ...    # 4-bit, MSB first
state_index = first accepted nibbles, where a nibble n is accepted iff n < 12,
              mapped by index = n mod 6
```

**Why rejection sampling.** `12 = 2 × 6`, so the accepted range `0..11` contains
each residue class exactly twice and the six states are exactly equiprobable. A
naive `byte mod 6` would be biased: `256 = 42 × 6 + 4` favours four of the six
states. The property is asserted both structurally (each residue occurs twice in
`0..11`) and statistically over 6000 states using M1's exact Clopper-Pearson
interval at the suite confidence.

**Determinism and statelessness.** The derivation is a pure function of
`(binding, count)`. Rejection sampling consumes a variable number of nibbles,
which is still deterministic because the stream is deterministic. There is no
global state, so interleaved derivations do not interfere, and deriving fewer
states yields the same prefix as deriving more.

`state_sequence_metadata` records *how* to reproduce the sequence (derivation
name, domain tag, alphabet, count) — never the derived values.

---

## 8. Signer workflow

```
sign(message, signer_id, verifier_id, state_count, simulator_seed)
 1. validate the message (non-empty string, NFC)
 2. create the session                       (or accept an injected one)
 3. compute message_hash and message_binding
 4. derive the reference state sequence      (pure function of the binding)
 5. initialise transcript metadata
 6. for each state: teleport it with the M1 engine, record Alice's Bell bits
 7. assemble the transcript and compute its hash
 8. return SigningResult(session status=SIGNED, transcript)
```

Step 6 calls `backend.quantum.teleport.teleport_circuit` and
`backend.quantum.measure.run_counts`. **No teleportation mathematics is
duplicated in protocol code.** The signer runs with the feed-forward correction
enabled and does **not** measure Bob's qubit: measuring the received qubit is
the verifier's job, and letting the signer do it would blur the two roles.

The per-state simulator seed is `simulator_seed + index`, so a signing run is
reproducible when a caller asks for it.

The signer imports nothing from `backend.attacks` or `backend.detection`, and
knows nothing about how a transcript will be attacked.

---

## 9. Teleportation integration

| Concern | Owner |
|---|---|
| what state is transported, and why it is in the sequence | protocol (`encoding.py`) |
| which session it belongs to | protocol (`session.py`) |
| what the verifier expects | protocol (`encoding.py`, re-derived by `verifier.py`) |
| circuits, quantum states, Bell measurement, corrections, measurement | quantum core (M1) |

The protocol layer is a *client* of the quantum core. The dependency direction
is one way:

```
reference_qds  →  backend.protocol  →  backend.quantum
```

`backend.quantum` imports nothing from `backend.protocol`. This is enforced by
`tests/protocol/test_architecture.py`.

---

## 10. Transcript

A transcript carries:

| Field | Purpose |
|---|---|
| `transcript_version` | schema version (currently `1`) |
| `protocol_version` | protocol semantics version |
| `session_id`, `nonce` | session identity, bound into the message binding |
| `created_at` | audit timestamp (UTC ISO-8601) |
| `message_hash`, `message_binding` | message/session commitment |
| `signer_id`, `verifier_id` | parties |
| `state_count` | sequence length |
| `state_sequence_metadata` | how to reproduce the sequence |
| `states` | the declared symbolic signature states |
| `teleportation_branches` | Alice's public Bell bits, per state |
| `verification_metadata` | signer-declared verification policy |
| `transcript_hash` | SHA-256 over every other field |

```
transcript_hash = SHA256( canonical_bytes( transcript.payload() ) )
```

`payload()` is every field **except** `transcript_hash`. `created_at` is not in
the milestone's minimum field list; it is included because the transcript is the
auditable artifact and a timestamp is required for audit. It is covered by the
hash like every other field.

`verification_metadata` is a *declaration* by the signer (basis policy,
measurement mode, correction convention, sequence source). The verifier
re-derives its own expectations regardless and does not obey it.

No private material appears in the transcript: no keys, no amplitudes, no
simulator seed.

---

## 11. Verifier workflow

```
verify(transcript, message, verifier_context)
 1. parse and validate the transcript        → transcript_valid
 2. recompute and compare transcript_hash    → transcript_valid
 3. check protocol version and identities    → session_valid
 4. recompute message_hash and the binding from (message, session_id, nonce,
    protocol_version)                         → message_valid
 5. derive the expected state sequence from the *recomputed* binding and
    compare it with the declared states       → state_sequence_valid
 6. run the quantum verification path per state → measurement_valid
 7. return VerificationResult(accepted = all of the above and no errors)
```

**The verifier does not trust the signer.** It never reads the expected sequence
out of the transcript's own claim and accepts it; it derives the sequence itself
from the binding it recomputed, then compares. Concretely, the anti-pattern

```python
verifier.expected_states = signer.states   # never done
```

does not occur. `test_verifier_does_not_trust_the_signers_state_sequence`
constructs a transcript that is internally consistent and correctly hashed but
disagrees with the verifier's reconstruction, and shows it is rejected on the
state-sequence check alone.

### The quantum verification path

For each expected state:

1. take the state vector from the verified M1 core;
2. reconstruct the received qubit from Alice's recorded public Bell bits using
   M1's exact branch decomposition
   (`backend.quantum.teleport.uncorrected_branch_states`);
3. apply the M1 Pauli correction `Z^m0 · X^m1`
   (`backend.quantum.correction.correction_unitary`);
4. prepare the corrected state, rotate into the state's basis with M1's
   `add_basis_rotation`, and compute the projective probability of the expected
   eigenvalue with M1's `p_match`.

Step 2 is the **simulation seam**. In an ideal model the received qubit is
exactly the branch image of the expected state, so the verifier can reconstruct
it from public data. A later milestone replaces this reconstruction with the
actual channel output, at which point noise and tampering make step 4 fail.

`verify` accepts a `Transcript` or plain transcript data, and **never raises** on
untrusted input: any validation failure becomes a structured rejection.

---

## 12. Verification result

| Field | Meaning |
|---|---|
| `accepted` | all flags true and no errors recorded |
| `transcript_valid` | schema, field formats and transcript hash |
| `session_valid` | protocol version, verifier identity, count consistency |
| `message_valid` | message hash and recomputed binding match |
| `state_sequence_valid` | derived sequence and metadata match the declaration |
| `measurement_valid` | every per-state projective measurement matched |
| `verification_errors` | ordered, human-readable reasons |
| `verification_warnings` | always includes the "structural, not unforgeability" caveat |
| `state_count`, `mismatch_count` | raw counts |
| `basis_counts` | states per basis |
| `measurement_summary` | `checked` / `matched` / `mismatched` |

These diagnostics are **raw counts for later milestones**. M2 computes no false
positive rate, no false negative rate, no threshold, no attack label and no
confidence score, and `test_verification_result_carries_no_threshold_statistics`
asserts that none of those keys appear.

---

## 13. Canonical serialization

`backend/protocol/canonical.py` defines exactly one encoding.

1. Every `str` is normalised to Unicode **NFC**; lone surrogates are rejected.
2. Only `None`, `bool`, `int`, `str`, `list`/`tuple` and `dict` with `str` keys
   are accepted. **`float` is rejected**, and so are `bytes`.
3. The value is serialized with
   `json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)`
   and encoded as UTF-8.

Consequences: key order is by Unicode code point and therefore locale-
independent; there is no insignificant whitespace; non-ASCII text is emitted as
UTF-8 rather than `\uXXXX` escapes; and two textually equivalent strings
normalise to identical bytes.

`canonical_digest(obj) = SHA256(canonical_bytes(obj))`, lowercase hex.

Nothing hashes `repr()` output. Nothing uses `pickle`, `eval`, `exec` or
`compile`. `test_no_pickle_or_eval_in_the_protocol_layer` asserts this at the
AST level, and `tests/protocol/test_canonical.py` pins a golden encoding and its
digest as literals so an accidental change to the encoding is caught.

---

## 14. Protocol version

| Constant | Value | Meaning |
|---|---|---|
| `PROTOCOL_VERSION` | `RQDS-TP-1.0` | project reference protocol version |
| `TRANSCRIPT_VERSION` | `1` | serialized transcript schema version |

`RQDS-TP-1.0` is the **project's** reference construction identifier. It is not
an industry standard and implies no formal security property. Any incompatible
change to the semantics defined in this package must bump the protocol version;
any change to the transcript schema must bump the transcript version. The
transcript schema is **closed**: unknown fields are rejected rather than
ignored, so adding a field requires a version bump.

---

## 15. Assumptions

* The message, session identifier, nonce and protocol version the verifier
  receives are the ones the signer used. M2 tests that tampering with them is
  *detected*; it does not model an adversary who can substitute all of them
  consistently.
* The quantum channel is ideal and noiseless.
* The signer and verifier are both correct implementations of this document.
* The six reference states are the ones M1 verified.
* SHA-256 is collision-resistant and preimage-resistant.
* The verifier's code, the alphabet and the derivation are public.

---

## 16. Security boundaries

| Property | Provided by M2? |
|---|---|
| message ↔ session ↔ nonce ↔ version binding | **yes** |
| canonical, tamper-evident transcript | **yes** |
| independent verifier reconstruction | **yes** |
| strict rejection of malformed input | **yes** |
| unforgeability / authenticity | **no** |
| secrecy of the message | **no** |
| resistance to a quantum channel attack | **no** |
| replay prevention | **no** (data is provided; tracking is not implemented) |
| impersonation prevention | **no** (identities are modelled, not authenticated) |

The protocol has **no secret key**. Its integrity guarantees are structural and
binding-based. An adversary who can re-derive the sequence can produce a
consistent transcript, because the derivation is public and deterministic. That
is a property of the reference construction, not a bug to be patched here.

---

## 17. What this protocol does NOT prove

* It does **not** prove information-theoretic security, and in particular it does
  **not** follow from the use of quantum teleportation that any security
  property holds.
* It does **not** implement, match or approximate the official Egreen Quanta
  protocol or any standardized QDS scheme.
* It does **not** establish unforgeability, non-repudiation or deniability.
* It does **not** detect any attack. M2 verification is a deterministic
  structural check, not a detector.
* It does **not** calibrate thresholds or report error rates.

`describe_protocol()` returns `formal_security_claim: false` and
`standardized: false`, and the verifier always attaches a warning that
verification is structural.

---

## 18. Known limitations

1. **No secret key, so no authenticity.** Anyone who knows the message and the
   public derivation can build a consistent transcript. M2 detects *tampering
   with a given transcript*; it does not resist *forgery of a new one*.
2. **Branch metadata is not independently checkable in the ideal model.** The
   Pauli correction inverts every Bell branch exactly, so after correction the
   received qubit always equals the expected state, whatever the branch bits
   say. Consequently `measurement_valid` is always true in M2 and tampering with
   the branch bits *plus* recomputing the transcript hash is not detected. The
   field is recorded because a real teleportation protocol must transmit those
   bits, and because a later milestone's noisy or tampered channel makes them
   load-bearing. This limitation is asserted, not hidden:
   `test_f_branch_metadata_tamper_is_caught_by_the_transcript_hash`.
   The falsifiable component, `measure_state_in_basis`, is tested directly and
   returns 0.5 (i.e. fails) when a state is measured in the wrong basis.
3. **`created_at` is a claimed timestamp.** It is hashed, so it cannot be changed
   without detection, but nothing verifies it against a trusted clock.
4. **The state-sequence mapping is arbitrary.** It is a deterministic
   pseudorandom function of the binding. Its uniformity is tested; its
   suitability as a cryptographic commitment is not claimed.
5. **Single-shot teleportation per state.** Branch bits come from one simulator
   shot per state; no sampling statistics are collected in M2.
6. **No concurrency or transport layer.** Transcripts are passed as values;
   there is no wire protocol, no session store and no replay database.
7. **Verification cost is dominated by signing.** See §20.

---

## 19. Future replacement points

| Component | Module | Replace when |
|---|---|---|
| state-sequence derivation | `encoding.py` | a different (or specified) mapping is required |
| alphabet | `encoding.py` | states other than the six Pauli eigenstates are used |
| canonical encoding | `canonical.py` | a different deterministic format is standardized |
| transcript schema | `transcript.py` | fields change (bump `TRANSCRIPT_VERSION`) |
| message binding | `binding.py` | the committed field set changes (bump the protocol version) |
| received-qubit reconstruction | `verifier.py` | a real channel replaces the ideal model |
| measurement mode | `verifier.py` | sampled/statistical verification replaces the analytic path |
| identity handling | `models.py` | real authentication is added |
| replay tracking | *(absent)* | a later milestone adds a consumed-nonce store |

Each is isolated behind a small, documented interface so the replacement does
not ripple through the layer.

---

## 20. Performance

Signing runs one M1 teleportation circuit per state. On the reference machine
(CPython 3.13, Qiskit 2.5.2, Aer 0.17.2) the cost is **transpile-dominated at
roughly 0.15 s per state**, so the default `DEFAULT_STATE_COUNT = 16` gives a
signing time of roughly 2.5 s. Verification uses the analytic statevector path
at roughly 1 ms per state, i.e. it is effectively free next to signing.

No caching is used. A per-label memo for `uncorrected_branch_states` would save
roughly a factor of three on verification, but verification is not the
bottleneck, and §24 of the milestone brief asks for no premature optimization.
The measured numbers above come from `time.perf_counter` on this machine and are
not extrapolated.

---

## 21. Module map

```
backend/protocol/
    __init__.py        public surface
    canonical.py       canonical serialization + SHA-256 digests
    models.py          frozen dataclasses, enums, versions, validators
    binding.py         message hash + canonical message/session binding
    encoding.py        message binding -> reference state sequence
    session.py         session creation, CSPRNG identifiers, clock
    transcript.py      transcript build/hash/serialize/validate
    signer.py          signing workflow (calls the M1 engine)
    verifier.py        verification workflow + quantum verification path
    reference_qds.py   facade, protocol description
```

Dependency direction: `reference_qds → backend.protocol → backend.quantum`.
