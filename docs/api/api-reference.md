# SIH26141 Backend API — Reference

Milestone 7. This document is the endpoint contract. For architecture, lifecycle
and local development, see [`integration.md`](integration.md).

Base URL in local development: `http://127.0.0.1:8000`

---

## 1. Versioning

Two versions are independent and must not be conflated:

| Version | Value | What it versions |
| --- | --- | --- |
| API version | `v1` | the HTTP contract in this document |
| Reference protocol version | `RQDS-TP-1.0` | the QDS construction the API exposes |

Business endpoints are mounted under `/api/v1`. The three operational endpoints
are mounted at the root, unversioned, so an orchestrator does not have to know the
API version to ask whether the process is alive.

---

## 2. Endpoint inventory

### Operational (root, unversioned)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Liveness, API/protocol version, in-memory object counts |
| GET | `/ready` | Component import checks and store availability |
| GET | `/version` | Application, API, protocol, Python and package versions |

### Sessions

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/sessions` | Create a reference signing session |
| GET | `/api/v1/sessions` | List sessions |
| GET | `/api/v1/sessions/{session_id}` | Fetch one session |
| POST | `/api/v1/sessions/{session_id}/sign` | Sign the session, returning a transcript |
| POST | `/api/v1/sessions/{session_id}/expire` | Move the session to EXPIRED |

### Verification

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/verify` | Verify a transcript with the M2 verifier |

### Simulation

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/simulations` | Run a scenario — **observable output only** |
| POST | `/api/v1/simulations/evaluation` | Run a scenario as an evaluation artifact — **includes ground truth** |

### Detection

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/detect` | Run the M4 detector over observable input |

### Calibration

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/calibration/run` | Derive a threshold from honest-only data |
| GET | `/api/v1/calibration/reference` | Reference methodology and recorded operating point |
| GET | `/api/v1/calibration/{calibration_id}` | Retrieve a stored calibration |

### Evaluation

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/evaluation/run` | Run a benchmark profile |
| GET | `/api/v1/evaluation/{evaluation_id}` | Retrieve a stored summary |
| GET | `/api/v1/evaluation/{evaluation_id}/artifact` | Retrieve the full report (large) |

### Security analysis

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/security/assumptions` | Assumption register |
| GET | `/api/v1/security/observability` | Threat-observability matrix |
| GET | `/api/v1/security/composition` | Composition assessment |
| POST | `/api/v1/security/analyze` | Check statements against the forbidden-claim register |

---

## 3. Errors

Every non-2xx response has the same envelope:

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "no session with id 'abc'",
    "request_id": "9f2c...",
    "details": { "resource": "session", "id": "abc" }
  }
}
```

| Status | Code | When |
| --- | --- | --- |
| 400 | `BAD_REQUEST` | A schema-valid configuration the domain refuses (e.g. a fraction on a non-fractional attack) |
| 404 | `NOT_FOUND` | Unknown session, calibration or evaluation |
| 409 | `CONFLICT` | An illegal lifecycle transition |
| 413 | `PAYLOAD_TOO_LARGE` | Declared body over the configured limit |
| 422 | `UNPROCESSABLE_ENTITY` | Schema validation failure, including any unknown field |
| 500 | `INTERNAL_ERROR` | Unhandled failure. Logged with its traceback; the traceback is never returned |

Stack traces are never returned. Every response — success or failure — carries an
`X-Request-ID` header, and the same value appears in `error.request_id`.

A caller may supply its own `X-Request-ID`. It is echoed only when it is bounded
and made of safe characters; otherwise a fresh identifier is generated.

---

## 4. Worked examples

### 4.1 Create a session

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/sessions \
  -H 'Content-Type: application/json' \
  -d '{"message":"transfer 10 units to account 7","signer_id":"alice","verifier_id":"bob","state_count":8}'
```

```json
{
  "session_id": "8f0c…",
  "nonce": "b41d…",
  "protocol_version": "RQDS-TP-1.0",
  "protocol_status": "created",
  "lifecycle": "CREATED",
  "state_count": 8,
  "message_hash": "3a7c…",
  "message_binding": "d2e9…",
  "created_at": "2026-09-14T14:20:00+00:00",
  "signer_id": "alice",
  "verifier_id": "bob",
  "history": ["CREATED"]
}
```

### 4.2 Sign it

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/sessions/<session_id>/sign
```

Returns `transcript` (the serialized reference transcript), `transcript_hash`,
and `lifecycle: "SIGNED"`. Signing is deterministic: the signer's simulator seed
is fixed, so the same session always yields the same transcript.

### 4.3 Verify the transcript

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/verify \
  -H 'Content-Type: application/json' \
  -d '{"message":"transfer 10 units to account 7","transcript":{…},"verifier_context":{"verifier_id":"bob"}}'
