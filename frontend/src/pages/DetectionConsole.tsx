import { useEffect, useMemo, useState } from "react";
import {
  Gauge,
  Radar as RadarIcon,
  ScanSearch,
  ShieldAlert,
  SlidersHorizontal,
  Trash2,
} from "lucide-react";
import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
} from "recharts";
import { runDetection } from "../api/client";
import type { DetectionRequest, DetectionResponse } from "../api/types";
import { useApp } from "../state/AppContext";
import { useChartPalette } from "../state/chartPalette";
import {
  Badge,
  Button,
  Callout,
  Card,
  EmptyState,
  Field,
  JsonBlock,
  KeyValue,
  Spinner,
  Stat,
  TextArea,
  Toggle,
} from "../components/ui";
import { fmtNum, fmtPct, severityTone, statusTone, titleCase } from "../lib/format";
import { WorkStage, DetailsDisclosure } from "../components/workspace/WorkStage";

const EXAMPLE_REQUEST: DetectionRequest = {
  states: [],
  basis_counts: {},
  verification: { available: false },
  authorized_signers: [],
  authorized_verifiers: [],
  consume_replay: false,
};

export function DetectionConsole() {
  const { handoff, clearHandoff, pushToast, reportError } = useApp();
  const chart = useChartPalette();
  const [requestText, setRequestText] = useState<string>(() => JSON.stringify(EXAMPLE_REQUEST, null, 2));
  const [consumeReplay, setConsumeReplay] = useState(false);
  const [result, setResult] = useState<DetectionResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [origin, setOrigin] = useState<string | null>(null);

  useEffect(() => {
    if (handoff) {
      setRequestText(JSON.stringify(handoff.request, null, 2));
      setOrigin(handoff.origin);
      setResult(null);
    }
  }, [handoff]);

  async function handleRun() {
    let parsed: DetectionRequest;
    try {
      parsed = JSON.parse(requestText) as DetectionRequest;
    } catch {
      pushToast({
        variant: "error",
        title: "Invalid detection request JSON",
        message: "The body must be a JSON object of observable evidence only.",
      });
      return;
    }
    parsed.consume_replay = consumeReplay;
    setRunning(true);
    try {
      const res = await runDetection(parsed);
      setResult(res);
      pushToast({
        variant: res.finding_count > 0 ? "warn" : "success",
        title: `Detection complete · ${res.overall_status}`,
        message: `${res.finding_count} finding(s)`,
      });
    } catch (err) {
      reportError("Detection request failed", err);
    } finally {
      setRunning(false);
    }
  }

  const radarData = useMemo(() => {
    if (!result) return [];
    const f = result.features;
    const clamp01 = (v: number | null) => (v === null || Number.isNaN(v) ? 0 : Math.min(1, Math.max(0, v)));
    return [
      { metric: "Mismatch rate", value: clamp01(f.mismatch_rate) },
      { metric: "Disturbance rate", value: clamp01(f.verification_state_disturbance_rate) },
      { metric: "Recon. fidelity", value: clamp01(f.reconstruction_fidelity) },
      { metric: "Projective match", value: clamp01(f.projective_match_probability) },
      { metric: "Analytic fidelity", value: clamp01(f.fidelity.analytic_mean_fidelity) },
    ];
  }, [result]);

  return (
    <>
      <WorkStage
        index="04"
        name="Detection Console"
        subtitle="Evaluate observable evidence for statistical anomalies"
        lede="The detector receives observable evidence only — no attack type, no noise strength, no ground truth — and returns a finding plus its interpretation under the stated assumptions."
        action={
          <Button variant="primary" onClick={handleRun} loading={running}>
            <ScanSearch size={16} /> Run detection
          </Button>
        }
      />

      {origin && (
        <Callout variant="info" title={`Handoff received from ${origin}`}>
          The observable simulation data has been pre-filled below. The detector
          receives <strong>observable evidence only</strong> — no attack type, no
          noise strength, no ground truth. Unknown fields are rejected with HTTP 422.
          <div className="row" style={{ marginTop: 8 }}>
            <Button size="sm" variant="ghost" onClick={() => { clearHandoff(); setOrigin(null); }}>
              <Trash2 size={13} /> Clear handoff
            </Button>
          </div>
        </Callout>
      )}

      <Card
        title="Detection request"
        subtitle="POST /api/v1/detect — observable input only (extra fields forbidden)"
        icon={<ScanSearch size={17} />}
      >
        <div className="stack">
          <DetailsDisclosure summary="Observable evidence payload (raw JSON — technical)">
            <Field label="Observable evidence (JSON)">
              <TextArea rows={12} value={requestText} onChange={(e) => setRequestText(e.target.value)} />
            </Field>
          </DetailsDisclosure>
          <div className="row">
            <Toggle
              checked={consumeReplay}
              onChange={setConsumeReplay}
              label={<span>consume_replay <span className="faint">(record this event in the in-memory replay ledger)</span></span>}
            />
          </div>
          <div className="row">
            <Button variant="primary" onClick={handleRun} loading={running}>
              <ScanSearch size={15} /> Run detection
            </Button>
            <Button variant="ghost" onClick={() => setRequestText(JSON.stringify(EXAMPLE_REQUEST, null, 2))}>
              Reset to empty
            </Button>
          </div>
        </div>
      </Card>

      {running && <Spinner label="Running detector…" />}

      {!result && !running && (
        <Card>
          <EmptyState
            icon={<RadarIcon size={28} />}
            title="No detection result"
            body="Run detection over observable evidence, or send data from the Simulation Workbench."
          />
        </Card>
      )}

      {result && (
        <>
          <Card
            title="Detection result"
            subtitle={result.explanation}
            icon={<ShieldAlert size={17} />}
            actions={<Badge tone={statusTone(result.overall_status)}>{result.overall_status}</Badge>}
          >
            <div className="grid cols-4">
              <Stat label="Protocol valid" value={result.protocol_valid ? "YES" : "NO"} sub="structural check" />
              <Stat label="Findings" value={result.finding_count} sub="structured evidence items" />
              <Stat label="Mismatch rate" value={fmtPct(result.features.mismatch_rate)} sub={fmtNum(result.features.mismatch.mismatch_rate)} />
              <Stat label="Disturbance rate" value={fmtPct(result.features.disturbance.disturbance_rate)} sub={`tolerance ${fmtNum(result.features.disturbance.tolerance)}`} />
            </div>
          </Card>

          <Callout variant="evidence" title={`Security assessment · ${result.security_assessment.status}`}>
            <div className="row" style={{ marginBottom: 8 }}>
              <Badge tone="violet">formal_proof_present: {String(result.security_assessment.formal_proof_present)}</Badge>
              <Badge tone="info">ground_truth_used: {String(result.security_assessment.ground_truth_used)}</Badge>
            </div>
            {result.security_assessment.limitations.length > 0 && (
              <ul>
                {result.security_assessment.limitations.map((l, i) => (
                  <li key={i}>{l}</li>
                ))}
              </ul>
            )}
            <p className="note" style={{ marginTop: 8 }}>
              Detection produces evidence about one observable event. It is not a
              verdict and it cannot establish that a session is secure.
            </p>
          </Callout>

          <div className="grid side-2">
            <Card title={`Findings (${result.findings.length})`} icon={<ShieldAlert size={17} />}>
              {result.findings.length === 0 ? (
                <EmptyState title="No findings" body="The detector surfaced no structured evidence for this input." />
              ) : (
                <div className="stack">
                  {result.findings.map((f) => (
                    <div className="finding" key={f.finding_id}>
                      <div className="finding-head">
                        <Badge tone={severityTone(f.severity)}>{f.severity}</Badge>
                        <strong style={{ fontSize: 13, color: "var(--text-hi)" }}>{titleCase(f.category)}</strong>
                        {f.blocking && <Badge tone="danger">BLOCKING</Badge>}
                        <Badge tone="neutral">{f.calibration}</Badge>
                        {f.strength !== null && <span className="chip">strength {fmtNum(f.strength, 3)}</span>}
                        <span className="fid">{f.finding_id}</span>
                      </div>
                      <div className="finding-body">
                        <p>{f.explanation}</p>
                        {f.evidence_items.length > 0 && (
                          <div className="table-wrap">
                            <table className="data">
                              <thead>
                                <tr>
                                  <th>Evidence</th>
                                  <th>Observed</th>
                                  <th>Expected</th>
                                  <th>Source</th>
                                </tr>
                              </thead>
                              <tbody>
                                {f.evidence_items.map((e, i) => (
                                  <tr key={i}>
                                    <td className="mono">{e.name}</td>
                                    <td className="mono wrap">{fmtVal(e.observed)}</td>
                                    <td className="mono wrap">{fmtVal(e.expected)}</td>
                                    <td className="faint">{e.source}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                        {f.notes.length > 0 && (
                          <ul className="clean-list">
                            {f.notes.map((n, i) => (
                              <li key={i} className="note">• {n}</li>
                            ))}
                          </ul>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            <Card title="Diagnostic radar" subtitle="Evidence, never a decision" icon={<Gauge size={17} />}>
              <div className="chart-box" style={{ height: 260 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <RadarChart data={radarData} outerRadius="72%">
                    <PolarGrid stroke={chart.grid} />
                    <PolarAngleAxis dataKey="metric" tick={{ fill: chart.tick, fontSize: 10 }} />
                    <PolarRadiusAxis domain={[0, 1]} tick={{ fill: chart.axis, fontSize: 9 }} />
                    <Radar dataKey="value" stroke={chart.slate} fill={chart.accent} fillOpacity={0.22} />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
            </Card>
          </div>

          <div className="grid cols-2">
            <Card title="Feature analysis" icon={<SlidersHorizontal size={17} />}>
              <KeyValue
                entries={[
                  ["Mismatch (valid/total)", `${result.features.mismatch.n_mismatch} / ${result.features.mismatch.n_valid} (of ${result.features.mismatch.n_total})`],
                  ["Mismatch rate", fmtNum(result.features.mismatch.mismatch_rate)],
                  ["Disturbance (n/total)", `${result.features.disturbance.n_disturbed} / ${result.features.disturbance.n_verification_states}`],
                  ["Identical to mismatch", String(result.features.disturbance.identical_to_mismatch)],
                  ["Analytic mean fidelity", fmtNum(result.features.fidelity.analytic_mean_fidelity)],
                  ["Mean mismatch probability", fmtNum(result.features.fidelity.mean_mismatch_probability)],
                  ["Sampled match frequency", fmtNum(result.features.fidelity.sampled_match_frequency)],
                  ["Reconstruction fidelity", fmtNum(result.features.reconstruction_fidelity)],
                  ["Projective match prob.", fmtNum(result.features.projective_match_probability)],
                  ["State count consistent", fmtBool(result.features.state_count_consistency)],
                  ["Transcript validity", fmtBool(result.features.transcript_validity)],
                  ["Session consistency", fmtBool(result.features.session_consistency)],
                  ["Signer authorization", fmtBool(result.features.signer_authorization_validity)],
                  ["Verifier authorization", fmtBool(result.features.verifier_authorization_validity)],
                ]}
              />
            </Card>

            <Card title="Basis statistics" icon={<SlidersHorizontal size={17} />}>
              <div className="stack">
                <div className="row">
                  {result.features.basis.observed_bases.map((b) => (
                    <span key={b} className="chip">
                      {b}: {result.features.basis.counts[b] ?? 0}
                      {result.features.basis.mismatch_rates[b] != null &&
                        ` · mismatch ${fmtPct(result.features.basis.mismatch_rates[b])}`}
                    </span>
                  ))}
                </div>
                {result.features.basis.disturbed_bases.length > 0 && (
                  <Callout variant="warn" title="Disturbed bases">
                    {result.features.basis.disturbed_bases.join(", ")}
                  </Callout>
                )}
                <div>
                  <div className="stat-label" style={{ marginBottom: 6 }}>Distribution</div>
                  <JsonBlock data={result.features.basis.distribution} maxHeight={160} />
                </div>
              </div>
            </Card>
          </div>

          <DetailsDisclosure summary="Raw detection response (JSON — full technical detail)">
            <JsonBlock data={result} maxHeight={420} />
          </DetailsDisclosure>
        </>
      )}
    </>
  );
}

function fmtVal(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") return fmtNum(v);
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function fmtBool(v: boolean | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return v ? "true" : "false";
}
