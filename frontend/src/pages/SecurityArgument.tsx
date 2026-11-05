import { useCallback, useEffect, useState } from "react";
import {
  BookOpenCheck,
  CheckCircle2,
  Layers,
  Network,
  ScanSearch,
  ShieldAlert,
  ShieldX,
  XCircle,
} from "lucide-react";
import { analyzeStatements, getAssumptions, getComposition, getObservability } from "../api/client";
import {
  MEASUREMENT_MODES,
  NOISE_TYPES,
  type AnalyzeResponse,
  type AssumptionsResponse,
  type CompositionResponse,
  type MeasurementMode,
  type NoiseType,
  type ObservabilityResponse,
  type SecurityAssessment,
} from "../api/types";
import { useApp } from "../state/AppContext";
import {
  Badge,
  BoolMark,
  Button,
  Callout,
  Card,
  EmptyState,
  Field,
  Select,
  Spinner,
  TextArea,
} from "../components/ui";
import { fmtPct, titleCase } from "../lib/format";
import { WorkStage } from "../components/workspace/WorkStage";

type Tab = "assumptions" | "observability" | "composition" | "claims";

export function SecurityArgument() {
  const [tab, setTab] = useState<Tab>("assumptions");
  return (
    <>
      <WorkStage
        index="07"
        name="Security Argument"
        subtitle="What the evidence supports — and where its boundaries lie"
        lede="Assumptions, observability, composition and claim checking, with the security assessment carried by the backend. No claim goes beyond what the research supports."
      />

      <div className="tabs">
        <button className={`tab ${tab === "assumptions" ? "active" : ""}`} onClick={() => setTab("assumptions")}>
          <span className="row" style={{ gap: 6 }}><BookOpenCheck size={14} /> Assumption Register</span>
        </button>
        <button className={`tab ${tab === "observability" ? "active" : ""}`} onClick={() => setTab("observability")}>
          <span className="row" style={{ gap: 6 }}><Network size={14} /> Threat Observability</span>
        </button>
        <button className={`tab ${tab === "composition" ? "active" : ""}`} onClick={() => setTab("composition")}>
          <span className="row" style={{ gap: 6 }}><Layers size={14} /> Composition</span>
        </button>
        <button className={`tab ${tab === "claims" ? "active" : ""}`} onClick={() => setTab("claims")}>
          <span className="row" style={{ gap: 6 }}><ScanSearch size={14} /> Claim Checker</span>
        </button>
      </div>

      {tab === "assumptions" && <AssumptionsPanel />}
      {tab === "observability" && <ObservabilityPanel />}
      {tab === "composition" && <CompositionPanel />}
      {tab === "claims" && <ClaimChecker />}
    </>
  );
}



function AssessmentBar({ a }: { a: SecurityAssessment }) {
  return (
    <Callout variant="evidence" title={`Security assessment · ${a.status}`}>
      <div className="row" style={{ marginBottom: 8 }}>
        <Badge tone="violet">formal_proof_present: {String(a.formal_proof_present)}</Badge>
        <Badge tone="info">composable_security: {String(a.composable_security_established)}</Badge>
        <Badge tone="info">universal_detection: {String(a.universal_detection_guarantee)}</Badge>
        <Badge tone="info">forgery_bound: {String(a.forgery_bound_derived)}</Badge>
      </div>
      {a.limitations.length > 0 && (
        <ul>
          {a.limitations.map((l, i) => (
            <li key={i}>{l}</li>
          ))}
        </ul>
      )}
    </Callout>
  );
}



