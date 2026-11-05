import { useCallback, useEffect, useState } from "react";
import { BookmarkCheck, FlaskConical, Ruler, SlidersHorizontal } from "lucide-react";
import { getCalibration, getReferenceCalibration, runCalibration } from "../api/client";
import {
  MEASUREMENT_MODES,
  NOISE_TYPES,
  PROTOCOL_VERSION,
  type CalibrationResponse,
  type ConfidenceIntervalOut,
  type MeasurementMode,
  type NoiseType,
  type ReferenceCalibrationResponse,
} from "../api/types";
import { useApp } from "../state/AppContext";
import {
  Badge,
  Button,
  Callout,
  Card,
  Field,
  JsonBlock,
  KeyValue,
  NumberInput,
  RangeField,
  Select,
  Stat,
  TextInput,
} from "../components/ui";
import { fmtNum, fmtPct } from "../lib/format";
import { WorkStage } from "../components/workspace/WorkStage";

export function CalibrationLab() {
  const { pushToast, reportError } = useApp();

  const [configId, setConfigId] = useState("api-calibration");
  const [noiseType, setNoiseType] = useState<NoiseType>("depolarizing");
  const [noiseStrength, setNoiseStrength] = useState(0.0);
  const [stateCount, setStateCount] = useState(100);
  const [measurementMode, setMeasurementMode] = useState<MeasurementMode>("sampled");
  const [shotCount, setShotCount] = useState(1);
  const [confidence, setConfidence] = useState(0.95);
  const [seedStart, setSeedStart] = useState(0);
  const [sessionCount, setSessionCount] = useState(8);

  const [result, setResult] = useState<CalibrationResponse | null>(null);
  const [reference, setReference] = useState<ReferenceCalibrationResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [lookupId, setLookupId] = useState("");

  const loadReference = useCallback(async () => {
    try {
      setReference(await getReferenceCalibration());
    } catch (err) {
      reportError("Failed to load reference calibration", err);
    }
  }, [reportError]);

  useEffect(() => {
    void loadReference();
  }, [loadReference]);

  async function handleRun() {
    setRunning(true);
    try {
      const res = await runCalibration({
        config_id: configId.trim(),
        protocol_version: PROTOCOL_VERSION,
        noise_type: noiseType,



        noise_strength: noiseType === "none" ? 0 : noiseStrength,
        state_count: stateCount,
        measurement_mode: measurementMode,
        shot_count: shotCount,
        confidence,
        seed_start: seedStart,
        session_count: sessionCount,
      });
      setResult(res);
      pushToast({
        variant: "success",
        title: "Calibration complete",
        message: `critical count ${res.threshold.critical_count} · p_upper ${fmtNum(res.threshold.p_upper)}`,
      });
    } catch (err) {
      reportError("Calibration run failed", err);
    } finally {
      setRunning(false);
    }
  }

  async function handleLookup() {
    if (!lookupId.trim()) return;
    setRunning(true);
    try {
      const res = await getCalibration(lookupId.trim());
      setResult(res);
      pushToast({ variant: "info", title: "Calibration loaded", message: res.calibration_id });
    } catch (err) {
      reportError("Failed to load calibration", err);
    } finally {
      setRunning(false);
    }
  }

  const rop = reference?.recorded_operating_point ?? null;

  return (
    <>
      <WorkStage
        index="05"
        name="Calibration Lab"
        subtitle="Derive an honest-only expectation and decision threshold"
        lede="Run calibration over honest-only data to establish the reference operating point that observable evidence is compared against."
      />

      <div className="grid side-2">
        <Card title="Run calibration" subtitle="POST /api/v1/calibration/run — honest-only data" icon={<FlaskConical size={17} />}>
          <div className="stack">
            <div className="form-grid">
              <Field label="Config ID">
                <TextInput value={configId} onChange={(e) => setConfigId(e.target.value)} />
              </Field>
              <Field label="Noise type">
                <Select value={noiseType} onChange={(v) => setNoiseType(v as NoiseType)} options={NOISE_TYPES.map((n) => ({ value: n, label: n }))} />
              </Field>
              <Field label="Measurement mode">
                <Select value={measurementMode} onChange={(v) => setMeasurementMode(v as MeasurementMode)} options={MEASUREMENT_MODES.map((m) => ({ value: m, label: m }))} />
              </Field>
            </div>
            <Field
              label="Noise strength"
              hint={
                noiseType === "none"
                  ? "channel 'none' is noiseless — 0.0 is sent (the backend refuses any other value)"
                  : "0.0 – 1.0 channel parameter"
              }
            >
              <RangeField value={noiseType === "none" ? 0 : noiseStrength} min={0} max={1} step={0.01} onChange={setNoiseStrength} disabled={noiseType === "none"} format={(v) => v.toFixed(2)} />
            </Field>
            <div className="form-grid">
              <Field label="State count" hint="1–4096">
                <NumberInput min={1} max={4096} value={stateCount} onChange={(e) => setStateCount(Number(e.target.value))} />
              </Field>
              <Field label="Shot count" hint="1–1024">
                <NumberInput min={1} max={1024} value={shotCount} onChange={(e) => setShotCount(Number(e.target.value))} />
              </Field>
              <Field label="Session count" hint="1–64 (configured bound)">
                <NumberInput min={1} max={64} value={sessionCount} onChange={(e) => setSessionCount(Number(e.target.value))} />
              </Field>
              <Field label="Seed start" hint="≥ 0">
                <NumberInput min={0} value={seedStart} onChange={(e) => setSeedStart(Number(e.target.value))} />
              </Field>
            </div>
            <Field label="Confidence" hint="0.0 < x < 1.0 (default 0.95)">
              <RangeField value={confidence} min={0.5} max={0.999} step={0.001} onChange={setConfidence} format={(v) => v.toFixed(3)} />
            </Field>
            <div className="row">
              <Button variant="primary" onClick={handleRun} loading={running}>
                <FlaskConical size={15} /> Run calibration
              </Button>
            </div>
          </div>
        </Card>

        <Card title="Retrieve stored calibration" subtitle="GET /api/v1/calibration/{id}" icon={<BookmarkCheck size={17} />}>
          <div className="stack">
            <Field label="Calibration ID" hint="in-memory only; lost on restart">
              <TextInput value={lookupId} placeholder="cal-…" onChange={(e) => setLookupId(e.target.value)} />
            </Field>
            <Button variant="ghost" onClick={handleLookup} loading={running} disabled={!lookupId.trim()}>
              Load
            </Button>
          </div>
        </Card>
      </div>

      {result && (
        <>
          <div className="grid cols-4">
            <Stat label="Critical count" value={result.threshold.critical_count} sub="reject when mismatches exceed this" />
            <Stat label="p_upper" value={fmtNum(result.threshold.p_upper)} sub="one-sided honest upper bound" />
            <Stat label="Threshold rate" value={fmtPct(result.threshold.threshold_rate)} sub={result.threshold.method} />
            <Stat label="Pooled rate" value={result.pooled_rate !== null ? fmtPct(result.pooled_rate) : "—"} sub={`${result.total_mismatch}/${result.total_valid} mismatches`} />
          </div>

          <Callout variant="evidence" title={`Calibration assessment · ${result.security_assessment.status}`}>
            <div className="row" style={{ marginBottom: 8 }}>
              <Badge tone="violet">formal_proof_present: {String(result.security_assessment.formal_proof_present)}</Badge>
            </div>
            {result.security_assessment.limitations.length > 0 && (
              <ul>
                {result.security_assessment.limitations.map((l, i) => (
                  <li key={i}>{l}</li>
                ))}
              </ul>
            )}
            <p className="note" style={{ marginTop: 8 }}>
              The threshold is valid only at the sample size, measurement mode, shot
              count and channel it was derived for.
            </p>
          </Callout>

          <div className="grid cols-2">
            <Card title="Decision threshold" icon={<Ruler size={17} />}>
              <KeyValue
                entries={[
                  ["Method", result.threshold.method],
                  ["State count", result.threshold.state_count],
                  ["Critical count", result.threshold.critical_count],
                  ["p_upper", fmtNum(result.threshold.p_upper)],
                  ["Threshold rate", fmtPct(result.threshold.threshold_rate)],
                  ["alpha", fmtNum(result.threshold.alpha)],
                  ["calibration_alpha", fmtNum(result.threshold.calibration_alpha)],
                  ["evaluation_alpha", fmtNum(result.threshold.evaluation_alpha)],
                  ["Calibration role", result.threshold.calibration_role],
                  ["Sessions", result.threshold.calibration_session_count],
                  ["Total valid / mismatch", `${result.threshold.calibration_total_valid} / ${result.threshold.calibration_total_mismatch}`],
                  ["Fingerprint", <span className="mono" style={{ fontSize: 11 }}>{result.threshold.calibration_fingerprint}</span>],
                ]}
              />
            </Card>

            <Card title="Confidence intervals" subtitle="Exact binomial" icon={<SlidersHorizontal size={17} />}>
              <div className="stack">
                <IntervalView label="Two-sided interval" ci={result.interval} />
                <IntervalView label="One-sided upper bound" ci={result.upper_bound} />
              </div>
            </Card>
          </div>

          <Card title="Homogeneity diagnostic" subtitle="Per-state probability vector is omitted by design" icon={<SlidersHorizontal size={17} />}>
            <div className="grid cols-2">
              <KeyValue
                entries={[
                  ["Homogeneous", String(result.homogeneity.homogeneous)],
                  ["Spread", fmtNum(result.homogeneity.spread)],
                  ["Tolerance", fmtNum(result.homogeneity.tolerance)],
                  ["Minimum", fmtNum(result.homogeneity.minimum)],
                  ["Maximum", fmtNum(result.homogeneity.maximum)],
                  ["Mean", fmtNum(result.homogeneity.mean)],
                  ["State count", result.homogeneity.state_count],
                ]}
              />
              <Callout variant="info" title="Omitted detail">
                {result.homogeneity.omitted}
              </Callout>
            </div>
          </Card>

          <Card title="Operating point" icon={<Ruler size={17} />}>
            <KeyValue
              entries={[
                ["Name", result.operating_point.name],
                ["Noise", `${result.operating_point.noise_type} @ ${fmtNum(result.operating_point.noise_strength, 2)}`],
                ["State count", result.operating_point.state_count],
                ["Measurement mode", result.operating_point.measurement_mode],
                ["Shot count", result.operating_point.shot_count],
                ["Seed range", `${result.operating_point.calibration_seed_start} – ${result.operating_point.calibration_seed_end}`],
                ["Observed calibration FRR", result.operating_point.observed_calibration_frr !== null ? fmtPct(result.operating_point.observed_calibration_frr) : "—"],
              ]}
            />
          </Card>
        </>
      )}

      <Card title="Reference comparator" subtitle="GET /api/v1/calibration/reference" icon={<BookmarkCheck size={17} />}
        actions={<Button size="sm" variant="ghost" onClick={loadReference}>Refresh</Button>}>
        {reference ? (
          <div className="stack">
            <div className="grid cols-2">
              <KeyValue
                entries={[
                  ["Methodology", reference.methodology],
                  ["Statistic", reference.statistic],
                  ["Operating point", reference.operating_point_name],
                  ["alpha", fmtNum(reference.alpha)],
                  ["calibration_alpha", fmtNum(reference.calibration_alpha)],
                  ["evaluation_alpha", fmtNum(reference.evaluation_alpha)],
                ]}
              />
              <div>
                <div className="stat-label" style={{ marginBottom: 6 }}>Recorded operating point</div>
                {rop ? (
                  <KeyValue
                    entries={[
                      ["Name", rop.name],
                      ["p_upper", fmtNum(rop.p_upper)],
                      ["Critical count", rop.critical_count],
                      ["Threshold rate", fmtPct(rop.threshold_rate)],
                      ["State count", rop.state_count],
                      ["Noise", `${rop.noise_type} @ ${fmtNum(rop.noise_strength, 2)}`],
                      ["Calibration sessions", rop.calibration_sessions],
                    ]}
                  />
                ) : (
                  <p className="note">No committed benchmark artifact present; the recorded operating point is omitted rather than invented.</p>
                )}
              </div>
            </div>

            {result && rop && (
              <CompareTable
                rows={[
                  ["p_upper", fmtNum(result.threshold.p_upper), fmtNum(rop.p_upper)],
                  ["critical_count", String(result.threshold.critical_count), String(rop.critical_count)],
                  ["threshold_rate", fmtPct(result.threshold.threshold_rate), fmtPct(rop.threshold_rate)],
                  ["state_count", String(result.threshold.state_count), String(rop.state_count)],
                ]}
              />
            )}

            {reference.limitations.length > 0 && (
              <Callout variant="evidence" title="Reference limitations">
                <ul>
                  {reference.limitations.map((l, i) => (
                    <li key={i}>{l}</li>
                  ))}
                </ul>
              </Callout>
            )}

            <div>
              <div className="stat-label" style={{ marginBottom: 6 }}>Provenance</div>
              <JsonBlock data={reference.provenance} maxHeight={180} />
            </div>
          </div>
        ) : (
          <p className="note">Loading reference methodology…</p>
        )}
      </Card>
    </>
  );
}

