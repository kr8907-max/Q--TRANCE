











export const NOISE_TYPES = [
  "none",
  "depolarizing",
  "bit_flip",
  "phase_flip",
  "bit_phase_flip",
] as const;
export type NoiseType = (typeof NOISE_TYPES)[number];


export const ATTACK_TYPES = [
  "none",
  "forgery",
  "impersonation",
  "unauthorized_verification",
  "replay",
  "intercept_resend",
  "channel_tampering",
] as const;
export type AttackType = (typeof ATTACK_TYPES)[number];



export const FRACTIONAL_ATTACK_TYPES: readonly AttackType[] = [
  "intercept_resend",
  "channel_tampering",
];


export const MEASUREMENT_MODES = ["projective-analytic", "sampled"] as const;
export type MeasurementMode = (typeof MEASUREMENT_MODES)[number];


export const PROTOCOL_VERSION = "RQDS-TP-1.0";
export const DEFAULT_STATE_COUNT = 16;
export const MAX_STATE_COUNT = 4096;


export const MAX_SEED = 2 ** 63 - 1;



export type ServiceStatus = "ok" | "degraded";

export interface ApiErrorBody {
  code: string;
  message: string;
  request_id: string | null;
  details: Record<string, unknown> | null;
}

export interface ApiErrorResponse {
  error: ApiErrorBody;
}

export interface HealthResponse {
  status: ServiceStatus;
  api_version: string;
  protocol_version: string;
  application_version: string | null;
  environment: string;
  state: Record<string, number>;
}

export interface VersionResponse {
  application_version: string | null;
  api_version: string;
  protocol_version: string;
  python_version: string;
  packages: Record<string, string>;
}

export interface ReadyCheck {
  name: string;
  ok: boolean;
  detail: string | null;
}

export interface ReadyResponse {
  ready: boolean;
  checks: ReadyCheck[];
}



export interface SessionCreateRequest {
  message: string;
  signer_id: string;
  verifier_id: string;
  state_count?: number;
  protocol_version?: string;
}

export interface SessionView {
  session_id: string;
  nonce: string;
  protocol_version: string;
  protocol_status: string;
  lifecycle: string;
  state_count: number;
  message_hash: string;
  message_binding: string;
  created_at: string;
  signer_id: string;
  verifier_id: string;
  history: string[];
}

export interface SessionSignResponse {
  session_id: string;
  lifecycle: string;
  protocol_status: string;
  transcript: Record<string, unknown>;
  transcript_hash: string;
  state_count: number;
  signer_id: string;
  verifier_id: string;
  created_at: string;
  history: string[];
}

export interface SessionSummary {
  session_id: string;
  lifecycle: string;
  protocol_status: string;
  signer_id: string;
  verifier_id: string;
  state_count: number;
  created_at: string;
  has_transcript: boolean;
  transcript_hash: string | null;
}

export interface SessionListResponse {
  sessions: SessionSummary[];
  total: number;
}



export interface VerifierContextIn {
  verifier_id: string;
  expected_protocol_version?: string | null;
}

export interface VerificationResultView {
  accepted: boolean;
  session_valid: boolean;
  message_valid: boolean;
  transcript_valid: boolean;
  state_sequence_valid: boolean;
  measurement_valid: boolean;
  errors: string[];
  warnings: string[];
  state_count: number;
  mismatch_count: number;
  basis_counts: Record<string, number>;
  measurement_summary: Record<string, number>;
}

export interface VerificationRequest {
  message: string;
  transcript: Record<string, unknown>;
  verifier_context: VerifierContextIn;
  session_id?: string | null;
}

export interface VerificationResponse extends VerificationResultView {
  session_id: string | null;
  lifecycle: string | null;
  note: string;
}



export interface NoiseSpec {
  noise_type?: NoiseType;
  noise_strength?: number;
}

export interface AttackSpec {
  attack_type?: AttackType;
  fraction?: number;
  seed?: number;
  parameters?: Record<string, unknown>;
}

export interface SimulationRequest {
  scenario_id?: string;
  message?: string;
  signer_id?: string;
  verifier_id?: string;
  protocol_version?: string;
  state_count?: number;
  shot_count?: number;
  random_seed?: number;
  measurement_mode?: MeasurementMode;
  noise?: NoiseSpec;
  attack?: AttackSpec;
  extra_authorized_verifiers?: string[];
}

export interface StateObservationOut {
  index: number;
  basis: string;
  expected_bit: number;
  probability_expected: number;
  matched: boolean;
}

