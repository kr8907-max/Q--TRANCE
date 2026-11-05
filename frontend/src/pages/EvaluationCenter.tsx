import { useMemo, useState } from "react";
import {
  BarChart3,
  FileText,
  Grid3x3,
  Play,
  Table2,
  Waves,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getEvaluation, getEvaluationArtifact, runEvaluation } from "../api/client";
import type {
  ConfusionMatrixOut,
  EvaluationArtifactResponse,
  EvaluationProfile,
  EvaluationSummary,
  MetricsOut,
} from "../api/types";
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
  Select,
  Spinner,
  Stat,
  TextInput,
} from "../components/ui";
import { fmtNum, fmtPct } from "../lib/format";
import { WorkStage } from "../components/workspace/WorkStage";

type MetricKey =
  | "detection_rate"
  | "far"
  | "frr"
  | "precision"
  | "recall"
  | "f1"
  | "accuracy";

const METRIC_OPTIONS: { value: MetricKey; label: string }[] = [
  { value: "detection_rate", label: "Detection rate" },
  { value: "far", label: "FAR (false acceptance)" },
  { value: "frr", label: "FRR (false rejection)" },
  { value: "precision", label: "Precision" },
  { value: "recall", label: "Recall" },
  { value: "f1", label: "F1" },
  { value: "accuracy", label: "Accuracy" },
];

