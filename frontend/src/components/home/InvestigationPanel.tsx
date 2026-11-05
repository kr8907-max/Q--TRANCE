







import { useState } from "react";
import { Copy, Check, FileSignature } from "lucide-react";
import type { SessionSummary } from "../../api/types";
import { useApp } from "../../state/AppContext";
import { Badge, EmptyState } from "../ui";
import { lifecycleTone, shortId, timeLabel } from "../../lib/format";

interface InvestigationPanelProps {
  latest: SessionSummary | null;
  total: number | null;
  loading: boolean;
}

export function InvestigationPanel({ latest, total, loading }: InvestigationPanelProps) {
  const { navigate } = useApp();
  const [reveal, setReveal] = useState(false);
  const [copied, setCopied] = useState(false);

  function copyId() {
    if (!latest) return;
    const id = latest.session_id;
    if (navigator.clipboard?.writeText) {
      void navigator.clipboard.writeText(id).then(() => {
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1400);
      });
    }
  }

  return (
    <div className="cc-panel cc-investigation">
      <div className="cc-panel-head">
        <span className="cc-panel-kicker">Current Investigation</span>
        <h3>Latest session</h3>
        {total !== null && <span className="cc-panel-sub mono">{total} in memory</span>}
      </div>

      {loading ? (
        <div className="cc-skel" style={{ width: "100%", height: 120 }} />
      ) : !latest ? (
        <EmptyState
          icon={<FileSignature size={22} />}
          title="No session yet"
          body="Create and sign a reference session in the Session Studio to begin an investigation."
        />
      ) : (
        <div className="cc-inv">
          <div className="cc-inv-idrow">
            <button
              type="button"
              className="cc-inv-id mono"
              onClick={() => setReveal((r) => !r)}
              title={reveal ? "Click to collapse" : "Click to reveal full session ID"}
            >
              {reveal ? latest.session_id : shortId(latest.session_id, 14)}
            </button>
            <button
              type="button"
              className="btn ghost sm"
              onClick={copyId}
              title="Copy session ID"
              aria-label="Copy session ID"
            >
              {copied ? <Check size={14} /> : <Copy size={14} />}
            </button>
          </div>

          <div className="cc-inv-meta">
            <Badge tone={lifecycleTone(latest.lifecycle)}>{latest.lifecycle}</Badge>
            <span className="cc-inv-chip mono">{latest.protocol_status}</span>
            <span className="cc-inv-chip mono">{latest.state_count} states</span>
          </div>

          <dl className="cc-inv-kv">
            <div>
              <dt>Signer</dt>
              <dd className="mono">{latest.signer_id}</dd>
            </div>
            <div>
              <dt>Verifier</dt>
              <dd className="mono">{latest.verifier_id}</dd>
            </div>
            <div>
              <dt>Created</dt>
              <dd className="mono">{timeLabel(latest.created_at)}</dd>
            </div>
            <div>
              <dt>Transcript</dt>
              <dd className="mono">{latest.has_transcript ? shortId(latest.transcript_hash, 12) : "—"}</dd>
            </div>
          </dl>

          <button type="button" className="btn ghost sm" onClick={() => navigate("sessions")}>
            Open Session Studio
          </button>
        </div>
      )}
    </div>
  );
}