```

```json
{
  "accepted": true,
  "session_valid": true,
  "message_valid": true,
  "transcript_valid": true,
  "state_sequence_valid": true,
  "measurement_valid": true,
  "errors": [],
  "warnings": [],
  "state_count": 8,
  "mismatch_count": 0,
  "basis_counts": { "Z": 4, "X": 4 },
  "measurement_summary": { "checked": 8, "matched": 8, "mismatched": 0 },
  "session_id": null,
  "lifecycle": null,
  "note": "A verification decision is a consistency result about one transcript. It is not a security verdict."
}
```

**A malformed transcript is not an HTTP error.** The M2 verifier turns malformed
*content* into `accepted: false` with an error string, and the API reports that
unchanged as a 200. Only a transcript that is not a JSON object at all is a 422.

### 4.4 Run a scenario (observable output)

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/simulations \
  -H 'Content-Type: application/json' \
  -d '{"state_count":8,"random_seed":11,
       "noise":{"noise_type":"depolarizing","noise_strength":0.02},
       "attack":{"attack_type":"channel_tampering","fraction":0.5,"seed":3}}'
```

The response contains `states`, `mismatch_count`, `mismatch_proportion`,
`mean_channel_disturbance`, `verification`, `authorization`, `simulator_seed` and
`observable_only: true`. **It has no ground-truth field at all** — not a null
field, an absent one.

The run is reproducible: the same `random_seed` reproduces the same session
identifiers, binding, state sequence and observations.

### 4.5 Run a scenario as an evaluation artifact

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/simulations/evaluation -d '{…}' -H 'Content-Type: application/json'
```

Same body, different route, different response schema: the payload additionally
contains `ground_truth` with `is_malicious`, the attack description and the label
`"evaluation ground truth; not observable operational output"`.

### 4.6 Detect over observable evidence

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/detect \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"s-1","nonce":"n-1",
       "states":[{"index":0,"basis":"Z","expected_bit":0,"probability_expected":1.0,"matched":true}],
       "declared_state_count":1,"measurement_mode":"sampled",
       "verification":{"available":true,"accepted":true}}'
```

The request schema has **no field** for `attack_type`, `attack_fraction`,
`noise_strength` or any ground-truth metadata, and unknown fields are refused with
a 422. Sending one is an error, not a silently dropped field.

The response carries `overall_status`, `findings`, `features`,
`diagnostic_statistics` and:

```json
"security_assessment": {
  "status": "evidence_only",
  "formal_proof_present": false,
  "ground_truth_used": false,
  "limitations": [
    "the detector consumes observable input only; no attack label reaches it",
    "a finding is evidence of inconsistency with the calibrated honest model, not attribution of a cause",
    "detection is not a security verdict: a CLEAR status does not establish that a session is honest, because an adversary can produce consistent observations",
    "no formal forgery bound and no universal detection guarantee is produced here"
  ]
}
```

Set `consume_replay: true` to record the event in the shared M4 replay ledger; a
second event with the same nonce then produces a `REPLAY` finding. The ledger is
in memory and is lost on restart.

### 4.7 Calibrate

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/calibration/run \
  -H 'Content-Type: application/json' \
  -d '{"state_count":100,"session_count":8}'
```

Returns `calibration_id`, `config`, `interval`, `upper_bound`, `homogeneity`,
`threshold` and `operating_point`. The per-state homogeneity probability vector is
**omitted** — for the reference dataset it is tens of thousands of floats and it
is simulator-internal detail.

```bash
curl -s http://127.0.0.1:8000/api/v1/calibration/reference
```

Reports the reference method, the error-budget split, and the operating point
recorded in the committed benchmark artifact (read, not recomputed).

### 4.8 Evaluate

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/evaluation/run \
  -H 'Content-Type: application/json' -d '{"profile":"smoke"}'
```

Returns per-attack confusion matrices with `detection_rate`, `far`, `tpr`, `tnr`,
`precision`, `recall`, `f1` and `accuracy`; `honest_frr_by_noise`;
`detection_by_noise_and_attack`; the operating point; and `curve_names`.

There is deliberately **no pooled "overall" matrix**: the benchmark scores honest
and malicious populations separately and the per-attack rows contain no honest
trials, so a pooled matrix would report an FRR computed from zero sessions.

`profile: "reference"` is the full recorded benchmark and takes minutes; the route
is synchronous, so allow a long client timeout.

### 4.9 Security analysis

```bash
curl -s http://127.0.0.1:8000/api/v1/security/observability
curl -s -X POST http://127.0.0.1:8000/api/v1/security/analyze \
  -H 'Content-Type: application/json' \
  -d '{"statements":["At N=500 under the calibrated honest depolarizing channel at eta=0.01, the empirical false-rejection rate was 0.0% over 120 independent honest trials."]}'
```

Every security response carries a `security_assessment` with
`status: "assumption_conditioned"`, `formal_proof_present: false` and the
applicable limitations. No response offers a boolean verdict, and none says the
system is secure.