function IntervalView({ label, ci }: { label: string; ci: ConfidenceIntervalOut | null }) {
  if (!ci) return <p className="note">{label}: not available.</p>;
  const lowerPct = Math.max(0, Math.min(100, ci.lower * 100));
  const widthPct = Math.max(0, Math.min(100 - lowerPct, (ci.upper - ci.lower) * 100));
  return (
    <div>
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 4 }}>
        <strong style={{ fontSize: 12.5, color: "var(--text-hi)" }}>{label}</strong>
        <Badge tone="info">{fmtPct(ci.confidence, 1)} · {ci.method}{ci.one_sided ? " · one-sided" : ""}</Badge>
      </div>
      <div style={{ position: "relative", height: 12, borderRadius: 999, background: "var(--surface-3)", border: "1px solid var(--border-soft)", overflow: "hidden" }}>
        <div style={{ position: "absolute", left: `${lowerPct}%`, width: `${widthPct}%`, top: 0, bottom: 0, background: "var(--accent)" }} />
      </div>
      <div className="row" style={{ justifyContent: "space-between", marginTop: 4 }}>
        <span className="mono faint" style={{ fontSize: 11 }}>lower {fmtNum(ci.lower)}</span>
        <span className="mono faint" style={{ fontSize: 11 }}>{ci.successes}/{ci.trials} · width {fmtNum(ci.width)}</span>
        <span className="mono faint" style={{ fontSize: 11 }}>upper {fmtNum(ci.upper)}</span>
      </div>
    </div>
  );
}

function CompareTable({ rows }: { rows: [string, string, string][] }) {
  return (
    <div className="table-wrap">
      <table className="data">
        <thead>
          <tr>
            <th>Metric</th>
            <th>Derived (this run)</th>
            <th>Recorded reference</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([m, a, b]) => (
            <tr key={m}>
              <td className="mono">{m}</td>
              <td className="mono">{a}</td>
              <td className="mono">{b}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
