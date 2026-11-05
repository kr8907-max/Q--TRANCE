











import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { FlaskConical } from "lucide-react";
import type { ObservabilityResponse, ReferenceCalibrationResponse } from "../../api/types";
import { useChartPalette } from "../../state/chartPalette";
import { Badge, Callout, EmptyState } from "../ui";
import { fmtPct, titleCase } from "../../lib/format";

interface EvidencePanelProps {
  reference: ReferenceCalibrationResponse | null;
  observability: ObservabilityResponse | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}

interface RateRow {
  threat: string;
  detection: number | null;
  far: number | null;
}

function pctTick(v: number) {
  return `${Math.round(v * 100)}%`;
}

export function EvidencePanel({ reference, observability, loading, error, onRetry }: EvidencePanelProps) {
  const chart = useChartPalette();
  const op = reference?.recorded_operating_point ?? null;

  const rows: RateRow[] = (observability?.rows ?? [])
    .filter((r) => r.empirically_evaluated && r.m5_detection_rate !== null)
    .map((r) => ({
      threat: titleCase(r.threat),
      detection: r.m5_detection_rate,
      far: r.m5_far,
    }));

  if (loading) {
    return (
      <div className="cc-panel cc-evidence" aria-busy="true" aria-label="Loading evidence">
        <div className="cc-panel-head">
          <span className="cc-panel-kicker">Evidence</span>
          <div className="cc-skel" style={{ width: 180, height: 14 }} />
        </div>
        <div className="cc-skel" style={{ width: 140, height: 44 }} />
        <div className="cc-skel" style={{ width: "100%", height: 180 }} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="cc-panel cc-evidence">
        <div className="cc-panel-head">
          <span className="cc-panel-kicker">Evidence</span>
          <h3>Calibrated expectation</h3>
        </div>
        <Callout variant="danger" title="Backend evidence unavailable">
          Live evidence cannot currently be retrieved. {error}
          <div style={{ marginTop: 10 }}>
            <button type="button" className="btn ghost sm" onClick={onRetry}>
              Retry
            </button>
          </div>
        </Callout>
      </div>
    );
  }

  if (!op && rows.length === 0) {
    return (
      <div className="cc-panel cc-evidence">
        <div className="cc-panel-head">
          <span className="cc-panel-kicker">Evidence</span>
          <h3>Calibrated expectation</h3>
        </div>
        <EmptyState
          icon={<FlaskConical size={22} />}
          title="No calibrated reference yet"
          body="Run the Calibration Lab to derive a decision threshold from honest-only data; it will appear here as the reference expectation."
        />
      </div>
    );
  }


  return (
    <div className="cc-panel cc-evidence">
      <div className="cc-panel-head">
        <span className="cc-panel-kicker">Evidence</span>
        <h3>Calibrated expectation</h3>
        <p className="cc-panel-sub">
          Reference operating point from honest-only calibration. Observed runs are
          compared against this expectation by the detector.
        </p>
      </div>

      <div className="cc-evidence-grid">
        <div className="cc-evidence-metric">
          <div className="cc-metric-label">Threshold rate</div>
          <div className="cc-metric-value mono">{op ? fmtPct(op.threshold_rate) : "—"}</div>
          {op && (
            <div className="cc-metric-sub">
              p_upper {fmtPct(op.p_upper)} · critical count {op.critical_count} / {op.state_count} states
            </div>
          )}
          {op && (
            <div className="cc-kv-mini mono">
              <span>config {op.name}</span>
              <span>
                {op.noise_type} · strength {op.noise_strength}
              </span>
              <span>{op.calibration_sessions} calibration sessions</span>
              <span>
                α {op.alpha} · FRR {op.observed_calibration_frr === null ? "—" : fmtPct(op.observed_calibration_frr)}
              </span>
            </div>
          )}
          {reference?.security_assessment && (
            <div className="cc-evidence-status">
              <Badge tone="info">{reference.security_assessment.status}</Badge>
              {reference.security_assessment.limitations[0] && (
                <p className="cc-note">{reference.security_assessment.limitations[0]}</p>
              )}
            </div>
          )}
        </div>


        {rows.length > 0 && (
          <div className="cc-evidence-chart">
            <div className="cc-chart-head">
              <span className="cc-chart-title">Empirical detection rate per modelled attack</span>
              <span className="cc-chart-sub mono">{observability?.source ?? "M5 evaluation"}</span>
            </div>
            <ResponsiveContainer width="100%" height={210}>
              <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -14 }} barGap={3}>
                <CartesianGrid stroke={chart.grid} vertical={false} />
                <XAxis
                  dataKey="threat"
                  tick={{ fill: chart.tick, fontSize: 10.5 }}
                  axisLine={{ stroke: chart.axis }}
                  tickLine={false}
                  interval={0}
                  angle={-18}
                  textAnchor="end"
                  height={46}
                />
                <YAxis
                  domain={[0, 1]}
                  tickFormatter={pctTick}
                  tick={{ fill: chart.tick, fontSize: 10.5 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  cursor={{ fill: chart.cursor }}
                  contentStyle={{
                    background: chart.tooltipBg,
                    border: `1px solid ${chart.tooltipBorder}`,
                    borderRadius: 10,
                    fontSize: 12,
                  }}
                  formatter={(value: unknown, name: unknown) => [
                    typeof value === "number" ? fmtPct(value) : "—",
                    name === "detection" ? "Detection rate" : "False-accept rate",
                  ]}
                />
                <Bar dataKey="detection" name="detection" fill={chart.accent} radius={[5, 5, 0, 0]} maxBarSize={26} />
                <Bar dataKey="far" name="far" fill={chart.slate} radius={[5, 5, 0, 0]} maxBarSize={26} opacity={0.75} />
              </BarChart>
            </ResponsiveContainer>
            <p className="cc-note">
              Rates are empirical, finite-sample and configuration-dependent; they do not
              transfer to other configurations.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