export interface AuthorizationObservationsOut {
  presented_signer: string;
  presented_verifier: string;
  authorized_signers: string[];
  authorized_verifiers: string[];
  signer_authorized: boolean;
  verifier_authorized: boolean;
}

export interface GroundTruthOut {
  label: string;
  scenario_id: string;
  is_malicious: boolean;
  noise: Record<string, unknown>;
  attack: Record<string, unknown>;
  notes: string[];
}

export interface SimulationResponse {
  scenario_id: string;
  protocol_version: string;
  state_count: number;
  measurement_mode: string;
  simulator_seed: number;
  mismatch_count: number;
  mismatch_proportion: number;
  mean_channel_disturbance: number;
  basis_counts: Record<string, number>;
  states: StateObservationOut[];
  verification: VerificationResultView;
  authorization: AuthorizationObservationsOut;
  runtime_seconds: number | null;
  observable_only: boolean;
  note: string;
}

export interface SimulationEvaluationResponse extends SimulationResponse {
  ground_truth: GroundTruthOut;
  observable_only: false;
}



export interface StateEvidenceIn {
  index: number;
  basis?: string | null;
  expected_bit?: number | null;
  probability_expected?: number | null;
  matched?: boolean | null;
}

export interface VerificationEvidenceIn {
  available?: boolean;
  accepted?: boolean | null;
  session_valid?: boolean | null;
  message_valid?: boolean | null;
  transcript_valid?: boolean | null;
  state_sequence_valid?: boolean | null;
  measurement_valid?: boolean | null;
  errors?: string[];
  warnings?: string[];
  declared_mismatch_count?: number | null;
  declared_basis_counts?: Record<string, number>;
  measurement_summary?: Record<string, number>;
}


export interface DetectionRequest {
  session_id?: string | null;
  nonce?: string | null;
  protocol_version?: string | null;
  message_binding?: string | null;
  declared_transcript_hash?: string | null;
  signer_id?: string | null;
  verifier_id?: string | null;
  created_at?: string | null;
  message?: string | null;
  verifier_context_id?: string | null;
  expected_protocol_version?: string | null;
  authorized_signers?: string[];
  authorized_verifiers?: string[];
  reported_signer_authorized?: boolean | null;
  reported_verifier_authorized?: boolean | null;
  transcript_payload?: Record<string, unknown> | null;
  transcript_parse_error?: string | null;
  states?: StateEvidenceIn[];
  declared_state_count?: number | null;
  measurement_mode?: string | null;
  basis_counts?: Record<string, number>;
  verification?: VerificationEvidenceIn;
  consume_replay?: boolean;
}

export interface RateEstimateOut {
  successes: number;
  trials: number;
  confidence: number;
  rate: number | null;
  lower: number | null;
  upper: number | null;
  defined: boolean;
}

export interface MismatchAnalysisOut {
  n_total: number;
  n_valid: number;
  n_mismatch: number;
  n_missing: number;
  n_malformed: number;
  mismatch_rate: number | null;
  rate_estimate: RateEstimateOut | null;
  defined: boolean;
  notes: string[];
}

export interface DisturbanceAnalysisOut {
  n_verification_states: number;
  n_disturbed: number;
  n_undisturbed: number;
  n_missing: number;
  n_malformed: number;
  disturbance_rate: number | null;
  rate_estimate: RateEstimateOut | null;
  tolerance: number;
  defined: boolean;
  identical_to_mismatch: boolean;
  notes: string[];
}

export interface FidelityAnalysisOut {
  n_valid: number;
  n_malformed: number;
  analytic_mean_fidelity: number | null;
  analytic_min_fidelity: number | null;
  mean_mismatch_probability: number | null;
  sampled_match_frequency: number | null;
  sampled_match_count: number | null;
  measurement_mode: string | null;
  defined: boolean;
  notes: string[];
}

export interface BasisStatisticsOut {
  observed_bases: string[];
  counts: Record<string, number>;
  distribution: Record<string, number>;
  mismatch_counts: Record<string, number>;
  mismatch_rates: Record<string, number | null>;
  disturbance_counts: Record<string, number>;
  disturbance_rates: Record<string, number | null>;
  disturbed_bases: string[];
}

