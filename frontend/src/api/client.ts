/**
 * Typed HTTP client for the SIH26141 backend.
 *
 * - Base URL from VITE_API_BASE_URL (defaults to http://127.0.0.1:8000).
 * - Sends only the headers the backend CORS policy allows: Content-Type and
 *   X-Request-ID. Any other header would fail the preflight.
 * - Every non-2xx response is parsed against the backend's error envelope
 *   ({ error: { code, message, request_id, details } }) and surfaced as an
 *   ApiError, so the UI can always show error.code and error.message.
 */

import type {
  AnalyzeRequest,
  AnalyzeResponse,
  ApiErrorBody,
  AssumptionsResponse,
  CalibrationResponse,
  CalibrationRunRequest,
  CompositionResponse,
  DetectionRequest,
  DetectionResponse,
  EvaluationArtifactResponse,
  EvaluationProfile,
  EvaluationSummary,
  HealthResponse,
  NoiseType,
  MeasurementMode,
  ObservabilityResponse,
  ReadyResponse,
  ReferenceCalibrationResponse,
  SessionCreateRequest,
  SessionListResponse,
  SessionSignResponse,
  SessionView,
  SimulationEvaluationResponse,
  SimulationRequest,
  SimulationResponse,
  VerificationRequest,
  VerificationResponse,
  VersionResponse,
} from "./types";

export const API_BASE_URL: string = (
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000"
).replace(/\/+$/, "");

const API_PREFIX = "/api/v1";


export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly requestId: string | null;
  readonly details: Record<string, unknown> | null;

  constructor(body: ApiErrorBody, status: number) {
    super(body.message || `Request failed with code ${body.code}`);
    this.name = "ApiError";
    this.code = body.code;
    this.status = status;
    this.requestId = body.request_id ?? null;
    this.details = body.details ?? null;
  }
}

function newRequestId(): string {
  const c = globalThis.crypto;
  if (c && typeof c.randomUUID === "function") return c.randomUUID();
  return `req-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

interface RequestOptions {
  method?: "GET" | "POST";
  body?: unknown;
  query?: Record<string, string | number | undefined>;
  signal?: AbortSignal;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const url = new URL(`${API_BASE_URL}${path}`);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined) url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
}

async function parseErrorEnvelope(res: Response): Promise<ApiError> {
  let body: ApiErrorBody | null = null;
  try {
    const data = (await res.json()) as { error?: ApiErrorBody };
    if (data && typeof data === "object" && data.error) body = data.error;
  } catch {

  }
  if (!body) {
    body = {
      code: res.status === 0 ? "NETWORK_ERROR" : httpStatusToCode(res.status),
      message: res.statusText || `HTTP ${res.status}`,
      request_id: res.headers.get("X-Request-ID"),
      details: null,
    };
  }
  return new ApiError(body, res.status);
}

function httpStatusToCode(status: number): string {
  switch (status) {
    case 400:
      return "BAD_REQUEST";
    case 404:
      return "NOT_FOUND";
    case 409:
      return "CONFLICT";
    case 413:
      return "PAYLOAD_TOO_LARGE";
    case 422:
      return "UNPROCESSABLE_ENTITY";
    case 503:
      return "SERVICE_UNAVAILABLE";
    default:
      return status >= 500 ? "INTERNAL_ERROR" : "BAD_REQUEST";
  }
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, query, signal } = options;
  const headers: Record<string, string> = { "X-Request-ID": newRequestId() };
  const init: RequestInit = { method, headers, signal };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }

  let res: Response;
  try {
    res = await fetch(buildUrl(path, query), init);
  } catch (err) {

    const message =
      err instanceof TypeError
        ? err.message
        : "Network request failed. Is the backend running and reachable?";
    throw new ApiError(
      {
        code: "NETWORK_ERROR",
        message: `Cannot reach the API at ${API_BASE_URL}. ${message}`,
        request_id: headers["X-Request-ID"],
        details: null,
      },
      0,
    );
  }

  if (!res.ok) throw await parseErrorEnvelope(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}



export const getHealth = () => request<HealthResponse>("/health");
export const getReady = () => request<ReadyResponse>("/ready");
export const getVersion = () => request<VersionResponse>("/version");



export const createSession = (body: SessionCreateRequest) =>
  request<SessionView>(`${API_PREFIX}/sessions`, { method: "POST", body });

export const listSessions = () =>
  request<SessionListResponse>(`${API_PREFIX}/sessions`);

export const getSession = (sessionId: string) =>
  request<SessionView>(`${API_PREFIX}/sessions/${encodeURIComponent(sessionId)}`);

export const signSession = (sessionId: string) =>
  request<SessionSignResponse>(
    `${API_PREFIX}/sessions/${encodeURIComponent(sessionId)}/sign`,
    { method: "POST" },
  );

export const expireSession = (sessionId: string) =>
  request<SessionView>(
    `${API_PREFIX}/sessions/${encodeURIComponent(sessionId)}/expire`,
    { method: "POST" },
  );



export const verifyTranscript = (body: VerificationRequest) =>
  request<VerificationResponse>(`${API_PREFIX}/verify`, { method: "POST", body });



export const runSimulation = (body: SimulationRequest) =>
  request<SimulationResponse>(`${API_PREFIX}/simulations`, { method: "POST", body });

export const runSimulationEvaluation = (body: SimulationRequest) =>
  request<SimulationEvaluationResponse>(`${API_PREFIX}/simulations/evaluation`, {
    method: "POST",
    body,
  });



export const runDetection = (body: DetectionRequest) =>
  request<DetectionResponse>(`${API_PREFIX}/detect`, { method: "POST", body });



export const runCalibration = (body: CalibrationRunRequest) =>
  request<CalibrationResponse>(`${API_PREFIX}/calibration/run`, {
    method: "POST",
    body,
  });

export const getReferenceCalibration = () =>
  request<ReferenceCalibrationResponse>(`${API_PREFIX}/calibration/reference`);

export const getCalibration = (calibrationId: string) =>
  request<CalibrationResponse>(
    `${API_PREFIX}/calibration/${encodeURIComponent(calibrationId)}`,
  );



export const runEvaluation = (profile: EvaluationProfile) =>
  request<EvaluationSummary>(`${API_PREFIX}/evaluation/run`, {
    method: "POST",
    body: { profile },
  });

export const getEvaluation = (evaluationId: string) =>
  request<EvaluationSummary>(
    `${API_PREFIX}/evaluation/${encodeURIComponent(evaluationId)}`,
  );

export const getEvaluationArtifact = (evaluationId: string) =>
  request<EvaluationArtifactResponse>(
    `${API_PREFIX}/evaluation/${encodeURIComponent(evaluationId)}/artifact`,
  );



export const getAssumptions = (noiseType: NoiseType, measurementMode: MeasurementMode) =>
  request<AssumptionsResponse>(`${API_PREFIX}/security/assumptions`, {
    query: { noise_type: noiseType, measurement_mode: measurementMode },
  });

export const getObservability = () =>
  request<ObservabilityResponse>(`${API_PREFIX}/security/observability`);

export const getComposition = () =>
  request<CompositionResponse>(`${API_PREFIX}/security/composition`);

export const analyzeStatements = (body: AnalyzeRequest) =>
  request<AnalyzeResponse>(`${API_PREFIX}/security/analyze`, { method: "POST", body });
