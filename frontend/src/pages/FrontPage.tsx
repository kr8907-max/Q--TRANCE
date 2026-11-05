




















import { useEffect, useRef } from "react";
import { ArrowRight, ChevronDown } from "lucide-react";
import { useApp } from "../state/AppContext";
import { FrontFieldScene } from "../components/front/FrontFieldScene";
import { FrontFooter } from "../components/front/FrontFooter";
import { useScrollProgress } from "../lib/useScrollProgress";


const FLOW = [
  { k: "CREATE", d: "a session" },
  { k: "SIMULATE", d: "noise / attack conditions" },
  { k: "OBSERVE", d: "measurable evidence" },
  { k: "DETECT", d: "statistical anomalies" },
  { k: "CALIBRATE", d: "expectation & thresholds" },
  { k: "EVALUATE", d: "empirical performance" },
  { k: "EXPLAIN", d: "assumptions & limitations" },
];

const EVIDENCE = [
  { k: "OBSERVATION", d: "Raw, observable protocol and measurement output." },
  { k: "EVIDENCE", d: "Observed values compared against calibrated expectation." },
  { k: "FINDING", d: "A detection result returned by the backend." },
  { k: "INTERPRETATION", d: "Backend-supported, assumption-dependent meaning." },
];

const WHY = [
  "Quantum-inspired protocol simulation",
  "Threat & noise modelling",
  "Observable-only detection",
  "Statistical calibration",
  "Finite-sample evaluation",
  "Transparent security analysis",
];


function Reveal({ children, className = "", delay = 0 }: { children: React.ReactNode; className?: string; delay?: number }) {
  const ref = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            el.classList.add("in");
            io.disconnect();
          }
        }
      },
      { threshold: 0.18 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return (
    <div ref={ref} className={`fp-reveal ${className}`} style={{ transitionDelay: `${delay}ms` }}>
      {children}
    </div>
  );
}
export function FrontPage() {
  const { enterConsole } = useApp();
  const progress = useScrollProgress();
  const howRef = useRef<HTMLElement | null>(null);

  const scrollToHow = () => howRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });

  return (
    <div className="fp">

      <FrontFieldScene progress={progress} className="fp-field" />


      <header className="fp-nav">
        <span className="fp-nav-brand">
          <img className="fp-nav-logo" src="/qtrace-logo.png" alt="" aria-hidden="true" />
          <span className="fp-nav-name">Q-TRACE</span>
        </span>
        <nav className="fp-nav-links" aria-label="Front page">
          <button type="button" onClick={scrollToHow}>How It Works</button>
          <a href="#fp-evidence">Evidence</a>
          <a href="#fp-why">Security Boundary</a>
        </nav>
        <button type="button" className="fp-cta fp-cta-sm" onClick={enterConsole}>
          Enter Console <ArrowRight size={14} />
        </button>
      </header>


      <section className="fp-hero">
        <div className="fp-hero-copy">
          <Reveal>
            <h1 className="fp-title">
              <span className="fp-title-line">Q-TRACE</span>
              <span className="fp-title-sub">
                Quantum Threat &amp; Reliability Analysis for Cryptographic Evidence
              </span>
            </h1>
          </Reveal>
          <Reveal delay={120}>
            <p className="fp-lede">
              Q-TRACE is a research and evidence console for quantum threat and
              reliability analysis of cryptographic evidence under modelled noise
              and attack conditions.
            </p>
          </Reveal>
          <Reveal delay={220}>
            <div className="fp-hero-actions">
              <button type="button" className="fp-cta fp-cta-lg" onClick={enterConsole}>
                Enter Security Console <ArrowRight size={16} />
              </button>
              <button type="button" className="fp-ghost" onClick={scrollToHow}>
                Explore the System
              </button>
            </div>
          </Reveal>
        </div>

        <button
          type="button"
          className="fp-scrollcue"
          onClick={scrollToHow}
          aria-label="Scroll to how it works"
        >
          <ChevronDown size={18} />
        </button>
      </section>


      <section className="fp-section" ref={howRef} id="fp-how">
        <Reveal>
          <p className="fp-kicker">How the system works</p>
          <h2 className="fp-h2">From a session to a security interpretation</h2>
        </Reveal>
        <ol className="fp-flow">
          {FLOW.map((s, i) => (
            <Reveal key={s.k} delay={i * 70} className="fp-flow-item">
              <li className="fp-stage">
                <span className="fp-stage-idx mono">{String(i + 1).padStart(2, "0")}</span>
                <span className="fp-stage-name">{s.k}</span>
                <span className="fp-stage-desc">{s.d}</span>
              </li>
              {i < FLOW.length - 1 && <span className="fp-stage-link" aria-hidden="true" />}
            </Reveal>
          ))}
        </ol>
      </section>


      <section className="fp-section" id="fp-evidence">
        <Reveal>
          <p className="fp-kicker">Evidence, not a score</p>
          <h2 className="fp-h2">Observable evidence over opaque verdicts</h2>
          <p className="fp-body">
            The console evaluates observable evidence rather than presenting an opaque
            security score. Each run moves through a deliberate chain of reasoning.
          </p>
        </Reveal>
        <div className="fp-cards">
          {EVIDENCE.map((e, i) => (
            <Reveal key={e.k} delay={i * 80}>
              <div className="fp-card">
                <span className="fp-card-k mono">{e.k}</span>
                <p className="fp-card-d">{e.d}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </section>


      <section className="fp-section" id="fp-why">
        <Reveal>
          <p className="fp-kicker">Why this project</p>
          <h2 className="fp-h2">A research-grade empirical security prototype</h2>
        </Reveal>
        <ul className="fp-why">
          {WHY.map((w, i) => (
            <Reveal key={w} delay={i * 60}>
              <li className="fp-why-item">{w}</li>
            </Reveal>
          ))}
        </ul>
        <Reveal delay={200}>
          <p className="fp-note">
            Results are empirical, finite-sample and configuration-dependent. The system
            produces evidence and transparent assumptions — not guarantees, proofs, or
            claims of unconditional security.
          </p>
        </Reveal>
      </section>


      <section className="fp-enter">
        <Reveal>
          <h2 className="fp-h2">Ready to operate the system</h2>
          <p className="fp-body">
            The console is the operational environment: sessions, simulation, detection,
            calibration, evaluation and security analysis.
          </p>
          <button type="button" className="fp-cta fp-cta-lg" onClick={enterConsole}>
            Enter Security Console <ArrowRight size={16} />
          </button>
        </Reveal>
      </section>


      <FrontFooter />


      <span className="fp-code mono" aria-hidden="true">
        SIH26141
      </span>
    </div>
  );
}