export interface DetectionFeaturesOut {
  mismatch: MismatchAnalysisOut;
  disturbance: DisturbanceAnalysisOut;
  fidelity: FidelityAnalysisOut;
  basis: BasisStatisticsOut;
  measurement_counts_by_basis: Record<string, number>;
  basis_distribution: Record<string, number>;
  mismatch_rate: number | null;
  projective_match_probability: number | null;
  reconstruction_fidelity: number | null;
  verification_state_disturbance_rate: number | null;
  state_count_consistency: boolean | null;
  transcript_validity: boolean | null;
  transcript_hash_validity: boolean | null;
  session_consistency: boolean | null;
  nonce_freshness_state: boolean | null;
  signer_authorization_validity: boolean | null;
  verifier_authorization_validity: boolean | null;
  cross_verifier_disagreement: unknown;
  redundancies: Record<string, string>;
  notes: string[];
}

export interface EvidenceItemOut {
  name: string;
  observed: unknown;
  expected: unknown;
  source: string;
  explanation: string;
}

export interface ThreatEvidenceOut {
  category: string;
  severity: string;
  calibration: string;
  blocking: boolean;
  explanation: string;
  finding_id: string;
  strength: number | null;
  evidence_items: EvidenceItemOut[];
  observed_values: Record<string, unknown>;
  comparison_values: Record<string, unknown>;
  source_metrics: string[];
  session_reference: string | null;
  timestamp: string | null;
  notes: string[];
}

export interface DetectionAssessment {
  status: string;
  formal_proof_present: boolean;
  ground_truth_used: boolean;
  limitations: string[];
}

export interface DetectionResponse {
  protocol_valid: boolean;
  overall_status: string;
  explanation: string;
  finding_count: number;
  findings: ThreatEvidenceOut[];
  features: DetectionFeaturesOut;
  diagnostic_statistics: Record<string, unknown>;
  session_reference: string | null;
  notes: string[];
  security_assessment: DetectionAssessment;
}



export interface CalibrationConfigOut {
  config_id: string;
  protocol_version: string;
  noise_type: string;
  noise_strength: number;
  state_count: number;
  measurement_mode: string;
  shot_count: number;
  statistic: string;
  confidence: number;
  seed_start: number;
  session_count: number;
  dataset_role: string;
}

export interface ConfidenceIntervalOut {
  lower: number;
  upper: number;
  confidence: number;
  method: string;
  one_sided: boolean;
  successes: number;
  trials: number;
  width: number;
}

export interface HomogeneityOut {
  homogeneous: boolean;
  spread: number;
  tolerance: number;
  minimum: number;
  maximum: number;
  mean: number;
  state_count: number;
  notes: string[];
  omitted: string;
}

export interface ThresholdOut {
  state_count: number;
  p_upper: number;
  critical_count: number;
  threshold_rate: number;
  method: string;
  alpha: number;
  calibration_alpha: number;
  evaluation_alpha: number;
  calibration_fingerprint: string;
  calibration_session_count: number;
  calibration_total_valid: number;
  calibration_total_mismatch: number;
  calibration_pooled_rate: number | null;
  calibration_role: string;
}

export interface OperatingPointOut {
  name: string;
  protocol_version: string;
  noise_type: string;
  noise_strength: number;
  state_count: number;
  measurement_mode: string;
  shot_count: number;
  calibration_seed_start: number;
  calibration_seed_end: number;
  observed_calibration_frr: number | null;
  threshold: ThresholdOut;
  notes: string[];
}

export interface CalibrationRunRequest {
  config_id?: string;
  protocol_version?: string;
  noise_type?: NoiseType;
  noise_strength?: number;
  state_count?: number;
  measurement_mode?: MeasurementMode;
  shot_count?: number;
  confidence?: number;
  seed_start?: number;
  session_count?: number;
}

export interface CalibrationAssessment {
  status: string;
  formal_proof_present: boolean;
  limitations: string[];
}

export interface CalibrationResponse {
  calibration_id: string;
  config: CalibrationConfigOut;
  total_valid: number;
  total_mismatch: number;
  pooled_rate: number | null;
  interval: ConfidenceIntervalOut | null;
  upper_bound: ConfidenceIntervalOut | null;
  homogeneity: HomogeneityOut;
  threshold: ThresholdOut;
  operating_point: OperatingPointOut;
  notes: string[];
  security_assessment: CalibrationAssessment;
}

export interface RecordedOperatingPointOut {
  name: string;
  protocol_version: string;
  statistic: string;
  state_count: number;
  measurement_mode: string;
  shot_count: number;
  p_upper: number;
  critical_count: number;
  threshold_rate: number;
  alpha: number;
  noise_type: string;
  noise_strength: number;
  calibration_sessions: number;
  observed_calibration_frr: number | null;
}

