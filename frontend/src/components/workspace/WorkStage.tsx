












import type { ReactNode } from "react";

interface WorkStageProps {
  index: string;
  name: string;
  subtitle: string;
  lede?: ReactNode;
  action?: ReactNode;
}

export function WorkStage({ index, name, subtitle, lede, action }: WorkStageProps) {
  return (
    <header className="workstage">
      <span className="workstage-numeral mono" aria-hidden="true">{index}</span>
      <div className="workstage-copy">
        <span className="workstage-kicker mono">Stage {index}</span>
        <h2 className="workstage-title">{name}</h2>
        <p className="workstage-sub">{subtitle}</p>
        {lede && <p className="workstage-lede">{lede}</p>}
      </div>
      {action && <div className="workstage-action">{action}</div>}
    </header>
  );
}





export function DetailsDisclosure({
  summary,
  children,
  defaultOpen = false,
}: {
  summary: ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  return (
    <details className="disclosure" open={defaultOpen || undefined}>
      <summary className="disclosure-summary">{summary}</summary>
      <div className="disclosure-body">{children}</div>
    </details>
  );
}





export interface FlowStep {
  label: string;
  state: "done" | "current" | "todo";
}

export function SteppedFlow({ steps }: { steps: FlowStep[] }) {
  return (
    <ol className="stepflow" aria-label="Progress">
      {steps.map((s, i) => (
        <li key={s.label} className={`stepflow-step ${s.state}`}>
          <span className="stepflow-dot" aria-hidden="true" />
          <span className="stepflow-label">{s.label}</span>
          {i < steps.length - 1 && <span className="stepflow-link" aria-hidden="true" />}
        </li>
      ))}
    </ol>
  );
}
