










import { describe, expect, it } from "vitest";
import type { SimulationResponse } from "../api/types";
import {
  buildDetectionRequest,
  buildSimulationRequest,
  identifierError,
  parseExtraVerifiers,
  type SimulationFormState,
} from "./scenarioForm";

const BASE_FORM: SimulationFormState = {
  scenarioId: "api-scenario",
  message: "reference message",
  signerId: "alice",
  verifierId: "bob",
  stateCount: 64,
  shotCount: 1,
  randomSeed: 0,
  measurementMode: "sampled",
  noiseType: "depolarizing",
  noiseStrength: 0.05,
  attackType: "none",
  fraction: 0.3,
  attackSeed: 0,
  extraVerifiers: "",
};

describe("identifierError", () => {
  it.each(["tamperdemo", "tamper_demo", "api-scenario", "demo1"])(
    "accepts %s, matching the backend identifier regex",
    (id) => {
      expect(identifierError(id)).toBeNull();
    },
  );

  it.each([
    ["demo1 ", "trailing whitespace"],
    [" demo1", "leading whitespace"],
    ["tamper demo", "an interior space"],
    ["", "empty"],
  ])("rejects %j (%s), as the backend does", (id) => {
    expect(identifierError(id)).not.toBeNull();
  });

  it("rejects identifiers longer than 128 characters", () => {
    expect(identifierError("a".repeat(129))).not.toBeNull();
    expect(identifierError("a".repeat(128))).toBeNull();
  });
});

describe("buildSimulationRequest", () => {
  it("serializes the default form into the payload the backend accepts", () => {
    const req = buildSimulationRequest(BASE_FORM);
    expect(req).toEqual({
      scenario_id: "api-scenario",
      message: "reference message",
      signer_id: "alice",
      verifier_id: "bob",
      protocol_version: "RQDS-TP-1.0",
      state_count: 64,
      shot_count: 1,
      random_seed: 0,
      measurement_mode: "sampled",
      noise: { noise_type: "depolarizing", noise_strength: 0.05 },
      attack: { attack_type: "none", fraction: 0, seed: 0 },
    });

    expect(Object.keys(req).sort()).toEqual(
      [
        "attack",
        "measurement_mode",
        "message",
        "noise",
        "protocol_version",
        "random_seed",
        "scenario_id",
        "shot_count",
        "signer_id",
        "state_count",
        "verifier_id",
      ].sort(),
    );
  });

  it("trims identifiers — copy-pasted whitespace no longer reaches the wire", () => {
    const req = buildSimulationRequest({
      ...BASE_FORM,
      scenarioId: "demo1 ",
      signerId: " alice",
      verifierId: "bob\t",
    });
    expect(req.scenario_id).toBe("demo1");
    expect(req.signer_id).toBe("alice");
    expect(req.verifier_id).toBe("bob");
  });

  it("sends noise_strength 0 when the channel is 'none', regardless of the slider", () => {


    const req = buildSimulationRequest({ ...BASE_FORM, noiseType: "none", noiseStrength: 0.05 });
    expect(req.noise).toEqual({ noise_type: "none", noise_strength: 0 });
  });

  it("keeps the slider strength for real noise channels", () => {
    const req = buildSimulationRequest({ ...BASE_FORM, noiseType: "bit_flip", noiseStrength: 0.2 });
    expect(req.noise).toEqual({ noise_type: "bit_flip", noise_strength: 0.2 });
  });

  it("zeroes the fraction for non-fractional attacks", () => {
    const req = buildSimulationRequest({ ...BASE_FORM, attackType: "replay", fraction: 0.3 });
    expect(req.attack).toEqual({ attack_type: "replay", fraction: 0, seed: 0 });
  });

  it("keeps the fraction for fractional attacks", () => {
    const req = buildSimulationRequest({
      ...BASE_FORM,
      attackType: "channel_tampering",
      fraction: 0.3,
      attackSeed: 7,
    });
    expect(req.attack).toEqual({ attack_type: "channel_tampering", fraction: 0.3, seed: 7 });
  });

  it("parses, trims and omits extra verifiers", () => {
    expect(parseExtraVerifiers("carol, dave,,  ")).toEqual(["carol", "dave"]);
    const withExtras = buildSimulationRequest({ ...BASE_FORM, extraVerifiers: "carol, dave" });
    expect(withExtras.extra_authorized_verifiers).toEqual(["carol", "dave"]);
    const without = buildSimulationRequest({ ...BASE_FORM, extraVerifiers: " , ," });
    expect("extra_authorized_verifiers" in without).toBe(false);
  });
});

describe("buildDetectionRequest (observable-only handoff)", () => {
  const result: SimulationResponse = {
    scenario_id: "api-scenario",
    protocol_version: "RQDS-TP-1.0",
    state_count: 2,
    measurement_mode: "sampled",
    simulator_seed: 0,
    mismatch_count: 1,
    mismatch_proportion: 0.5,
    mean_channel_disturbance: 0.1,
    basis_counts: { Z: 2 },
    states: [
      { index: 0, basis: "Z", expected_bit: 0, probability_expected: 0.9, matched: true },
      { index: 1, basis: "Z", expected_bit: 1, probability_expected: 0.4, matched: false },
    ],
    verification: {
      accepted: false,
      session_valid: true,
      message_valid: true,
      transcript_valid: true,
      state_sequence_valid: true,
      measurement_valid: false,
      errors: ["mismatch above threshold"],
      warnings: [],
      state_count: 2,
      mismatch_count: 1,
      basis_counts: { Z: 2 },
      measurement_summary: { mismatch_proportion: 0.5 },
    },
    authorization: {
      presented_signer: "alice",
      presented_verifier: "bob",
      authorized_signers: ["alice"],
      authorized_verifiers: ["bob"],
      signer_authorized: true,
      verifier_authorized: true,
    },
    runtime_seconds: 0.01,
    observable_only: true,
    note: "observable",
  };

  it("carries observable evidence only — no ground truth, no attack label", () => {
    const req = buildDetectionRequest(result, "reference message");
    const wire = JSON.stringify(req).toLowerCase();
    expect(wire).not.toContain("ground_truth");
    expect(wire).not.toContain("attack");
    expect(wire).not.toContain("is_malicious");
    expect(req.states).toHaveLength(2);
    expect(req.message).toBe("reference message");
    expect(req.declared_state_count).toBe(2);
    expect(req.verification?.available).toBe(true);
  });
});
