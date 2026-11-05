






















import {
  FRACTIONAL_ATTACK_TYPES,
  PROTOCOL_VERSION,
  type AttackType,
  type DetectionRequest,
  type MeasurementMode,
  type NoiseType,
  type SimulationRequest,
  type SimulationResponse,
} from "../api/types";


export const IDENTIFIER_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:@-]{0,127}$/;






export function identifierError(value: string): string | null {
  if (value.length === 0) return "Identifier is required.";
  if (value.length > 128) return "Identifier must be at most 128 characters.";
  if (!IDENTIFIER_PATTERN.test(value)) {
    return "Identifiers must start with a letter or digit and may then contain only letters, digits, '.', '_', ':', '@' or '-'.";
  }
  return null;
}


export function parseExtraVerifiers(text: string): string[] {
  return text
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}


export interface SimulationFormState {
  scenarioId: string;
  message: string;
  signerId: string;
  verifierId: string;
  stateCount: number;
  shotCount: number;
  randomSeed: number;
  measurementMode: MeasurementMode;
  noiseType: NoiseType;
  noiseStrength: number;
  attackType: AttackType;
  fraction: number;
  attackSeed: number;
  extraVerifiers: string;
}













export function buildSimulationRequest(form: SimulationFormState): SimulationRequest {
  const isFractional = FRACTIONAL_ATTACK_TYPES.includes(form.attackType);
  const req: SimulationRequest = {
    scenario_id: form.scenarioId.trim(),
    message: form.message,
    signer_id: form.signerId.trim(),
    verifier_id: form.verifierId.trim(),
    protocol_version: PROTOCOL_VERSION,
    state_count: form.stateCount,
    shot_count: form.shotCount,
    random_seed: form.randomSeed,
    measurement_mode: form.measurementMode,
    noise: {
      noise_type: form.noiseType,
      noise_strength: form.noiseType === "none" ? 0 : form.noiseStrength,
    },
    attack: {
      attack_type: form.attackType,
      fraction: isFractional ? form.fraction : 0,
      seed: form.attackSeed,
    },
  };
  const extras = parseExtraVerifiers(form.extraVerifiers);
  if (extras.length > 0) req.extra_authorized_verifiers = extras;
  return req;
}










export function buildDetectionRequest(
  result: SimulationResponse,
  message: string,
): DetectionRequest {
  return {
    protocol_version: result.protocol_version,
    signer_id: result.authorization.presented_signer,
    verifier_id: result.authorization.presented_verifier,
    message,
    measurement_mode: result.measurement_mode,
    declared_state_count: result.state_count,
    basis_counts: result.basis_counts,
    states: result.states.map((s) => ({
      index: s.index,
      basis: s.basis,
      expected_bit: s.expected_bit,
      probability_expected: s.probability_expected,
      matched: s.matched,
    })),
    authorized_signers: result.authorization.authorized_signers,
    authorized_verifiers: result.authorization.authorized_verifiers,
    reported_signer_authorized: result.authorization.signer_authorized,
    reported_verifier_authorized: result.authorization.verifier_authorized,
    verification: {
      available: true,
      accepted: result.verification.accepted,
      session_valid: result.verification.session_valid,
      message_valid: result.verification.message_valid,
      transcript_valid: result.verification.transcript_valid,
      state_sequence_valid: result.verification.state_sequence_valid,
      measurement_valid: result.verification.measurement_valid,
      errors: result.verification.errors,
      warnings: result.verification.warnings,
      declared_mismatch_count: result.verification.mismatch_count,
      declared_basis_counts: result.verification.basis_counts,
      measurement_summary: result.verification.measurement_summary,
    },
  };
}
