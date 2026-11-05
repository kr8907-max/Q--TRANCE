










import { ArrowRight } from "lucide-react";
import type { SessionSummary, ObservabilityResponse, ReferenceCalibrationResponse } from "../../api/types";
import { useApp, type ViewKey } from "../../state/AppContext";
import { Badge } from "../ui";
import { fmtPct, lifecycleTone, shortId, timeLabel } from "../../lib/format";

interface FocusPanelProps {
  focus: string | null;
  latest: SessionSummary | null;
  reference: ReferenceCalibrationResponse | null;
  observability: ObservabilityResponse | null;
  online: boolean;
}

const STAGE_INFO: Record<string, { name: string; view: ViewKey; blurb: string }> = {
  create: { name: "Create", view: "sessions", blurb: "Establish a signing session and bind a message to a protocol run." },
  simulate: { name: "Simulate", view: "simulation", blurb: "Run the protocol under modelled noise and attack conditions." },
  observe: { name: "Observe", view: "simulation", blurb: "Inspect the observable protocol and measurement output." },
  detect: { name: "Detect", view: "detection", blurb: "Evaluate observable evidence for statistical anomalies." },
  calibrate: { name: "Calibrate", view: "calibration", blurb: "Derive the honest-only expectation and decision threshold." },
  evaluate: { name: "Evaluate", view: "evaluation", blurb: "Measure empirical detector performance across modelled attacks." },
  explain: { name: "Explain", view: "security", blurb: "Read the assumptions, observability and security boundaries." },
};

export function FocusPanel({ focus, latest, reference, observability, online }: FocusPanelProps) {
  const { navigate } = useApp();


  if (focus && STAGE_INFO[focus]) {
    const s = STAGE_INFO[focus];
    return (
      <aside className="focus-panel" aria-live="polite">
        <span className="focus-kicker">Stage</span>
        <h3 className="focus-title">{s.name}</h3>
        <p className="focus-blurb">{s.blurb}</p>
        <button type="button" className="btn ghost sm" onClick={() => navigate(s.view)} disabled={!online}>
          Open {s.name} <ArrowRight size={14} />
        </button>
      </aside>
    );
  }


  const op = reference?.recorded_operating_point ?? null;
  const covered = observability?.covered_count ?? null;
  const assessed = observability?.security_assessment?.status ?? null;

  return (
    <aside className="focus-panel" aria-live="polite">
      <span className="focus-kicker">Current investigation</span>
      <h3 className="focus-title">
        {latest ? <span className="mono">{shortId(latest.session_id, 14)}</span> : "No investigation"}
      </h3>
      {latest && (
        <div className="focus-meta">
          <Badge tone={lifecycleTone(latest.lifecycle)}>{latest.lifecycle}</Badge>
          <span className="focus-chip mono">{latest.state_count} states</span>
          <span className="focus-chip mono">{timeLabel(latest.created_at)}</span>
        </div>
      )}

      <ol className="focus-chain">
        <ChainStep
          k="Observation"
          value={latest ? `${latest.state_count} states · ${latest.protocol_status}` : "—"}
          state={latest ? "set" : "await"}
        />
        <ChainStep
          k="Evidence"
          value={latest?.has_transcript ? `transcript ${shortId(latest.transcript_hash, 10)}` : "awaiting signature"}
          state={latest?.has_transcript ? "set" : "await"}
        />
        <ChainStep
          k="Finding"
          value={op ? `threshold ${fmtPct(op.threshold_rate)}` : "awaiting calibration"}
          state={op ? "set" : "await"}
        />
        <ChainStep
          k="Interpretation"
          value={assessed ? `${assessed}${covered !== null ? ` · ${covered} threats covered` : ""}` : "awaiting analysis"}
          state={assessed ? "set" : "await"}
        />
      </ol>

      <button
        type="button"
        className="btn primary sm"
        onClick={() => navigate(latest ? "detection" : "sessions")}
        disabled={!online}
      >
        {latest ? "Investigate detection" : "Create session"} <ArrowRight size={14} />
      </button>
    </aside>
  );
}

function ChainStep({ k, value, state }: { k: string; value: string; state: "set" | "await" }) {
  return (
    <li className={`chain-step ${state}`}>
      <span className="chain-k">{k}</span>
      <span className="chain-v mono">{value}</span>
    </li>
  );
}
