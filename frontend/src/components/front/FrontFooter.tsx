







import { ArrowUpRight } from "lucide-react";
import { API_BASE_URL } from "../../api/client";
import { useApp, VIEWS, type ViewKey } from "../../state/AppContext";

const PLATFORM: ViewKey[] = [
  "dashboard",
  "sessions",
  "simulation",
  "detection",
  "calibration",
  "evaluation",
];

function labelFor(key: ViewKey): string {
  return VIEWS.find((v) => v.key === key)?.label ?? key;
}

export function FrontFooter() {
  const { enterConsole, navigate } = useApp();

  const go = (v: ViewKey) => {
    enterConsole();
    navigate(v);
  };

  return (
    <footer className="fp-footer">
      <div className="fp-footer-grid">
        <div className="fp-footer-brand">
          <span className="fp-footer-logo-row">
            <img className="fp-footer-logo" src="/qtrace-logo.png" alt="" aria-hidden="true" />
            <span className="fp-footer-name">Q-TRACE</span>
          </span>
          <p className="fp-footer-full">
            Quantum Threat &amp; Reliability Analysis for Cryptographic Evidence
          </p>
          <p className="fp-footer-desc">
            An experimental quantum-simulation-backed, model-based threat detection
            framework for analyzing observable security evidence in
            teleportation-based digital-signature verification.
          </p>
          <p className="fp-footer-meta mono">RQDS-TP-1.0 · SIH26141</p>
        </div>

        <nav className="fp-footer-col" aria-label="Platform">
          <h3 className="fp-footer-h">Platform</h3>
          {PLATFORM.map((k) => (
            <button key={k} type="button" className="fp-footer-link" onClick={() => go(k)}>
              {labelFor(k)}
            </button>
          ))}
        </nav>

        <nav className="fp-footer-col" aria-label="Security and research">
          <h3 className="fp-footer-h">Security &amp; Research</h3>
          <button type="button" className="fp-footer-link" onClick={() => go("security")}>
            Security Argument
          </button>
          <a className="fp-footer-link" href="#fp-how">How It Works</a>
          <a className="fp-footer-link" href="#fp-evidence">Evidence Philosophy</a>
          <a className="fp-footer-link" href="#fp-why">Security Boundary</a>
        </nav>

        <nav className="fp-footer-col" aria-label="Project and support">
          <h3 className="fp-footer-h">Project / Support</h3>
          <button type="button" className="fp-footer-link" onClick={enterConsole}>
            Enter Security Console
          </button>
          <a className="fp-footer-link" href={`${API_BASE_URL}/docs`} target="_blank" rel="noreferrer">
            API reference (Swagger) <ArrowUpRight size={12} />
          </a>
          <a className="fp-footer-link" href={`${API_BASE_URL}/health`} target="_blank" rel="noreferrer">
            Service health <ArrowUpRight size={12} />
          </a>
          <p className="fp-footer-note">
            Prototype — sessions, calibrations and results are held in memory and
            lost on restart.
          </p>
        </nav>
      </div>

      <div className="fp-footer-bottom">
        <span>© 2026 Q-TRACE</span>
        <span>SIH 2026 project prototype • Experimental research and demonstration platform</span>
      </div>
    </footer>
  );
}
