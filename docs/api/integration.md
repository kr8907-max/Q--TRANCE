# SIH26141 Backend API — Integration Guide

Milestone 7. This document covers architecture, the session lifecycle, local
development, storage, concurrency, logging and the known limitations. For the
endpoint contract, see [`api-reference.md`](api-reference.md).

---

## 1. What this layer is

An **application boundary** over the validated engines. It exposes M1–M6 through
a typed HTTP API and reimplements none of them.

```
                    FRONTEND (M8)
                         |
                         v
                    REST / API          <- this milestone
                         |
        +----------------+----------------+
        |                |                |
        v                v                v
     Protocol       Simulation       Detection
        |                |                |
        +----------------+----------------+
                         |
                     Calibration
                         |
                      Security
                         |
                      Quantum
```

The dependency direction is one-way and is enforced by a test:
`backend.api` imports the engine packages, and **no engine package imports
`backend.api`**.

| Concern | Owner | The API does |
| --- | --- | --- |
| Session creation, signing, verification | `backend.protocol` | builds a session, calls the signer, calls the verifier |
| Scenario execution | `backend.simulation` | assembles a `ScenarioConfig`, calls `run_scenario` |
| Detection | `backend.detection` | projects observable fields into `ObservableDetectionInput`, calls `detect` |
| Calibration | `backend.calibration` (+ `backend.evaluation` dataset helpers) | calls the estimator and threshold derivation |
| Evaluation | `backend.evaluation` | calls `run_benchmark`, selects and renames fields |
| Security interpretation | `backend.security` | returns the register, matrix and composition summary |

The API never imports `qiskit`. That is checked by a test, so the boundary cannot
erode silently.

### Package layout

```
backend/api/
    app.py              application factory, middleware wiring, OpenAPI metadata
    config.py           environment-driven settings, input bounds, CORS policy
    context.py          request-scoped correlation identifier and session reference
    dependencies.py     FastAPI dependency providers (settings, store)
    errors.py           ApiError, the error envelope, the exception handlers
    middleware.py       correlation, payload bound, structured access log
    store.py            in-memory orchestration state, lifecycle table, locking
    version.py          API version, application version, protocol version
    routes/             one module per concern; thin
    schemas/            typed request and response models
    services/           orchestration; one module per concern
```

---

## 2. Request flow

```
HTTP request
    |
    v
CORS middleware
    |
    v
RequestContextMiddleware      correlation id, payload bound, access log
    |
    v
FastAPI validation            Pydantic schema (extra fields forbidden)
    |
    v
route                         thin: binds schema, calls service
    |
    v
service                       calls an existing engine package
    |
    v
engine package                protocol / simulation / detection / calibration / evaluation / security
    |
    v
typed response model
```

Routes do not import engine packages directly, and services do not import routes.
Both are checked by tests.

---

## 3. Local development

### Install

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt      # Windows
# .venv/bin/pip install -r requirements.txt        # POSIX
```

### Run

```bash
uvicorn backend.api.app:create_app --factory --reload --port 8000
```

`create_app` is a factory, so `--factory` is required. Interactive documentation
is then at:

* Swagger UI: `http://127.0.0.1:8000/docs`
* ReDoc: `http://127.0.0.1:8000/redoc`
* OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`

### Smoke test

```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/version
curl -s http://127.0.0.1:8000/ready
```

### Tests

```bash
pytest tests/api -q          # API suite
pytest -q                    # everything, including M1-M6 regression
```

The API tests use FastAPI's `TestClient`; no server is started and no test needs
the network.

---

## 4. Session lifecycle

The lifecycle is an **application** concern. It does not replace the protocol's
own `SessionStatus`, which is reported separately as `protocol_status`.

```
CREATED --sign--> SIGNED --verify accepted--> VERIFIED --expire--> EXPIRED
                     |
                     +--verify rejected--> REJECTED --expire--> EXPIRED
                     |
                     +--expire--> EXPIRED