function AssumptionsPanel() {
  const { reportError } = useApp();
  const [noiseType, setNoiseType] = useState<NoiseType>("depolarizing");
  const [mode, setMode] = useState<MeasurementMode>("sampled");
  const [data, setData] = useState<AssumptionsResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(await getAssumptions(noiseType, mode));
    } catch (err) {
      reportError("Failed to load assumptions", err);
    } finally {
      setLoading(false);
    }
  }, [noiseType, mode, reportError]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <>
      <Card title="Assumption register" subtitle="GET /api/v1/security/assumptions" icon={<BookOpenCheck size={17} />}
        actions={<Button size="sm" variant="ghost" onClick={load}>Refresh</Button>}>
        <div className="form-grid">
          <Field label="Channel noise">
            <Select value={noiseType} onChange={(v) => setNoiseType(v as NoiseType)} options={NOISE_TYPES.map((n) => ({ value: n, label: n }))} />
          </Field>
          <Field label="Measurement mode">
            <Select value={mode} onChange={(v) => setMode(v as MeasurementMode)} options={MEASUREMENT_MODES.map((m) => ({ value: m, label: m }))} />
          </Field>
        </div>
      </Card>

      {loading && <Spinner label="Resolving register…" />}

      {data && (
        <>
          <AssessmentBar a={data.security_assessment} />
          <div className="row">
            {Object.entries(data.summary).map(([k, v]) => (
              <span key={k} className="chip">{titleCase(k)}: {v}</span>
            ))}
            <span className="chip">resolved for {data.noise_type} · {data.measurement_mode}</span>
          </div>
          <Callout variant="info" title="Note">{data.note}</Callout>

          <div className="stack">
            {data.assumptions.map((asm) => (
              <div className="finding" key={asm.key}>
                <div className="finding-head">
                  <Badge tone={statusBadge(asm.status)}>{asm.status}</Badge>
                  <strong className="mono" style={{ fontSize: 12.5, color: "var(--text-hi)" }}>{asm.key}</strong>
                  {asm.citation && <span className="fid">{asm.citation}</span>}
                </div>
                <div className="finding-body">
                  <p>{asm.statement}</p>
                  <div className="grid cols-2">
                    <div>
                      <div className="stat-label" style={{ marginBottom: 4 }}>Evidence</div>
                      <p className="note">{asm.evidence}</p>
                    </div>
                    <div>
                      <div className="stat-label" style={{ marginBottom: 4 }}>If violated</div>
                      <p className="note">{asm.consequence_if_violated}</p>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {data.weaker_than_exact.length > 0 && (
            <Callout variant="warn" title="Weaker than exact">
              {data.weaker_than_exact.join(", ")}
            </Callout>
          )}
        </>
      )}
    </>
  );
}

function statusBadge(status: string): "ok" | "warn" | "danger" | "neutral" {
  const s = status.toLowerCase();
  if (s.includes("held") || s.includes("satisfied") || s.includes("ok") || s.includes("met")) return "ok";
  if (s.includes("partial") || s.includes("assum") || s.includes("conditional")) return "warn";
  if (s.includes("violat") || s.includes("fail") || s.includes("unmet")) return "danger";
  return "neutral";
}



function ObservabilityPanel() {
  const { reportError } = useApp();
  const [data, setData] = useState<ObservabilityResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(await getObservability());
    } catch (err) {
      reportError("Failed to load observability matrix", err);
    } finally {
      setLoading(false);
    }
  }, [reportError]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <>
      <Card title="Threat-observability matrix" subtitle="GET /api/v1/security/observability" icon={<Network size={17} />}
        actions={<Button size="sm" variant="ghost" onClick={load}>Refresh</Button>}>
        {loading ? (
          <Spinner label="Loading matrix…" />
        ) : data ? (
          <div className="stack">
            <AssessmentBar a={data.security_assessment} />
            <div className="row">
              <Badge tone="ok">quantum-visible: {data.quantum_visible.length}</Badge>
              <Badge tone="warn">classical-only: {data.classical_only.length}</Badge>
              <Badge tone="info">empirically evaluated: {data.empirically_evaluated_count}</Badge>
              <Badge tone="violet">covered: {data.covered_count}</Badge>
            </div>
            <p className="note">Source: {data.source}</p>

            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>Threat</th>
                    <th className="center">Quantum disturbance</th>
                    <th className="center">Protocol anomaly</th>
                    <th className="center">Auth evidence</th>
                    <th className="center">Replay evidence</th>
                    <th className="center">Detector-visible (quantum)</th>
                    <th className="center">Requires classical control</th>
                    <th className="center">M5 detection</th>
                    <th className="center">M5 FAR</th>
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map((r) => (
                    <tr key={r.threat}>
                      <td className="mono">{r.threat}</td>
                      <td className="center"><BoolMark value={r.quantum_disturbance} /></td>
                      <td className="center"><BoolMark value={r.protocol_anomaly} /></td>
                      <td className="center"><BoolMark value={r.authentication_evidence} /></td>
                      <td className="center"><BoolMark value={r.replay_evidence} /></td>
                      <td className="center"><BoolMark value={r.detector_visible_quantum} /></td>
                      <td className="center"><BoolMark value={r.requires_classical_control} /></td>
                      <td className="mono center">{r.m5_detection_rate != null ? fmtPct(r.m5_detection_rate, 1) : "—"}</td>
                      <td className="mono center">{r.m5_far != null ? fmtPct(r.m5_far, 1) : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="grid cols-2">
              <Callout variant="info" title="Quantum-visible threats">
                {data.quantum_visible.length ? data.quantum_visible.join(", ") : "none"}
              </Callout>
              <Callout variant="warn" title="Classical-only threats">
                {data.classical_only.length
                  ? `${data.classical_only.join(", ")} — a threat to the protocol layer, not undetectable by the system as a whole.`
                  : "none"}
              </Callout>
            </div>
          </div>
        ) : (
          <EmptyState title="No data" />
        )}
      </Card>
    </>
  );
}



function CompositionPanel() {
  const { reportError } = useApp();
  const [data, setData] = useState<CompositionResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(await getComposition());
    } catch (err) {
      reportError("Failed to load composition", err);
    } finally {
      setLoading(false);
    }
  }, [reportError]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <Card title="Composition assessment" subtitle="GET /api/v1/security/composition" icon={<Layers size={17} />}
      actions={<Button size="sm" variant="ghost" onClick={load}>Refresh</Button>}>
      {loading ? (
        <Spinner label="Loading composition…" />
      ) : data ? (
        <div className="stack">
          <AssessmentBar a={data.security_assessment} />
          <div className="row">
            <Badge tone="info">components: {data.component_count}</Badge>
            <Badge tone="warn">unresolved: {data.unresolved_count}</Badge>
            <Badge tone={data.formal_composition_theorem_present ? "ok" : "danger"}>
              formal_composition_theorem_present: {String(data.formal_composition_theorem_present)}
            </Badge>
          </div>
          <Callout variant="info" title="Note">{data.note}</Callout>

          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Component</th>
                  <th>Property evaluated</th>
                  <th>Evidence source</th>
                  <th>Assumption boundary</th>
                  <th>Composition dependency</th>
                  <th>Unresolved dependency</th>
                  <th>Security conclusion</th>
                </tr>
              </thead>
              <tbody>
                {data.components.map((c) => (
                  <tr key={c.component}>
                    <td className="mono">{c.component}</td>
                    <td className="wrap">{c.property_evaluated}</td>
                    <td className="wrap">{c.evidence_source}</td>
                    <td className="wrap">{c.assumption_boundary}</td>
                    <td className="wrap">{c.composition_dependency}</td>
                    <td className="wrap">{c.unresolved_dependency}</td>
                    <td className="wrap">{c.security_conclusion}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <EmptyState title="No data" />
      )}
    </Card>
  );
}



function ClaimChecker() {
  const { reportError } = useApp();
  const [text, setText] = useState(
    "The system is 100% secure against all attacks.\nAt the reference operating point, the measured false-acceptance rate on modelled forgery was 0.0%.\nAll quantum threats are detectable by the prototype.",
  );
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [running, setRunning] = useState(false);

  async function handleCheck() {
    const statements = text
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);
    if (statements.length === 0) {
      setResult(null);
      return;
    }
    setRunning(true);
    try {
      const res = await analyzeStatements({ statements });
      setResult(res);
    } catch (err) {
      reportError("Claim check failed", err);
    } finally {
      setRunning(false);
    }
  }

  return (
    <>
      <Card title="Interactive claim checker" subtitle="POST /api/v1/security/analyze — one statement per line" icon={<ScanSearch size={17} />}>
        <div className="stack">
          <Field label="Security claims" hint="checked against the forbidden-claim register; a blunt guard-rail, not a completeness guarantee">
            <TextArea rows={7} value={text} onChange={(e) => setText(e.target.value)} />
          </Field>
          <div className="row">
            <Button variant="primary" onClick={handleCheck} loading={running}>
              <ShieldAlert size={15} /> Check claims
            </Button>
          </div>
        </div>
      </Card>

      {running && <Spinner label="Checking…" />}

      {result && (
        <>
          <AssessmentBar a={result.security_assessment} />

          <Card title={`Verdicts (${result.checks.length})`} icon={<ShieldAlert size={17} />}>
            {result.checks.length === 0 ? (
              <EmptyState title="No statements checked" />
            ) : (
              <div className="stack">
                {result.checks.map((c, i) => {
                  const allowed = c.verdict.toUpperCase() === "ALLOWED";
                  return (
                    <div className="finding" key={i}>
                      <div className="finding-head">
                        <Badge tone={allowed ? "ok" : "danger"} icon={allowed ? <CheckCircle2 size={12} /> : <ShieldX size={12} />}>
                          {c.verdict}
                        </Badge>
                        <span style={{ fontSize: 13, color: "var(--text-hi)" }}>{c.statement}</span>
                      </div>
                      <div className="finding-body">
                        {c.violations.length > 0 && (
                          <div>
                            <div className="stat-label" style={{ marginBottom: 4 }}>Violations</div>
                            <ul className="clean-list">
                              {c.violations.map((v, j) => (
                                <li key={j} className="row" style={{ gap: 8 }}>
                                  <XCircle size={13} style={{ color: "var(--danger)" }} /> {v}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {c.reasons.length > 0 && (
                          <div>
                            <div className="stat-label" style={{ marginBottom: 4 }}>Reasons</div>
                            <ul className="clean-list">
                              {c.reasons.map((r, j) => (
                                <li key={j} className="note">• {r}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>

          {result.allowed_statement_example && (
            <Callout variant="info" title="Shape of an allowed measurement statement">
              {result.allowed_statement_example}
            </Callout>
          )}

          <div className="grid cols-2">
            <Card title={`Forbidden claims (${result.forbidden_claims.length})`} icon={<ShieldX size={17} />}>
              <ClaimList items={result.forbidden_claims} claimKey="claim" />
            </Card>
            <Card title={`Banned terminology (${result.banned_terminology.length})`} icon={<XCircle size={17} />}>
              <ClaimList items={result.banned_terminology} claimKey="term" />
            </Card>
          </div>
        </>
      )}
    </>
  );
}

function ClaimList({ items, claimKey }: { items: Record<string, string>[]; claimKey: string }) {
  if (items.length === 0) return <p className="note">None registered.</p>;
  return (
    <ul className="clean-list">
      {items.map((it, i) => (
        <li key={i} className="finding" style={{ padding: "10px 12px" }}>
          <strong style={{ fontSize: 12.5, color: "var(--danger)" }}>{it[claimKey] ?? ""}</strong>
          {it.reason && <div className="note" style={{ marginTop: 4 }}>{it.reason}</div>}
        </li>
      ))}
    </ul>
  );
}
