import { useEffect, useMemo, useRef, useState } from "react";
import {
  Atom,
  FlaskConical,
  Play,
  Radar,
  ScatterChart as ScatterIcon,
  Table2,
} from "lucide-react";
import {
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import { runSimulation, runSimulationEvaluation } from "../api/client";
import {
  ATTACK_TYPES,
  FRACTIONAL_ATTACK_TYPES,
  MAX_STATE_COUNT,
  MEASUREMENT_MODES,
  NOISE_TYPES,
  type AttackType,
  type MeasurementMode,
  type NoiseType,
  type SimulationEvaluationResponse,
  type SimulationResponse,
} from "../api/types";
import {
  buildDetectionRequest,
  buildSimulationRequest,
  identifierError,
} from "../lib/scenarioForm";
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
  NumberInput,
  RangeField,
  Select,
  Spinner,
  Stat,
  TextArea,
  TextInput,
  Toggle,
} from "../components/ui";
import { fmtNum, fmtPct, shortId } from "../lib/format";
import { WorkStage } from "../components/workspace/WorkStage";

const ROW_CAP = 400;

export function SimulationBench() {
  const { pushToast, reportError, sendToDetection } = useApp();
  const chart = useChartPalette();

  const [scenarioId, setScenarioId] = useState("api-scenario");
  const [message, setMessage] = useState("reference message");
  const [signerId, setSignerId] = useState("alice");
  const [verifierId, setVerifierId] = useState("bob");
  const [stateCount, setStateCount] = useState(64);
  const [shotCount, setShotCount] = useState(1);
  const [randomSeed, setRandomSeed] = useState(0);
  const [measurementMode, setMeasurementMode] = useState<MeasurementMode>("sampled");
  const [noiseType, setNoiseType] = useState<NoiseType>("depolarizing");
  const [noiseStrength, setNoiseStrength] = useState(0.05);
  const [attackType, setAttackType] = useState<AttackType>("none");
  const [fraction, setFraction] = useState(0.3);
  const [attackSeed, setAttackSeed] = useState(0);
  const [extraVerifiers, setExtraVerifiers] = useState("");
  const [evalMode, setEvalMode] = useState(false);

  const [result, setResult] = useState<SimulationResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [tab, setTab] = useState<"table" | "scatter" | "raw">("table");




  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const isFractional = FRACTIONAL_ATTACK_TYPES.includes(attackType);



  const scenarioError = identifierError(scenarioId.trim());

  function buildRequest() {
    return buildSimulationRequest({
      scenarioId,
      message,
      signerId,
      verifierId,
      stateCount,
      shotCount,
      randomSeed,
      measurementMode,
      noiseType,
      noiseStrength,
      attackType,
      fraction,
      attackSeed,
      extraVerifiers,
    });
  }

  async function handleRun() {

    if (running) return;
    if (scenarioError) {
      pushToast({ variant: "error", title: "Scenario ID is invalid", message: scenarioError });
      return;
    }
    setRunning(true);
    try {
      const req = buildRequest();
      const res = evalMode
        ? await runSimulationEvaluation(req)
        : await runSimulation(req);
      if (!mounted.current) return;
      setResult(res);
      pushToast({
        variant: "success",
        title: evalMode ? "Evaluation simulation complete" : "Simulation complete",
        message: `${res.mismatch_count}/${res.state_count} mismatches`,
      });
    } catch (err) {
      if (!mounted.current) return;
      reportError("Simulation failed", err);
    } finally {
      if (mounted.current) setRunning(false);
    }
  }

  function handleSendToDetection() {
    if (!result) return;
    sendToDetection({
      request: buildDetectionRequest(result, message),
      origin: `simulation:${result.scenario_id}`,
      at: Date.now(),
    });
    pushToast({ variant: "info", title: "Observable data sent to Detection Console" });
  }

  const scatter = useMemo(() => {
    if (!result) return { matched: [], mismatched: [] };
    const matched: { x: number; y: number }[] = [];
    const mismatched: { x: number; y: number }[] = [];
    for (const s of result.states) {
      (s.matched ? matched : mismatched).push({ x: s.index, y: s.probability_expected });
    }
    return { matched, mismatched };
  }, [result]);

  const evalResult = result && "ground_truth" in result ? (result as SimulationEvaluationResponse) : null;

  return (
    <>
      <WorkStage
        index="03"
        name="Simulation Bench"
        subtitle="Build a scenario, run it, inspect the observable output"
        lede="Configure the protocol, noise and attack conditions, then run the experiment. The result becomes the observation you can hand off to detection."
      />

      <Card title="Scenario builder" subtitle="POST /api/v1/simulations" icon={<FlaskConical size={17} />}>
        <div className="stack">
          <div className="form-grid">
            <Field
              label="Scenario ID"
              hint={
                scenarioError ? (
                  <span style={{ color: "var(--danger)" }}>{scenarioError}</span>
                ) : (
                  "letter/digit first, then letters, digits, . _ : @ -"
                )
              }
            >
              <TextInput value={scenarioId} onChange={(e) => setScenarioId(e.target.value)} />
            </Field>
            <Field label="Signer ID">
              <TextInput value={signerId} onChange={(e) => setSignerId(e.target.value)} />
            </Field>
            <Field label="Verifier ID">
              <TextInput value={verifierId} onChange={(e) => setVerifierId(e.target.value)} />
            </Field>
            <Field label="Extra authorized verifiers" hint="comma-separated, optional">
              <TextInput value={extraVerifiers} placeholder="carol, dave" onChange={(e) => setExtraVerifiers(e.target.value)} />
            </Field>
          </div>

          <Field label="Message">
            <TextArea rows={2} value={message} onChange={(e) => setMessage(e.target.value)} />
          </Field>

          <div className="form-grid">
            <Field label="State count" hint={`1–${MAX_STATE_COUNT}`}>
              <NumberInput min={1} max={MAX_STATE_COUNT} value={stateCount} onChange={(e) => setStateCount(Number(e.target.value))} />
            </Field>
            <Field label="Shot count" hint="1–1024 (configured bound)">
              <NumberInput min={1} max={1024} value={shotCount} onChange={(e) => setShotCount(Number(e.target.value))} />
            </Field>
            <Field label="Random seed" hint="0 – 2^63-1">
              <NumberInput min={0} value={randomSeed} onChange={(e) => setRandomSeed(Number(e.target.value))} />
            </Field>
            <Field label="Measurement mode">
              <Select
                value={measurementMode}
                onChange={(v) => setMeasurementMode(v as MeasurementMode)}
                options={MEASUREMENT_MODES.map((m) => ({ value: m, label: m }))}
              />
            </Field>
          </div>

          <div className="grid cols-2">
            <div className="stack">
              <Field label="Channel noise">
                <Select
                  value={noiseType}
                  onChange={(v) => setNoiseType(v as NoiseType)}
                  options={NOISE_TYPES.map((n) => ({ value: n, label: n }))}
                />
              </Field>
              <Field
                label="Noise strength"
                hint={
                  noiseType === "none"
                    ? "channel 'none' is noiseless — 0.0 is sent (the backend refuses any other value)"
                    : "0.0 – 1.0 channel parameter"
                }
              >
                <RangeField
                  value={noiseType === "none" ? 0 : noiseStrength}
                  min={0}
                  max={1}
                  step={0.01}
                  onChange={setNoiseStrength}
                  disabled={noiseType === "none"}
                  format={(v) => v.toFixed(2)}
                />
              </Field>
            </div>

            <div className="stack">
              <Field label="Attack">
                <Select
                  value={attackType}
                  onChange={(v) => setAttackType(v as AttackType)}
                  options={ATTACK_TYPES.map((a) => ({ value: a, label: a }))}
                />
              </Field>
              <Field
                label="Target fraction"
                hint={isFractional ? "0.0 – 1.0 (fractional attack)" : "must be 0.0 for this attack"}
              >
                <RangeField
                  value={isFractional ? fraction : 0}
                  min={0}
                  max={1}
                  step={0.01}
                  onChange={setFraction}
                  disabled={!isFractional}
                  format={(v) => v.toFixed(2)}
                />
              </Field>
              <Field label="Attack seed">
                <NumberInput min={0} value={attackSeed} onChange={(e) => setAttackSeed(Number(e.target.value))} />
              </Field>
            </div>
          </div>

          <div className="row">
            <Toggle
              checked={evalMode}
              onChange={setEvalMode}
              label={
                <span>
                  Evaluation mode{" "}
                  <span className="faint">(POST /simulations/evaluation — returns simulator ground truth)</span>
                </span>
              }
            />
          </div>

          {evalMode && (
            <Callout variant="warn" title="Evaluation material">
              The <code>ground_truth</code> block carries the hidden attack label the
              simulator used. It is <strong>not observable output</strong> and must
              never be fed to the detector — the detection request omits it by design.
            </Callout>
          )}

          <div className="row">
            <Button variant="primary" onClick={handleRun} loading={running} disabled={!!scenarioError}>
              <Play size={15} /> Run {evalMode ? "evaluation " : ""}simulation
            </Button>
          </div>

          {running && <Spinner label="Running simulation…" />}
        </div>
      </Card>

      {running && !result ? (
        <Card
          title="Running"
          subtitle="the backend is processing the scenario"
          icon={<FlaskConical size={17} />}
        >
          <Spinner label="Running simulation…" />
        </Card>
      ) : !result ? (
        <Card>
          <EmptyState
            icon={<Atom size={28} />}
            title="No simulation run yet"
            body="Configure a scenario and run it. Output is deterministic for a given seed and is observable-only unless evaluation mode is enabled."
          />
        </Card>
      ) : (
        <>
          <div className="grid cols-4">
            <Stat label="Mismatch count" value={result.mismatch_count} sub={`of ${result.state_count} states`} />
            <Stat label="Mismatch proportion" value={fmtPct(result.mismatch_proportion)} sub="observable" />
            <Stat label="Mean disturbance" value={fmtNum(result.mean_channel_disturbance)} sub="channel estimate" />
            <Stat
              label="Verification"
              value={
                <span style={{ fontSize: 18 }}>
                  <Badge tone={result.verification.accepted ? "ok" : "danger"}>
                    {result.verification.accepted ? "ACCEPTED" : "NOT ACCEPTED"}
                  </Badge>
                </span>
              }
              sub={result.verification.errors.length ? `${result.verification.errors.length} error(s)` : "no errors"}
            />
          </div>

          <Card
            title={`Run · ${shortId(result.scenario_id, 24)}`}
            subtitle={`${result.measurement_mode} · seed ${result.simulator_seed} · ${result.protocol_version}`}
            icon={<Atom size={17} />}
            actions={
              <Button size="sm" variant="cyan" onClick={handleSendToDetection}>
                <Radar size={14} /> Send observable data to detector
              </Button>
            }
          >
            <div className="grid cols-2">
              <KeyValue
                entries={[
                  ["Scenario ID", result.scenario_id],
                  ["State count", result.state_count],
                  ["Measurement mode", result.measurement_mode],
                  ["Simulator seed", result.simulator_seed],
                  ["Runtime (s)", result.runtime_seconds !== null ? fmtNum(result.runtime_seconds, 3) : "—"],
                  ["Observable only", String(result.observable_only)],
                ]}
              />
              <div className="stack">
                <div>
                  <div className="stat-label" style={{ marginBottom: 6 }}>Authorization</div>
                  <div className="row">
                    <Badge tone={result.authorization.signer_authorized ? "ok" : "danger"}>
                      signer {result.authorization.signer_authorized ? "authorized" : "UNAUTHORIZED"}
                    </Badge>
                    <Badge tone={result.authorization.verifier_authorized ? "ok" : "danger"}>
                      verifier {result.authorization.verifier_authorized ? "authorized" : "UNAUTHORIZED"}
                    </Badge>
                  </div>
                  <div className="row" style={{ marginTop: 8 }}>
                    <span className="chip">presented signer: {result.authorization.presented_signer}</span>
                    <span className="chip">presented verifier: {result.authorization.presented_verifier}</span>
                  </div>
                </div>
                <div>
                  <div className="stat-label" style={{ marginBottom: 6 }}>Basis counts</div>
                  <div className="row">
                    {Object.entries(result.basis_counts).map(([b, c]) => (
                      <span key={b} className="chip">
                        {b}: {c}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            <Callout variant="info" title="Observable-output note">
              {result.note}
            </Callout>
          </Card>

          {evalResult && (
            <Card title="Simulator ground truth" subtitle="Evaluation material — not observable output" icon={<FlaskConical size={17} />}>
              <div className="stack">
                <div className="row">
                  <Badge tone={evalResult.ground_truth.is_malicious ? "danger" : "ok"}>
                    {evalResult.ground_truth.is_malicious ? "MALICIOUS" : "HONEST"}
                  </Badge>
                  <span className="chip">{evalResult.ground_truth.label}</span>
                </div>
                <JsonBlock data={evalResult.ground_truth} maxHeight={240} />
              </div>
            </Card>
          )}

          <Card
            title="Observed states"
            subtitle={`${result.states.length} states`}
            icon={<Table2 size={17} />}
            tight
            actions={
              <div className="tabs" style={{ borderBottom: "none" }}>
                <button className={`tab ${tab === "table" ? "active" : ""}`} onClick={() => setTab("table")}>
                  <span className="row" style={{ gap: 6 }}>
                    <Table2 size={14} /> Table
                  </span>
                </button>
                <button className={`tab ${tab === "scatter" ? "active" : ""}`} onClick={() => setTab("scatter")}>
                  <span className="row" style={{ gap: 6 }}>
                    <ScatterIcon size={14} /> Scatter
                  </span>
                </button>
                <button className={`tab ${tab === "raw" ? "active" : ""}`} onClick={() => setTab("raw")}>
                  Raw JSON
                </button>
              </div>
            }
          >
            {tab === "table" && (
              <div className="table-wrap" style={{ maxHeight: 460 }}>
                <table className="data">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Basis</th>
                      <th>Expected bit</th>
                      <th>P(expected)</th>
                      <th>Matched</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.states.slice(0, ROW_CAP).map((s) => (
                      <tr key={s.index}>
                        <td className="mono">{s.index}</td>
                        <td className="mono">{s.basis}</td>
                        <td className="mono">{s.expected_bit}</td>
                        <td className="mono">{fmtNum(s.probability_expected)}</td>
                        <td>
                          <Badge tone={s.matched ? "ok" : "danger"}>{s.matched ? "match" : "mismatch"}</Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {result.states.length > ROW_CAP && (
                  <p className="note" style={{ padding: "10px 14px" }}>
                    Showing first {ROW_CAP} of {result.states.length} states. The full
                    set is sent to the detector via the handoff action.
                  </p>
                )}
              </div>
            )}

            {tab === "scatter" && (
              <div className="chart-box" style={{ padding: 16 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: 0 }}>
                    <CartesianGrid stroke={chart.grid} />
                    <XAxis type="number" dataKey="x" name="state index" stroke={chart.axis} tick={{ fill: chart.tick, fontSize: 11 }} />
                    <YAxis type="number" dataKey="y" name="P(expected)" domain={[0, 1]} stroke={chart.axis} tick={{ fill: chart.tick, fontSize: 11 }} />
                    <ZAxis range={[40, 40]} />
                    <Tooltip cursor={{ strokeDasharray: "3 3", stroke: chart.axis }} contentStyle={{ background: chart.tooltipBg, border: `1px solid ${chart.tooltipBorder}`, borderRadius: 10, boxShadow: "0 10px 34px rgba(0,0,0,0.18)", color: chart.textHi }} />
                    <ReferenceLine y={0.5} stroke={chart.ref} strokeDasharray="4 4" />
                    <Scatter name="matched" data={scatter.matched} fill={chart.accent} />
                    <Scatter name="mismatch" data={scatter.mismatched} fill={chart.danger} />
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
            )}

            {tab === "raw" && (
              <div style={{ padding: 16 }}>
                <JsonBlock data={result} maxHeight={460} />
              </div>
            )}
          </Card>
        </>
      )}
    </>
  );
}