CREATED --expire--> EXPIRED
```

| Transition | Endpoint | Illegal move |
| --- | --- | --- |
| `-> CREATED` | `POST /sessions` | — |
| `CREATED -> SIGNED` | `POST /sessions/{id}/sign` | signing twice is a 409 |
| `SIGNED -> VERIFIED` | `POST /verify` with `session_id` | verifying an unsigned session is a 409 |
| `SIGNED -> REJECTED` | `POST /verify` with `session_id` | — |
| `any non-terminal -> EXPIRED` | `POST /sessions/{id}/expire` | expiring twice is a 409 |

`EXPIRED` is terminal. Every refusal returns 409 with the current state, the
requested state and the allowed set in `error.details`.

Recording a verification against a session is **optional and additive**: it never
changes the verification result. A caller who wants the verification result alone
omits `session_id`.

Automatic expiry is **disabled by default** so lifecycle behaviour is never a
surprise. `ApiSettings.session_ttl_seconds` enables it.

---

## 5. Storage

Everything is in memory:

| Store | Contents | Lifetime |
| --- | --- | --- |
| Session records | session, transcript, lifecycle history | lost on restart |
| Calibration records | calibration and operating point | lost on restart |
| Evaluation records | summary, report, markdown | lost on restart |
| Replay ledger | consumed session/nonce/transcript identities | lost on restart |

There is **no database**, by design: this milestone asks for prototype
orchestration, and a database would add a dependency and an operational surface
the API does not need yet. A restart therefore discards every session,
calibration and evaluation, and resets replay history.

The replay ledger is `backend.detection.replay.ReplayRegistry`, reused rather than
reimplemented. It is a single-process, in-memory session-state mechanism — **not**
a persistent or distributed replay-prevention system.

---

## 6. Concurrency

The application object is shared between requests, so all shared mutable state
lives behind one re-entrant lock in `ApiStore`.

* Every store mutation and read takes the lock.
* Detection takes the lock around its call, because detection reads and (with
  `consume_replay`) writes the shared replay ledger. Detection is a cheap
  analysis over the state list, so this does not serialise anything expensive.
* **No scenario simulation and no benchmark run is ever executed while the lock
  is held.** Those are the slow operations and they hold no shared state.

Uvicorn runs synchronous endpoints in a thread pool, so this matters in practice,
not only in theory.

---

## 7. Logging

One structured JSON record per request, on the `sih26141.api` logger:

```json
{
  "timestamp": "2026-09-14T14:20:00.123456+00:00",
  "level": "INFO",
  "logger": "sih26141.api",
  "message": "request",
  "request_id": "9f2c…",
  "method": "POST",
  "route": "/sessions/{session_id}/sign",
  "path": "/api/v1/sessions/8f0c…/sign",
  "status_code": 200,
  "duration_ms": 1166.8,
  "session_id": "8f0c…",
  "outcome": "ok"
}
```

`outcome` is one of `ok`, `client_error`, `server_error`, `payload_too_large`,
`error`. Request bodies, message contents and attack labels are **not** logged.

`session_id` is populated when the request names a session: from the path
parameter for the session routes, and from the body for `POST /verify`. It is
read from the **request scope**, not from a `ContextVar`. That distinction
matters here: route handlers are synchronous, so Starlette runs them in a worker
thread, and a `ContextVar` written inside that thread is discarded when it
returns — the middleware would never observe it. The scope dictionary is shared
between the middleware and the route, so writing to it works.

`request_id` is kept in **both** places, for the same kind of reason. The
`ContextVar` serves everything that runs inside the middleware. The scope copy
serves the one handler that does not: an unhandled exception is handled by
Starlette's `ServerErrorMiddleware`, which sits *above* this application's
middleware, so by the time that handler runs the context variable has been reset.
Without the scope copy a 500 would carry no identifier at all while its log line
carried one — precisely the case where correlation matters most.

There are two logging call sites in the whole API: the access log in
`middleware.py` and the unhandled-error log in `errors.py`. Neither writes a
request body, so there is nowhere for message content or a label to leak.

---

## 8. CORS

CORS is configurable and never silently wildcarded.

| Environment variable | Default | Meaning |
| --- | --- | --- |
| `SIH26141_API_CORS_ORIGINS` | localhost:5173 / 127.0.0.1:5173 / localhost:3000 / 127.0.0.1:3000 | Comma-separated allowed origins |
| `SIH26141_API_ALLOW_WILDCARD_CORS` | unset | Set to `1` to permit `*` |
| `SIH26141_API_ENVIRONMENT` | `development` | Free-text label reported by `/health` |

Setting `SIH26141_API_CORS_ORIGINS=*` without the opt-in variable raises at
startup, because this API has no authentication and a wildcard origin would let
any web page read every response. Credentials are never allowed.

The default origins are the usual local development ports (Vite 5173, CRA 3000)
so the M8 frontend works out of the box in development.

---

## 9. Security controls, and what is not implemented

Implemented:

* every input is validated by a typed schema, and unknown fields are refused;
* input bounds on body size, message length, state count, shot count, calibration
  sessions and statement count;
* malformed transcripts are rejected by the protocol verifier and reported as
  such;
* no `eval`, no `exec`, no `pickle`, no dynamic import of caller-supplied names;
* no filesystem access driven by request input, so no traversal surface;
* no secrets in responses, and no stack traces;
* correlation identifiers are sanitised before being echoed or logged.

**Not implemented, and not pretended otherwise:** there is no authentication, no
authorization, no rate limiting, no TLS termination and no audit log. This is a
prototype boundary for the frontend milestone, not a deployed service.

### How the configurable input bounds work

Four of the bounds above — `message` length, `shot_count`, calibration
`session_count` and the number of `statements` per analyze request — are read
from the application's `ApiSettings` rather than fixed in the schema. Tightening
one is a settings change, not a code change. They are constructor arguments
(`ApiSettings(max_message_chars=...)`); unlike the CORS settings above they are
not read from the environment, so a deployment that needs them sets them where
the application object is built.

The limit is applied in a **second validation pass**. FastAPI validates the body
first, which is what gives the endpoint its OpenAPI request schema, its
`extra="forbid"` handling and the framework's normal 422 shape. The API layer
then validates the parsed payload again with the application's settings placed in
the Pydantic validation context; the schema's own validators read the limit from
there. Re-validating from the dumped payload rather than the parsed object
matters: an instance that has already passed its validators is trusted on a
second pass, so the limit would never be reached.

Nothing global is involved. The schema class is shared, and the limit travels
with the request from the application that served it, so two applications in one
process cannot configure each other. A setting above the static ceiling the
schemas are built around is refused when the application is constructed, because
it would otherwise be silently ignored in favour of the static bound.

---

## 10. Known limitations

1. **Storage is in memory.** Restart loses sessions, calibrations, evaluations and
   replay history.
2. **No authentication.** Every endpoint is open. Do not expose the API beyond a
   development network.
3. **Long operations are synchronous.** `POST /evaluation/run` with
   `profile: "reference"` takes minutes and holds the connection. The smoke
   profile takes tens of seconds. There is no job queue and no progress
   reporting; a future milestone should make these asynchronous.
4. **Calibration and simulation are not cached.** Repeating a request repeats the
   work.
5. **No cross-process state.** Two API processes do not share sessions or the
   replay ledger.
6. **The reference operating point is read from a committed artifact.**
   `GET /calibration/reference` reports it only when
   `benchmarks/m5-reference.json` is present; otherwise the field is `null` and
   `provenance.available` is `false`.
7. **The API inherits the engine's boundaries.** Detection produces evidence, not
   a verdict; the security endpoints are assumption-conditioned; there is no
   composition theorem and no forgery bound. Nothing in this layer strengthens
   any of that.
8. **`profile: "reference"` cannot be parameterised.** The profile defines the
   configuration, so a caller cannot assemble an unbounded benchmark through the
   API. That is deliberate.

---

## 11. Troubleshooting

| Symptom | Cause |
| --- | --- |
| `404` on `/api/v1/...` after a restart | in-memory store was cleared |
| `409` on `sign` | the session is not `CREATED`; check `lifecycle` |
| `409` on `verify` with a `session_id` | the session is not `SIGNED`; omit `session_id` for the verification result alone |
| `422` mentioning an unexpected field | unknown fields are refused by design |
| `413` | declared body over 1 MiB |
| `null` operating point on `/calibration/reference` | the committed benchmark artifact is missing from the checkout |
| A deprecation warning from starlette | the pinned `anyio` was upgraded; see the note in `requirements.txt` |