export interface ReferenceCalibrationResponse {
  methodology: string;
  statistic: string;
  operating_point_name: string;
  alpha: number;
  calibration_alpha: number;
  evaluation_alpha: number;
  recorded_operating_point: RecordedOperatingPointOut | null;
  provenance: Record<string, unknown>;
  limitations: string[];
  security_assessment: CalibrationAssessment;
}



export type EvaluationProfile = "smoke" | "reference";

export interface EvaluationRunRequest {
  profile: EvaluationProfile;
}

export interface ConfusionMatrixOut {
  tp: number;
  tn: number;
  fp: number;
  fn: number;
  total: number | null;
  honest: number | null;
  malicious: number | null;
}

export interface MetricsOut {
  confusion: ConfusionMatrixOut;
  detection_rate: number | null;
  far: number | null;
  frr: number | null;
  tpr: number | null;
  tnr: number | null;
  specificity: number | null;
  fnr: number | null;
  fpr: number | null;
  precision: number | null;
  recall: number | null;
  f1: number | null;
  accuracy: number | null;
  far_definition: string | null;
  frr_definition: string | null;
  note: string | null;
}

export interface EvaluationConfigurationOut {
  profile: string;
  description: string;
  state_count: number;
  calibration_sessions: number;
  evaluation_trials: number;
  measurement_mode: string;
  shot_count: number;
  noise_type: string;
  reference_noise_strength: number;
  attack_types: string[];
  attack_fraction: number;
  seed_base: number;
}

export interface EvaluationAssessment {
  status: string;
  ground_truth_used: boolean;
  formal_proof_present: boolean;
  limitations: string[];
}

export interface EvaluationSummary {
  evaluation_id: string;
  profile: string;
  dataset_role: string;
  seed_base: number;
  configuration: EvaluationConfigurationOut;
  operating_point: RecordedOperatingPointOut | null;
  by_attack_type: Record<string, MetricsOut>;
  honest_frr_by_noise: Record<string, number | null>;
  detection_by_noise_and_attack: Record<string, Record<string, number>>;
  curve_names: string[];
  sample_size_rows: number;
  runtime_seconds: number | null;
  ground_truth_used: boolean;
  security_assessment: EvaluationAssessment;
  note: string;
}

export interface EvaluationArtifactResponse {
  evaluation_id: string;
  profile: string;
  artifact: Record<string, unknown>;
  markdown: string | null;
  size_warning: string;
}



export interface SecurityAssessment {
  status: string;
  formal_proof_present: boolean;
  composable_security_established: boolean;
  universal_detection_guarantee: boolean;
  forgery_bound_derived: boolean;
  limitations: string[];
}

export interface AssumptionOut {
  key: string;
  statement: string;
  status: string;
  evidence: string;
  consequence_if_violated: string;
  citation: string | null;
}

export interface AssumptionsResponse {
  noise_type: string;
  measurement_mode: string;
  assumptions: AssumptionOut[];
  summary: Record<string, number>;
  weaker_than_exact: string[];
  by_status: Record<string, string[]>;
  note: string;
  security_assessment: SecurityAssessment;
}

export interface ObservabilityRowOut {
  threat: string;
  quantum_disturbance: boolean;
  protocol_anomaly: boolean;
  authentication_evidence: boolean;
  replay_evidence: boolean;
  detector_visible_quantum: boolean;
  requires_classical_control: boolean;
  empirically_evaluated: boolean;
  covered_by_prototype: boolean;
  m5_detection_rate: number | null;
  m5_far: number | null;
  notes: string[];
}

export interface ObservabilityResponse {
  rows: ObservabilityRowOut[];
  quantum_visible: string[];
  classical_only: string[];
  empirically_evaluated_count: number;
  covered_count: number;
  source: string;
  security_assessment: SecurityAssessment;
}

export interface CompositionRowOut {
  component: string;
  property_evaluated: string;
  evidence_source: string;
  assumption_boundary: string;
  composition_dependency: string;
  unresolved_dependency: string;
  security_conclusion: string;
}

export interface CompositionResponse {
  components: CompositionRowOut[];
  component_count: number;
  unresolved_count: number;
  formal_composition_theorem_present: boolean;
  note: string;
  security_assessment: SecurityAssessment;
}

export interface AnalyzeRequest {
  statements: string[];
  context?: Record<string, unknown>;
}

export interface StatementCheckOut {
  statement: string;
  verdict: string;
  violations: string[];
  reasons: string[];
}

export interface AnalyzeResponse {
  checks: StatementCheckOut[];
  forbidden_claims: Record<string, string>[];
  banned_terminology: Record<string, string>[];
  allowed_statement_example: string | null;
  notes: string[];
  security_assessment: SecurityAssessment;
}