export function EvaluationCenter() {
  const { pushToast, reportError } = useApp();
  const chart = useChartPalette();
  const [profile, setProfile] = useState<EvaluationProfile>("smoke");
  const [result, setResult] = useState<EvaluationSummary | null>(null);
  const [artifact, setArtifact] = useState<EvaluationArtifactResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [loadingArtifact, setLoadingArtifact] = useState(false);
  const [lookupId, setLookupId] = useState("");
  const [attack, setAttack] = useState<string>("");
  const [metric, setMetric] = useState<MetricKey>("detection_rate");
  const [reportTab, setReportTab] = useState<"markdown" | "artifact">("markdown");

  const attacks = useMemo(() => (result ? Object.keys(result.by_attack_type) : []), [result]);

  async function handleRun() {
    setRunning(true);
    setArtifact(null);
    try {
      const res = await runEvaluation(profile);
      setResult(res);
      setAttack(Object.keys(res.by_attack_type)[0] ?? "");
      pushToast({ variant: "success", title: `Evaluation complete (${profile})`, message: res.evaluation_id });
    } catch (err) {
      reportError("Evaluation run failed", err);
    } finally {
      setRunning(false);
    }
  }

  async function handleLookup() {
    if (!lookupId.trim()) return;
    setRunning(true);
    try {
      const res = await getEvaluation(lookupId.trim());
      setResult(res);
      setAttack(Object.keys(res.by_attack_type)[0] ?? "");
      pushToast({ variant: "info", title: "Evaluation loaded", message: res.evaluation_id });
    } catch (err) {
      reportError("Failed to load evaluation", err);
    } finally {
      setRunning(false);
    }
  }

  async function handleLoadArtifact(id: string) {
    setLoadingArtifact(true);
    try {
      const res = await getEvaluationArtifact(id);
      setArtifact(res);
      pushToast({ variant: "info", title: "Artifact loaded" });
    } catch (err) {
      reportError("Failed to load artifact", err);
    } finally {
      setLoadingArtifact(false);
    }
  }

  const chartData = useMemo(() => {
    if (!result) return [];
    return attacks.map((a) => ({
      attack: a,
      value: result.by_attack_type[a][metric] ?? 0,
    }));
  }, [result, attacks, metric]);

  const selected: MetricsOut | null = result && attack ? result.by_attack_type[attack] ?? null : null;

  return (
    <>
      <WorkStage
        index="06"
        name="Evaluation Center"
        subtitle="Measure empirical detector behaviour under benchmark"
        lede="Run a benchmark to observe detection, false-alarm and rejection behaviour across modelled attacks — empirical and configuration-dependent, never a score."
      />

      <Card title="Run benchmark" subtitle="POST /api/v1/evaluation/run" icon={<Play size={17} />}>
        <div className="stack">
          <div className="grid cols-2">
            <Field label="Profile" hint="'smoke' runs in seconds; 'reference' takes minutes">
              <Select
                value={profile}
                onChange={(v) => setProfile(v as EvaluationProfile)}
                options={[
                  { value: "smoke", label: "smoke (fast)" },
                  { value: "reference", label: "reference (full, slow)" },
                ]}
              />
            </Field>
            <Field label="Retrieve by ID" hint="GET /api/v1/evaluation/{id}">
              <div className="row">
                <TextInput value={lookupId} placeholder="eval-…" onChange={(e) => setLookupId(e.target.value)} />
                <Button variant="ghost" onClick={handleLookup} disabled={!lookupId.trim()} loading={running}>
                  Load
                </Button>
              </div>
            </Field>
          </div>

          {profile === "reference" && (
            <Callout variant="warn" title="Reference profile is expensive">
              The backend runs the full recorded benchmark <strong>synchronously</strong>{" "}
              and it can take minutes. The request will block until it completes — allow
              a long timeout before running it.
            </Callout>
          )}

          <div className="row">
            <Button variant="primary" onClick={handleRun} loading={running}>
              <Play size={15} /> Run {profile} evaluation
            </Button>
          </div>
        </div>
      </Card>

      {running && <Spinner label="Working…" />}

      {!result && !running && (
        <Card>
          <EmptyState
            icon={<BarChart3 size={28} />}
            title="No evaluation run yet"
            body="Run the smoke profile for a fast benchmark, or retrieve a stored evaluation by ID."
          />
        </Card>
      )}

      {result && (
        <>
          <Callout variant="evidence" title={`Security assessment · ${result.security_assessment.status}`}>
            <div className="row" style={{ marginBottom: 8 }}>
              <Badge tone="warn">ground_truth_used: {String(result.security_assessment.ground_truth_used)}</Badge>
              <Badge tone="violet">formal_proof_present: {String(result.security_assessment.formal_proof_present)}</Badge>
            </div>
            {result.security_assessment.limitations.length > 0 && (
              <ul>
                {result.security_assessment.limitations.map((l, i) => (
                  <li key={i}>{l}</li>
                ))}
              </ul>
            )}
            <p className="note" style={{ marginTop: 8 }}>{result.note}</p>
          </Callout>

          <div className="grid cols-4">
            <Stat label="Profile" value={result.profile} sub={result.dataset_role} />
            <Stat label="Attack types" value={attacks.length} sub="modelled" />
            <Stat label="Trials" value={result.configuration.evaluation_trials} sub={`seed base ${result.seed_base}`} />
            <Stat label="Runtime (s)" value={result.runtime_seconds !== null ? fmtNum(result.runtime_seconds, 2) : "—"} sub="synchronous" />
          </div>

          <Card title="Configuration" subtitle={result.configuration.description} icon={<Table2 size={17} />}>
            <div className="grid cols-2">
              <KeyValue
                entries={[
                  ["State count", result.configuration.state_count],
                  ["Calibration sessions", result.configuration.calibration_sessions],
                  ["Evaluation trials", result.configuration.evaluation_trials],
                  ["Measurement mode", result.configuration.measurement_mode],
                  ["Shot count", result.configuration.shot_count],
                ]}
              />
              <KeyValue
                entries={[
                  ["Noise type", result.configuration.noise_type],
                  ["Reference noise strength", fmtNum(result.configuration.reference_noise_strength, 2)],
                  ["Attack fraction", fmtNum(result.configuration.attack_fraction, 2)],
                  ["Attack types", result.configuration.attack_types.join(", ")],
                  ["Operating point", result.operating_point ? result.operating_point.name : "—"],
                ]}
              />
            </div>
          </Card>

          <div className="grid side-2">
            <Card title="Metrics dashboard" subtitle={`Empirical ${metric.toUpperCase()} per attack`} icon={<BarChart3 size={17} />}
              actions={
                <Select value={metric} onChange={(v) => setMetric(v as MetricKey)} options={METRIC_OPTIONS} />
              }>
              <div className="chart-box">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} margin={{ top: 10, right: 16, bottom: 40, left: 0 }}>
                    <CartesianGrid stroke={chart.grid} vertical={false} />
                    <XAxis dataKey="attack" angle={-20} textAnchor="end" interval={0} stroke={chart.axis} height={60} tick={{ fill: chart.tick, fontSize: 11 }} />
                    <YAxis domain={[0, 1]} stroke={chart.axis} tick={{ fill: chart.tick, fontSize: 11 }} />
                    <Tooltip cursor={{ fill: chart.cursor }} contentStyle={{ background: chart.tooltipBg, border: `1px solid ${chart.tooltipBorder}`, borderRadius: 10, boxShadow: "0 10px 34px rgba(0,0,0,0.18)", color: chart.textHi }} />
                    <Bar dataKey="value" name={metric} fill={chart.accent} radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>

            <Card title="Confusion matrix" subtitle="Per-attack counts" icon={<Grid3x3 size={17} />}>
              {attacks.length === 0 ? (
                <p className="note">No per-attack rows in this run.</p>
              ) : (
                <div className="stack">
                  <Select value={attack} onChange={setAttack} options={attacks.map((a) => ({ value: a, label: a }))} />
                  {selected && <ConfusionMatrix cm={selected.confusion} />}
                </div>
              )}
            </Card>
          </div>

          <Card title="Per-attack metrics" icon={<Table2 size={17} />} tight>
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>Attack</th>
                    <th>TP</th>
                    <th>TN</th>
                    <th>FP</th>
                    <th>FN</th>
                    <th>Detection</th>
                    <th>FAR</th>
                    <th>FRR</th>
                    <th>Precision</th>
                    <th>Recall</th>
                    <th>F1</th>
                  </tr>
                </thead>
                <tbody>
                  {attacks.map((a) => {
                    const m = result.by_attack_type[a];
                    return (
                      <tr key={a} className="clickable" onClick={() => setAttack(a)} style={a === attack ? { background: "var(--accent-soft)" } : undefined}>
                        <td className="mono">{a}</td>
                        <td className="mono">{m.confusion.tp}</td>
                        <td className="mono">{m.confusion.tn}</td>
                        <td className="mono">{m.confusion.fp}</td>
                        <td className="mono">{m.confusion.fn}</td>
                        <td className="mono">{fmtPct(m.detection_rate)}</td>
                        <td className="mono">{fmtPct(m.far)}</td>
                        <td className="mono">{fmtPct(m.frr)}</td>
                        <td className="mono">{fmtPct(m.precision)}</td>
                        <td className="mono">{fmtPct(m.recall)}</td>
                        <td className="mono">{fmtPct(m.f1)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>

          <div className="grid cols-2">
            <Card title="Honest FRR by noise" subtitle="False-rejection side" icon={<Waves size={17} />}>
              {Object.keys(result.honest_frr_by_noise).length === 0 ? (
                <p className="note">No honest FRR rows reported.</p>
              ) : (
                <div className="table-wrap">
                  <table className="data">
                    <thead>
                      <tr><th>Noise level</th><th>Honest FRR</th></tr>
                    </thead>
                    <tbody>
                      {Object.entries(result.honest_frr_by_noise).map(([k, v]) => (
                        <tr key={k}>
                          <td className="mono">{k}</td>
                          <td className="mono">{v !== null ? fmtPct(v) : "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>

            <Card title="Detection by noise × attack" subtitle="Share of malicious trials rejected" icon={<Waves size={17} />}>
              <NoiseAttackMatrix data={result.detection_by_noise_and_attack} />
            </Card>
          </div>

          <Card
            title="Benchmark report"
            subtitle="GET /api/v1/evaluation/{id}/artifact"
            icon={<FileText size={17} />}
            actions={
              <Button size="sm" variant="ghost" onClick={() => handleLoadArtifact(result.evaluation_id)} loading={loadingArtifact}>
                Load artifact
              </Button>
            }
            tight
          >
            <div className="tabs">
              <button className={`tab ${reportTab === "markdown" ? "active" : ""}`} onClick={() => setReportTab("markdown")}>
                Markdown report
              </button>
              <button className={`tab ${reportTab === "artifact" ? "active" : ""}`} onClick={() => setReportTab("artifact")}>
                Artifact JSON
              </button>
            </div>
            <div style={{ padding: 16 }}>
              {!artifact ? (
                <EmptyState
                  icon={<FileText size={24} />}
                  title="Artifact not loaded"
                  body="The full report is large (megabytes for the reference profile). Load it deliberately."
                />
              ) : reportTab === "markdown" ? (
                artifact.markdown ? (
                  <div className="markdown">{artifact.markdown}</div>
                ) : (
                  <Callout variant="info" title="No markdown">
                    This artifact has no rendered markdown report. {artifact.size_warning}
                  </Callout>
                )
              ) : (
                <JsonBlock data={artifact.artifact} maxHeight={520} />
              )}
            </div>
          </Card>
        </>
      )}
    </>
  );
}

function ConfusionMatrix({ cm }: { cm: ConfusionMatrixOut }) {
  return (
    <div className="stack">
      <div className="cm">
        <div className="cm-corner" />
        <div className="cm-colhead">Flagged</div>
        <div className="cm-colhead">Cleared</div>

        <div className="cm-rowhead">Malicious</div>
        <Cell cls="cm-tp" value={cm.tp} label="TP" />
        <Cell cls="cm-fn" value={cm.fn} label="FN" />

        <div className="cm-rowhead">Honest</div>
        <Cell cls="cm-fp" value={cm.fp} label="FP" />
        <Cell cls="cm-tn" value={cm.tn} label="TN" />
      </div>
      <div className="row">
        {cm.total != null && <span className="chip">total {cm.total}</span>}
        {cm.honest != null && <span className="chip">honest {cm.honest}</span>}
        {cm.malicious != null && <span className="chip">malicious {cm.malicious}</span>}
      </div>
    </div>
  );
}

function Cell({ cls, value, label }: { cls: string; value: number; label: string }) {
  return (
    <div className={`cm-cell ${cls}`}>
      <div className="cm-val">{value}</div>
      <div className="cm-lbl">{label}</div>
    </div>
  );
}

function NoiseAttackMatrix({ data }: { data: Record<string, Record<string, number>> }) {
  const noiseLevels = Object.keys(data);
  const attackSet = new Set<string>();
  for (const n of noiseLevels) for (const a of Object.keys(data[n])) attackSet.add(a);
  const attackList = Array.from(attackSet);

  if (noiseLevels.length === 0 || attackList.length === 0) {
    return <p className="note">No noise × attack breakdown reported.</p>;
  }

  return (
    <div className="table-wrap">
      <table className="data">
        <thead>
          <tr>
            <th>Noise</th>
            {attackList.map((a) => (
              <th key={a}>{a}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {noiseLevels.map((n) => (
            <tr key={n}>
              <td className="mono">{n}</td>
              {attackList.map((a) => {
                const v = data[n][a];
                return (
                  <td key={a} className="mono" style={{ color: colorFor(v) }}>
                    {v != null ? fmtPct(v, 1) : "—"}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="row" style={{ padding: "10px 14px", gap: 12 }}>
        <LegendSwatch color="var(--danger)" label="low" />
        <LegendSwatch color="var(--warn)" label="mid" />
        <LegendSwatch color="var(--ok)" label="high detection" />
      </div>
    </div>
  );
}

function colorFor(v: number | undefined): string {
  if (v == null) return "var(--text-faint)";
  if (v >= 0.85) return "var(--ok)";
  if (v >= 0.5) return "var(--warn)";
  return "var(--danger)";
}

function LegendSwatch({ color, label }: { color: string; label: string }) {
  return (
    <span className="row" style={{ gap: 6, fontSize: 11, color: "var(--text-dim)" }}>
      <span style={{ width: 10, height: 10, borderRadius: 3, background: color, display: "inline-block" }} />
      {label}
    </span>
  );
}
