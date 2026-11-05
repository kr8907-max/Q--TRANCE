












import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  createSession,
  getHealth,
  getReady,
  getVersion,
  runSimulation,
} from "./client";

const BASE = "http://127.0.0.1:8000";

function jsonResponse(status: number, body: unknown, requestId = "rid-1"): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "X-Request-ID": requestId },
  });
}

describe("API client URL routing", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {

    fetchMock = vi.fn().mockImplementation(() => Promise.resolve(jsonResponse(200, {})));
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function calledUrl(): string {
    return String(fetchMock.mock.calls[0][0]);
  }

  it("probes liveness at the ROOT /health, not /api/v1/health", async () => {
    await getHealth();
    expect(calledUrl()).toBe(`${BASE}/health`);
    expect(calledUrl()).not.toContain("/api/v1");
  });

  it("probes readiness at the ROOT /ready", async () => {
    await getReady();
    expect(calledUrl()).toBe(`${BASE}/ready`);
  });

  it("reads version at the ROOT /version", async () => {
    await getVersion();
    expect(calledUrl()).toBe(`${BASE}/version`);
  });

  it("keeps business endpoints under /api/v1", async () => {
    await createSession({ message: "m", signer_id: "alice", verifier_id: "bob" });
    expect(calledUrl()).toBe(`${BASE}/api/v1/sessions`);

    fetchMock.mockClear();
    await runSimulation({ scenario_id: "demo1" });
    expect(calledUrl()).toBe(`${BASE}/api/v1/simulations`);

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect((init.headers as Record<string, string>)["X-Request-ID"]).toBeTruthy();
  });
});

describe("API client error envelope", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("maps a 400 configuration refusal to an actionable ApiError", async () => {


    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(400, {
          error: {
            code: "BAD_REQUEST",
            message:
              "the scenario configuration was refused: noise_type 'none' requires noise_strength 0.0, got 0.05",
            request_id: "req-400",
            details: {
              reason: "noise_type 'none' requires noise_strength 0.0, got 0.05",
              error_type: "NoiseValidationError",
            },
          },
        }),
      ),
    );

    const err = await runSimulation({ scenario_id: "demo1" }).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.code).toBe("BAD_REQUEST");
    expect(err.status).toBe(400);
    expect(err.message).toContain("noise_type 'none' requires noise_strength 0.0");
    expect(err.requestId).toBe("req-400");

    expect(err.details).toMatchObject({ error_type: "NoiseValidationError" });
  });

  it("preserves per-field 422 validation errors in details", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(422, {
          error: {
            code: "UNPROCESSABLE_ENTITY",
            message: "request validation failed",
            request_id: "req-422",
            details: {
              errors: [
                { loc: ["body", "state_count"], msg: "Input should be greater than or equal to 1", type: "greater_than_equal" },
              ],
            },
          },
        }),
      ),
    );

    const err = await runSimulation({ scenario_id: "demo1", state_count: 0 }).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(422);
    const errors = (err.details as { errors: { loc: string[]; msg: string }[] }).errors;
    expect(errors[0].loc).toEqual(["body", "state_count"]);
  });

  it("maps an unreachable backend to a NETWORK_ERROR with the base URL", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fetch failed")));
    const err = await getHealth().catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.code).toBe("NETWORK_ERROR");
    expect(err.message).toContain(BASE);
  });
});