Submitting an overclaim instead returns `forbidden` with the matched pattern and
its reason. The checker never accepts a sentence that asserts
information-theoretic security, because no such result was derived at any
milestone.

---

## 5. Key schemas

### `SessionView`

`session_id`, `nonce`, `protocol_version`, `protocol_status`, `lifecycle`,
`state_count`, `message_hash`, `message_binding`, `created_at`, `signer_id`,
`verifier_id`, `history`.

`protocol_status` is the protocol's own status (`created`, `signed`).
`lifecycle` is the API's orchestration state (see `integration.md` §4).

### `VerificationResponse`

Mirrors `VerificationResult` field for field: `accepted`, `session_valid`,
`message_valid`, `transcript_valid`, `state_sequence_valid`, `measurement_valid`,
`errors`, `warnings`, `state_count`, `mismatch_count`, `basis_counts`,
`measurement_summary`, plus optional `session_id` and `lifecycle`.

### `SimulationResponse` vs `SimulationEvaluationResponse`

| | `SimulationResponse` | `SimulationEvaluationResponse` |
| --- | --- | --- |
| Route | `/simulations` | `/simulations/evaluation` |
| `ground_truth` | **absent** | present and required |
| `observable_only` | `true` | `false` |

### `DetectionResponse`

`protocol_valid`, `overall_status`, `explanation`, `finding_count`, `findings`,
`features`, `diagnostic_statistics`, `session_reference`, `notes`,
`security_assessment`.

### `CalibrationResponse`

`calibration_id`, `config`, `total_valid`, `total_mismatch`, `pooled_rate`,
`interval`, `upper_bound`, `homogeneity`, `threshold`, `operating_point`, `notes`,
`security_assessment`.

### `EvaluationSummary`

`evaluation_id`, `profile`, `dataset_role`, `seed_base`, `configuration`,
`operating_point`, `by_attack_type`, `honest_frr_by_noise`,
`detection_by_noise_and_attack`, `curve_names`, `sample_size_rows`,
`runtime_seconds`, `ground_truth_used`, `security_assessment`, `note`.

---

## 6. Claim language

The API preserves the M6 boundaries rather than summarising them. It returns none
of the following, and there is no field in which any of them could appear:

* The API does not return `information_theoretically_secure: true`.
* The API does not return `secure: true`, `is_secure` or `unforgeable`.
* The API does not assert a formal forgery bound.
* The API does not make a composability claim.

What it returns instead is a structured, conditional assessment:

```json
"security_assessment": {
  "status": "assumption_conditioned",
  "formal_proof_present": false,
  "composable_security_established": false,
  "universal_detection_guarantee": false,
  "forgery_bound_derived": false,
  "limitations": [ "…" ]
}
```

---

## 7. Input bounds

| Bound | Limit |
| --- | --- |
| Request body | 1 MiB |
| `message` length | configured; default 4096 characters |
| Identity fields | the protocol's identifier rule: at most 128 characters, starting with an alphanumeric, from `A-Za-z0-9._:@-` |
| `protocol_version` | the protocol's version rule: `RQDS-TP-<major>.<minor>` |
| `state_count` | 1 – 4096 (the reference protocol's maximum signature length) |
| `shot_count` | configured; default 1 – 1024 |
| Calibration `session_count` | configured; default 1 – 64 |
| Calibration `confidence` | open interval (0, 1) |
| `statements` per analyze request | configured; default 50 |
| `random_seed` | 0 – 9223372036854775807 |

Identities and protocol versions are validated with the protocol's **own compiled
patterns**, not a second copy of the rule. A looser schema here would admit a
value the protocol then rejects, which surfaces a client error as a 500; the
reference protocol's rules are therefore the API's rules.

### Which bounds are configuration

Four bounds are read from the running application's settings rather than fixed in
the schema, so a deployment can tighten or relax them without editing code:

| Setting | Field it caps |
| --- | --- |
| `max_message_chars` | `message` on `/sessions`, `/verify`, `/simulations` and `/detect` |
| `max_shot_count` | `shot_count` on `/simulations` and `/calibration/run` |
| `max_calibration_sessions` | `session_count` on `/calibration/run` |
| `max_statements_per_request` | `statements` on `/security/analyze` |

The table above reports the **default** value of each, which is what an
application built with no explicit settings enforces. A configured limit is the
one actually applied: a value the default would accept is refused when the
application's setting is lower, and accepted when it is higher. Each request is
validated against the settings of the application it was routed to, so two
applications in one process do not share a bound.

Every schema still declares a static maximum so that OpenAPI describes the type.
A configured limit above that maximum would make the static bound the effective
limit, so such a setting is refused when the application is built rather than
being silently ignored.

Exceeding a schema bound is a 422; exceeding the body bound is a 413.
