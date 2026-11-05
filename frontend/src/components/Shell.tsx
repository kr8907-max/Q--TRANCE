import {
  Atom,
  BarChart3,
  FileSignature,
  Gauge,
  Menu,
  Radar,
  RefreshCw,
  ShieldCheck,
  SlidersHorizontal,
} from "lucide-react";
import { VIEWS, useApp, type ViewKey } from "../state/AppContext";
import { API_BASE_URL } from "../api/client";
import { Button, Dot } from "./ui";

const ICONS: Record<ViewKey, React.ReactNode> = {
  dashboard: <Gauge size={17} />,
  sessions: <FileSignature size={17} />,
  simulation: <Atom size={17} />,
  detection: <Radar size={17} />,
  calibration: <SlidersHorizontal size={17} />,
  evaluation: <BarChart3 size={17} />,
  security: <ShieldCheck size={17} />,
};

const SUBTITLES: Record<ViewKey, string> = {
  dashboard: "System health, versions and in-memory store counters",
  sessions: "Create, sign, expire and verify reference signing sessions",
  simulation: "Build scenarios and inspect observable quantum output",
  detection: "Run the detector over observable evidence only",
  calibration: "Derive decision thresholds from honest-only data",
  evaluation: "Empirical benchmark rates per modelled attack",
  security: "Assumptions, observability, composition and claim checking",
};

export function ConnectionBadge() {
  const { connection, refreshConnection } = useApp();
  const { status, health } = connection;
  const tone = status === "online" ? "ok" : status === "degraded" ? "warn" : status === "offline" ? "danger" : "idle";
  const label =
    status === "online"
      ? "Connected"
      : status === "degraded"
        ? "Degraded"
        : status === "offline"
          ? "Offline"
          : "Checking…";
  return (
    <div className="row" style={{ gap: 8 }}>
      <span className="conn" title={API_BASE_URL}>
        <Dot tone={tone} pulse={status === "checking"} />
        {label}
        {health && <span className="faint">· API {health.api_version}</span>}
      </span>
      <Button variant="ghost" size="sm" onClick={refreshConnection} title="Re-probe /health and /ready">
        <RefreshCw size={14} />
      </Button>
    </div>
  );
}

function navDone(key: ViewKey, counts: Record<string, number>): boolean {
  const get = (...ks: string[]) => ks.reduce((n, k) => (typeof counts[k] === "number" ? counts[k] : n), 0);
  switch (key) {
    case "sessions": return get("sessions") > 0;
    case "simulation": return get("simulations", "simulation_runs", "runs") > 0;
    case "detection": return get("detections", "detection_runs", "replay_ledger") > 0;
    case "calibration": return get("calibrations") > 0;
    case "evaluation": return get("evaluations") > 0;
    default: return false;
  }
}
export function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { view, navigate, connection } = useApp();
  return (
    <aside className={`sidebar ${open ? "open" : ""}`}>

      <div className="brand">
        <div className="brand-mark">
          <img className="brand-logo" src="/qtrace-logo.png" alt="" aria-hidden="true" />
        </div>
        <div className="brand-text">
          <h1>Q-TRACE</h1>
          <p>Quantum Threat &amp; Reliability Analysis for Cryptographic Evidence</p>
        </div>
      </div>

      <nav className="nav">
        <div className="nav-label">Workspaces</div>
        {VIEWS.map((v) => (
          <button
            key={v.key}
            className={`nav-item ${view === v.key ? "active" : ""}`}
            onClick={() => {
              navigate(v.key);
              onClose();
            }}
          >
            {ICONS[v.key]}
            <span>{v.label}</span>
            <span className={`nav-state ${navDone(v.key, connection.health?.state ?? {}) ? "done" : ""}`} aria-hidden="true" />
            <span className="nav-idx">{v.index}</span>
          </button>
        ))}
      </nav>

      <div className="sidebar-foot">
        <strong style={{ color: "var(--text-dim)" }}>Evidence-only prototype.</strong>{" "}
        Detection produces evidence, not verdicts. No formal proof, no universal
        detection guarantee. Data is held in memory and lost on restart.
      </div>
    </aside>
  );
}

export function Header({ onMenu }: { onMenu: () => void }) {
  const { view } = useApp();
  const meta = VIEWS.find((v) => v.key === view)!;
  return (
    <header className="header">
      <Button variant="ghost" size="sm" onClick={onMenu} title="Menu">
        <Menu size={18} />
      </Button>
      <div className="header-title">
        <h2>
          {meta.index} · {meta.label}
        </h2>
        <p>{SUBTITLES[view]}</p>
      </div>
      <div className="header-spacer" />
      <ConnectionBadge />
    </header>
  );
}
