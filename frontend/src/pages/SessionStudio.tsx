import { useCallback, useEffect, useState } from "react";
import {
  Clock,
  FileSignature,
  ListChecks,
  PenLine,
  RefreshCw,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import {
  createSession,
  expireSession,
  getSession,
  listSessions,
  signSession,
  verifyTranscript,
} from "../api/client";
import {
  DEFAULT_STATE_COUNT,
  MAX_STATE_COUNT,
  PROTOCOL_VERSION,
  type SessionSignResponse,
  type SessionSummary,
  type SessionView,
  type VerificationResponse,
} from "../api/types";
import { useApp } from "../state/AppContext";
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
  Spinner,
  TextArea,
  TextInput,
} from "../components/ui";
import { lifecycleTone, prettyJson, shortId, timeLabel } from "../lib/format";
import { WorkStage, SteppedFlow, DetailsDisclosure } from "../components/workspace/WorkStage";

export function SessionStudio() {
  const { pushToast, reportError } = useApp();

  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loadingList, setLoadingList] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<SessionView | null>(null);
  const [signResult, setSignResult] = useState<SessionSignResponse | null>(null);
  const [busy, setBusy] = useState<string | null>(null);


  const [message, setMessage] = useState("Reference message for signing");
  const [signerId, setSignerId] = useState("alice");
  const [verifierId, setVerifierId] = useState("bob");
  const [stateCount, setStateCount] = useState<number>(DEFAULT_STATE_COUNT);


  const [verifyMessage, setVerifyMessage] = useState("Reference message for signing");
  const [verifyVerifier, setVerifyVerifier] = useState("bob");
  const [verifyExpected, setVerifyExpected] = useState(PROTOCOL_VERSION);
  const [verifySessionId, setVerifySessionId] = useState("");
  const [transcriptText, setTranscriptText] = useState("");
  const [verifyResult, setVerifyResult] = useState<VerificationResponse | null>(null);

  const refreshList = useCallback(async () => {
    setLoadingList(true);
    try {
      const res = await listSessions();
      setSessions(res.sessions);
    } catch (err) {
      reportError("Failed to list sessions", err);
    } finally {
      setLoadingList(false);
    }
  }, [reportError]);

  useEffect(() => {
    void refreshList();
  }, [refreshList]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      setSignResult(null);
      return;
    }
    let cancelled = false;
    (async () => {
      setBusy("load");
      try {
        const view = await getSession(selectedId);
        if (!cancelled) setDetail(view);
      } catch (err) {
        if (!cancelled) reportError("Failed to load session", err);
      } finally {
        if (!cancelled) setBusy(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selectedId, reportError]);

  async function handleCreate() {
    setBusy("create");
    try {
      const view = await createSession({
        message,


        signer_id: signerId.trim(),
        verifier_id: verifierId.trim(),
        state_count: stateCount,
      });
      pushToast({ variant: "success", title: "Session created", message: view.session_id });
      setSelectedId(view.session_id);
      await refreshList();
    } catch (err) {
      reportError("Failed to create session", err);
    } finally {
      setBusy(null);
    }
  }

  async function handleSign() {
    if (!selectedId) return;
    setBusy("sign");
    try {
      const res = await signSession(selectedId);
      setSignResult(res);
      setTranscriptText(prettyJson(res.transcript));
      pushToast({ variant: "success", title: "Session signed", message: `transcript ${res.transcript_hash.slice(0, 12)}…` });
      setDetail((d) => (d ? { ...d, lifecycle: res.lifecycle, history: res.history } : d));
      await refreshList();
    } catch (err) {
      reportError("Failed to sign session", err);
    } finally {
      setBusy(null);
    }
  }

  async function handleExpire() {
    if (!selectedId) return;
    setBusy("expire");
    try {
      const view = await expireSession(selectedId);
      setDetail(view);
      pushToast({ variant: "info", title: "Session expired", message: view.session_id });
      await refreshList();
    } catch (err) {
      reportError("Failed to expire session", err);
    } finally {
      setBusy(null);
    }
  }

  async function handleVerify() {
    let transcript: Record<string, unknown>;
    try {
      transcript = JSON.parse(transcriptText) as Record<string, unknown>;
    } catch {
      pushToast({
        variant: "error",
        title: "Invalid transcript JSON",
        message: "Paste the serialized transcript object produced by signing.",
      });
      return;
    }
    setBusy("verify");
    try {
      const res = await verifyTranscript({
        message: verifyMessage,
        transcript,
        verifier_context: {
          verifier_id: verifyVerifier,
          expected_protocol_version: verifyExpected || null,
        },
        session_id: verifySessionId.trim() ? verifySessionId.trim() : null,
      });
      setVerifyResult(res);
      pushToast({
        variant: res.accepted ? "success" : "warn",
        title: res.accepted ? "Verification accepted" : "Verification not accepted",
        message: `${res.errors.length} error(s), ${res.warnings.length} warning(s)`,
      });
      if (res.session_id) {
        await refreshList();
        if (res.session_id === selectedId) {
          const view = await getSession(res.session_id);
          setDetail(view);
        }
      }
    } catch (err) {
      reportError("Verification request failed", err);
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <WorkStage
        index="02"
        name="Session Studio"
        subtitle="Establish and drive a signing investigation"
        lede="Create a session to bind a message to a protocol run, sign it to produce observable evidence, then verify or expire it through its lifecycle."
      />
      <SteppedFlow
        steps={[
          { label: "Create", state: detail ? "done" : "current" },
          { label: "Sign", state: detail && ["SIGNED","VERIFIED","EXPIRED"].includes(detail.lifecycle) ? "done" : detail ? "current" : "todo" },
          { label: "Verify", state: detail && detail.lifecycle === "VERIFIED" ? "done" : detail && detail.lifecycle === "SIGNED" ? "current" : "todo" },
          { label: "Expire", state: detail && detail.lifecycle === "EXPIRED" ? "done" : "todo" },
        ]}
      />
      <div className="grid side-2">
        <Card
          title="Create session"
          subtitle="POST /api/v1/sessions"
          icon={<FileSignature size={17} />}
        >
          <div className="stack">
            <Field label="Message" hint={`1–4096 characters (configured bound)`}>
              <TextArea value={message} onChange={(e) => setMessage(e.target.value)} rows={2} />
            </Field>
            <div className="form-grid">
              <Field label="Signer ID" hint="^[a-zA-Z0-9_-]{1,128}$">
                <TextInput value={signerId} onChange={(e) => setSignerId(e.target.value)} />
              </Field>
              <Field label="Verifier ID" hint="^[a-zA-Z0-9_-]{1,128}$">
                <TextInput value={verifierId} onChange={(e) => setVerifierId(e.target.value)} />
              </Field>
              <Field label="State count" hint={`1–${MAX_STATE_COUNT}`}>
                <NumberInput
                  min={1}
                  max={MAX_STATE_COUNT}
                  value={stateCount}
                  onChange={(e) => setStateCount(Number(e.target.value))}
                />
              </Field>
            </div>
            <div className="row">
              <Button variant="primary" onClick={handleCreate} loading={busy === "create"}>
                <PenLine size={15} /> Create session
              </Button>
              <span className="chip">protocol {PROTOCOL_VERSION}</span>
            </div>
          </div>
        </Card>

        <Card
          title="Sessions"
          subtitle={`${sessions.length} in memory`}
          icon={<ListChecks size={17} />}
          actions={
            <Button variant="ghost" size="sm" onClick={refreshList} loading={loadingList}>
              <RefreshCw size={14} /> Refresh
            </Button>
          }
          tight
        >
          {loadingList && sessions.length === 0 ? (
            <Spinner label="Loading sessions…" />
          ) : sessions.length === 0 ? (
            <EmptyState
              icon={<Clock size={26} />}
              title="No sessions yet"
              body="Create a session to begin. The store is in memory, so a backend restart clears this list."
            />
          ) : (
            <div className="table-wrap" style={{ maxHeight: 420 }}>
              <table className="data">
                <thead>
                  <tr>
                    <th>Session</th>
                    <th>Lifecycle</th>
                    <th>Signer → Verifier</th>
                    <th>States</th>
                  </tr>
                </thead>
                <tbody>
                  {sessions.map((s) => (
                    <tr
                      key={s.session_id}
                      className="clickable"
                      style={s.session_id === selectedId ? { background: "var(--accent-soft)" } : undefined}
                      onClick={() => setSelectedId(s.session_id)}
                    >
                      <td className="mono">{shortId(s.session_id, 12)}</td>
                      <td>
                        <Badge tone={lifecycleTone(s.lifecycle)}>{s.lifecycle}</Badge>
                      </td>
                      <td className="mono" style={{ fontSize: 11.5 }}>
                        {s.signer_id} → {s.verifier_id}
                      </td>
                      <td className="mono">{s.state_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>

      {busy === "load" && <Spinner label="Loading session detail…" />}

      {detail && (
        <Card
          title={`Session ${shortId(detail.session_id, 16)}`}
          subtitle="GET /api/v1/sessions/{id}"
          icon={<FileSignature size={17} />}
          actions={
            <>
              <Badge tone={lifecycleTone(detail.lifecycle)}>{detail.lifecycle}</Badge>
              <Button size="sm" variant="cyan" onClick={handleSign} loading={busy === "sign"}>
                <PenLine size={14} /> Sign
              </Button>
              <Button size="sm" variant="danger" onClick={handleExpire} loading={busy === "expire"}>
                <XCircle size={14} /> Expire
              </Button>
            </>
          }
        >
          <div className="grid cols-2">
            <KeyValue
              entries={[
                ["Session ID", detail.session_id],
                ["Nonce", detail.nonce],
                ["Protocol version", detail.protocol_version],
                ["Protocol status", detail.protocol_status],
                ["State count", detail.state_count],
                ["Signer", detail.signer_id],
                ["Verifier", detail.verifier_id],
                ["Created", timeLabel(detail.created_at)],
                ["Message hash", detail.message_hash],
                ["Message binding", detail.message_binding],
              ]}
            />
            <div className="stack">
              <div>
                <div className="stat-label" style={{ marginBottom: 6 }}>
                  Lifecycle history
                </div>
                <div className="row">
                  {detail.history.map((h, i) => (
                    <Badge key={i} tone={lifecycleTone(h)}>
                      {h}
                    </Badge>
                  ))}
                </div>
              </div>
              {signResult && (
                <Callout variant="info" title="Signed transcript">
                  Deterministic reference transcript. Inspect the JSON and its hash
                  below, then paste it into the verify workspace.
                </Callout>
              )}
            </div>
          </div>

          {signResult && (
            <div className="stack" style={{ marginTop: 16 }}>
              <div className="row">
                <Badge tone="violet">transcript_hash</Badge>
                <code className="mono" style={{ fontSize: 12, color: "var(--q-cyan)" }}>
                  {signResult.transcript_hash}
                </code>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    setTranscriptText(prettyJson(signResult.transcript));
                    setVerifySessionId(signResult.session_id);
                    pushToast({ variant: "info", title: "Transcript loaded into verifier" });
                  }}
                >
                  Load into verifier ↓
                </Button>
              </div>
              <JsonBlock data={signResult.transcript} maxHeight={280} />
            </div>
          )}
        </Card>
      )}

      <Card
        title="Verify transcript"
        subtitle="POST /api/v1/verify — a consistency result, not a security verdict"
        icon={<ShieldCheck size={17} />}
      >
        <div className="stack">
          <DetailsDisclosure summary="Verification inputs (technical)">
          <div className="form-grid">
            <Field label="Verifier ID">
              <TextInput value={verifyVerifier} onChange={(e) => setVerifyVerifier(e.target.value)} />
            </Field>
            <Field label="Expected protocol version" hint="optional">
              <TextInput value={verifyExpected} onChange={(e) => setVerifyExpected(e.target.value)} />
            </Field>
            <Field label="Session ID" hint="optional — records the outcome">
              <TextInput
                value={verifySessionId}
                placeholder="(none)"
                onChange={(e) => setVerifySessionId(e.target.value)}
              />
            </Field>
          </div>
          <Field label="Message" hint="must match the message the transcript binds">
            <TextArea value={verifyMessage} onChange={(e) => setVerifyMessage(e.target.value)} rows={2} />
          </Field>
          <Field label="Transcript JSON" hint="paste the serialized transcript object">
            <TextArea
              value={transcriptText}
              onChange={(e) => setTranscriptText(e.target.value)}
              rows={6}
              placeholder='{ "protocol_version": "...", "states": [ ... ] }'
            />
          </Field>
          <div className="row">
            <Button variant="primary" onClick={handleVerify} loading={busy === "verify"} disabled={!transcriptText.trim()}>
              <ShieldCheck size={15} /> Verify transcript
            </Button>
          </div>
          </DetailsDisclosure>

          {verifyResult && <VerificationPanel result={verifyResult} />}
        </div>
      </Card>
    </>
  );
}

function VerificationPanel({ result }: { result: VerificationResponse }) {
  return (
    <div className="stack">
      <div className="row">
        <Badge tone={result.accepted ? "ok" : "danger"}>
          {result.accepted ? "ACCEPTED" : "NOT ACCEPTED"}
        </Badge>
        {result.lifecycle && <Badge tone={lifecycleTone(result.lifecycle)}>{result.lifecycle}</Badge>}
        <span className="chip">mismatches {result.mismatch_count}</span>
        <span className="chip">states {result.state_count}</span>
      </div>

      <div className="grid cols-3">
        <FlagCell label="Session valid" ok={result.session_valid} />
        <FlagCell label="Message valid" ok={result.message_valid} />
        <FlagCell label="Transcript valid" ok={result.transcript_valid} />
        <FlagCell label="State sequence valid" ok={result.state_sequence_valid} />
        <FlagCell label="Measurement valid" ok={result.measurement_valid} />
        <FlagCell label="Accepted" ok={result.accepted} />
      </div>

      {result.errors.length > 0 && (
        <Callout variant="danger" title={`Errors (${result.errors.length})`}>
          <ul>
            {result.errors.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </Callout>
      )}
      {result.warnings.length > 0 && (
        <Callout variant="warn" title={`Warnings (${result.warnings.length})`}>
          <ul>
            {result.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </Callout>
      )}

      <div className="grid cols-2">
        <div>
          <div className="stat-label" style={{ marginBottom: 6 }}>Basis counts</div>
          <JsonBlock data={result.basis_counts} maxHeight={180} />
        </div>
        <div>
          <div className="stat-label" style={{ marginBottom: 6 }}>Measurement summary</div>
          <JsonBlock data={result.measurement_summary} maxHeight={180} />
        </div>
      </div>

      <Callout variant="evidence" title="Qualifier carried by every verification response">
        {result.note}
      </Callout>
    </div>
  );
}

function FlagCell({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className="stat" style={{ padding: 12 }}>
      <div className="stat-label">{label}</div>
      <div className="row" style={{ marginTop: 6, gap: 8 }}>
        <Badge tone={ok ? "ok" : "danger"}>{ok ? "TRUE" : "FALSE"}</Badge>
      </div>
    </div>
  );
}
