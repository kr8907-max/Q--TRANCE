











import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowRight, RefreshCw } from "lucide-react";
import { useApp, type ViewKey } from "../state/AppContext";
import { getObservability, getReferenceCalibration, listSessions } from "../api/client";
import type {
  ObservabilityResponse,
  ReferenceCalibrationResponse,
  SessionSummary,
} from "../api/types";
import { Badge, Dot } from "../components/ui";
import { fmtInt } from "../lib/format";
import { InvestigationOrbit, type OrbitStage } from "../components/console/InvestigationOrbit";
import { FocusPanel } from "../components/console/FocusPanel";
import { EvidencePanel } from "../components/home/EvidencePanel";
import { ActivityTimeline } from "../components/home/ActivityTimeline";

interface ConsoleData {
  sessions: SessionSummary[];
  sessionTotal: number | null;
  reference: ReferenceCalibrationResponse | null;
  observability: ObservabilityResponse | null;
}

const EMPTY: ConsoleData = { sessions: [], sessionTotal: null, reference: null, observability: null };

const SYSTEM_LABEL: Record<string, string> = {
  checking: "Initializing",
  online: "Ready",
  degraded: "Degraded",
  offline: "Offline",
};

function counter(counts: Record<string, number>, keys: string[]): number {
  for (const k of keys) {
    const v = counts[k];
    if (typeof v === "number" && Number.isFinite(v)) return v;
  }
  return 0;
}

export function Console() {
  const { connection, navigate, refreshConnection } = useApp();
  const { status, health, ready, version, lastChecked } = connection;
  const counts = health?.state ?? {};

  const [data, setData] = useState<ConsoleData>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [focus, setFocus] = useState<string | null>(null);
  const alive = useRef(true);

  const online = status === "online" || status === "degraded";

  const load = useCallback(async () => {
    if (status !== "online" && status !== "degraded") {
      setData(EMPTY);
      setLoading(false);
      setLoadError(status === "offline" ? "The backend is unreachable." : null);
      return;
    }
    setLoading(true);
    setLoadError(null);
    try {
      const [sessionsRes, reference, observability] = await Promise.all([
        listSessions().catch(() => null),
        getReferenceCalibration().catch(() => null),
        getObservability().catch(() => null),
      ]);
      if (!alive.current) return;
      setData({
        sessions: sessionsRes?.sessions ?? [],
        sessionTotal: sessionsRes?.total ?? null,
        reference,
        observability,
      });
    } catch (e) {
      if (!alive.current) return;
      setLoadError(e instanceof Error ? e.message : "Failed to load console data.");
    } finally {
      if (alive.current) setLoading(false);
    }
  }, [status]);

  useEffect(() => {
    alive.current = true;
    void load();
    return () => { alive.current = false; };
  }, [load]);

  const countsSig = JSON.stringify(counts);
  useEffect(() => {
    if (online) void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [countsSig]);

  const latest = data.sessions[0] ?? null;
  const sessionCount = data.sessionTotal ?? counts.sessions ?? 0;
  const calibrationCount = (counts.calibrations ?? 0) + (data.reference?.recorded_operating_point ? 1 : 0);
  const evaluationCount = counts.evaluations ?? 0;
  const simulations = counter(counts, ["simulations", "simulation_runs", "runs"]);
  const detections = counter(counts, ["detections", "detection_runs", "replay_ledger"]);


  const stages: OrbitStage[] = [
    { key: "create", label: "Create", view: "sessions", state: !online ? "offline" : sessionCount > 0 ? "complete" : "ready", meta: sessionCount > 0 ? String(sessionCount) : undefined },
    { key: "simulate", label: "Simulate", view: "simulation", state: !online ? "offline" : simulations > 0 ? "complete" : "ready" },
    { key: "observe", label: "Observe", view: "simulation", state: !online ? "offline" : simulations > 0 ? "complete" : "ready" },
    { key: "detect", label: "Detect", view: "detection", state: !online ? "offline" : detections > 0 ? "complete" : "ready" },
    { key: "calibrate", label: "Calibrate", view: "calibration", state: !online ? "offline" : calibrationCount > 0 ? "complete" : "ready", meta: calibrationCount > 0 ? String(calibrationCount) : undefined },
    { key: "evaluate", label: "Evaluate", view: "evaluation", state: !online ? "offline" : evaluationCount > 0 ? "complete" : "ready", meta: evaluationCount > 0 ? String(evaluationCount) : undefined },
    { key: "explain", label: "Explain", view: "security", state: online ? "ready" : "offline" },
  ];


  let next: { label: string; view: ViewKey } | null = null;
  if (status === "offline") next = null;
  else if (sessionCount === 0) next = { label: "Create your first session", view: "sessions" };
  else if (calibrationCount === 0) next = { label: "Run a calibration", view: "calibration" };
  else if (evaluationCount === 0) next = { label: "Run an evaluation benchmark", view: "evaluation" };
  else next = { label: "Open the detection console", view: "detection" };

  const statusTone =
    status === "online" ? "ok" : status === "degraded" ? "warn" : status === "offline" ? "danger" : "idle";

  return (
    <div className="console">

      <div className="console-ribbon" role="status" aria-label="System status">
        <span className="console-ribbon-item">
          <Dot tone={statusTone} pulse={status === "checking"} />
          <strong>{SYSTEM_LABEL[status]}</strong>
        </span>
        {ready && (
          <span className="console-ribbon-item">
            <Badge tone={ready.ready ? "ok" : "danger"}>{ready.ready ? "READY" : "NOT READY"}</Badge>
          </span>
        )}
        <span className="console-ribbon-item mono faint">{fmtInt(sessionCount)} sessions</span>
        <span className="console-ribbon-item mono faint">{fmtInt(calibrationCount)} calibrations</span>
        <span className="console-ribbon-item mono faint">{fmtInt(evaluationCount)} evaluations</span>
        {version && <span className="console-ribbon-item mono faint">api v{version.api_version}</span>}
        <button type="button" className="btn ghost sm console-refresh" onClick={refreshConnection} title="Re-probe /health and /ready" aria-label="Refresh system status">
          <RefreshCw size={13} />
        </button>
      </div>


      <div className="console-hero">
        <div className="orbit-panel">
          <InvestigationOrbit
            stages={stages}
            sessionId={latest?.session_id ?? null}
            online={online}
            onNavigate={(v) => navigate(v)}
            onFocus={setFocus}
            className="orbit-wrap"
          />
          {next && (
            <button type="button" className="orbit-next" onClick={() => navigate(next!.view)}>
              <span className="orbit-next-k">Next</span>
              <span className="orbit-next-l">{next.label}</span>
              <ArrowRight size={15} />
            </button>
          )}
        </div>
        <FocusPanel
          focus={focus}
          latest={latest}
          reference={data.reference}
          observability={data.observability}
          online={online}
        />
      </div>


      <EvidencePanel
        reference={data.reference}
        observability={data.observability}
        loading={loading}
        error={loadError}
        onRetry={() => { refreshConnection(); void load(); }}
      />


      <ActivityTimeline sessions={data.sessions} lastChecked={lastChecked} loading={loading} />
    </div>
  );
}
