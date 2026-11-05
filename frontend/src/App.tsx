import { useState } from "react";
import { Header, Sidebar } from "./components/Shell";
import { Toasts } from "./components/Toasts";
import { useApp } from "./state/AppContext";
import { ConsoleField } from "./components/console/ConsoleField";
import { FrontPage } from "./pages/FrontPage";
import { Console } from "./pages/Console";
import { SessionStudio } from "./pages/SessionStudio";
import { SimulationBench } from "./pages/SimulationBench";
import { DetectionConsole } from "./pages/DetectionConsole";
import { CalibrationLab } from "./pages/CalibrationLab";
import { EvaluationCenter } from "./pages/EvaluationCenter";
import { SecurityArgument } from "./pages/SecurityArgument";

export default function App() {
  const { view, entered, connection } = useApp();
  const [navOpen, setNavOpen] = useState(false);

  if (!entered) {
    return (
      <>
        <FrontPage />
        <Toasts />
      </>
    );
  }

  return (
    <div className="app">
      <ConsoleField status={connection.status} pulseKey={connection.lastChecked} className="console-field" />
      <Sidebar open={navOpen} onClose={() => setNavOpen(false)} />
      <div className={`scrim ${navOpen ? "show" : ""}`} onClick={() => setNavOpen(false)} />
      <div className="main">
        <Header onMenu={() => setNavOpen((o) => !o)} />
        <main className="content" key={view}>
          {view === "dashboard" && <Console />}
          {view === "sessions" && <SessionStudio />}
          {view === "simulation" && <SimulationBench />}
          {view === "detection" && <DetectionConsole />}
          {view === "calibration" && <CalibrationLab />}
          {view === "evaluation" && <EvaluationCenter />}
          {view === "security" && <SecurityArgument />}
        </main>
      </div>
      <span className="app-code mono" aria-hidden="true">SIH26141</span>
      <Toasts />

      <span className="app-code mono" aria-hidden="true">
        SIH26141
      </span>
    </div>
  );
}
