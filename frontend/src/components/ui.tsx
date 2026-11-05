import type { ReactNode } from "react";
import { AlertTriangle, Check, Info, Minus, ShieldAlert, X } from "lucide-react";
import type { Tone } from "../lib/format";



export function Card({
  title,
  subtitle,
  icon,
  actions,
  children,
  tight,
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  icon?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  tight?: boolean;
}) {
  return (
    <section className="card">
      {(title || actions) && (
        <header className="card-head">
          {icon && <span className="icon">{icon}</span>}
          <div>
            {title && <h3>{title}</h3>}
            {subtitle && <p>{subtitle}</p>}
          </div>
          {actions && (
            <>
              <div className="head-spacer" />
              <div className="row">{actions}</div>
            </>
          )}
        </header>
      )}
      <div className={tight ? "card-body tight" : "card-body"}>{children}</div>
    </section>
  );
}



export function Badge({
  tone = "neutral",
  children,
  icon,
}: {
  tone?: Tone;
  children: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <span className={`badge ${tone}`}>
      {icon}
      {children}
    </span>
  );
}

export function Dot({ tone = "idle", pulse }: { tone?: "ok" | "warn" | "danger" | "idle"; pulse?: boolean }) {
  return <span className={`dot ${tone} ${pulse ? "pulse" : ""}`} />;
}


export function BoolMark({ value }: { value: boolean | null | undefined }) {
  if (value === null || value === undefined)
    return <Minus size={15} className="faint" aria-label="unknown" />;
  return value ? (
    <Check size={15} style={{ color: "var(--ok)" }} aria-label="yes" />
  ) : (
    <X size={15} style={{ color: "var(--danger)" }} aria-label="no" />
  );
}



export function Button({
  children,
  onClick,
  variant = "default",
  size = "md",
  disabled,
  loading,
  type = "button",
  title,
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: "default" | "primary" | "cyan" | "ghost" | "danger";
  size?: "sm" | "md";
  disabled?: boolean;
  loading?: boolean;
  type?: "button" | "submit";
  title?: string;
}) {
  const cls = ["btn", variant !== "default" ? variant : "", size === "sm" ? "sm": ""]
    .filter(Boolean)
    .join(" ");
  return (
    <button
      className={cls}
      onClick={onClick}
      disabled={disabled || loading}
      type={type}
      title={title}
    >
      {loading ? <span className="spinner" /> : null}
      {children}
    </button>
  );
}



export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="field">
      <label>{label}</label>
      {children}
      {hint && <span className="hint">{hint}</span>}
    </div>
  );
}

export function TextInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input className="input" {...props} />;
}

export function NumberInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input className="input" type="number" {...props} />;
}

export function TextArea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className="textarea" {...props} />;
}

export function Select({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <select
      className="select"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

export function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: ReactNode;
}) {
  return (
    <label className="toggle">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span className="track" />
      <span>{label}</span>
    </label>
  );
}

export function RangeField({
  value,
  min,
  max,
  step,
  onChange,
  format,
  disabled,
}: {
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
  format?: (v: number) => string;

  disabled?: boolean;
}) {
  return (
    <div className="range-wrap" style={disabled ? { opacity: 0.45 } : undefined}>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        disabled={disabled}
      />
      <span className="range-value">{format ? format(value) : value}</span>
    </div>
  );
}



export function Spinner({ label }: { label?: string }) {
  return (
    <div className="loading-block">
      <span className="spinner" />
      {label && <span>{label}</span>}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  body,
}: {
  icon?: ReactNode;
  title: string;
  body?: ReactNode;
}) {
  return (
    <div className="empty">
      {icon && <span className="icon">{icon}</span>}
      <strong style={{ color: "var(--text)", fontSize: 14 }}>{title}</strong>
      {body && <p>{body}</p>}
    </div>
  );
}

const CALLOUT_ICON = {
  evidence: <ShieldAlert size={18} />,
  warn: <AlertTriangle size={18} />,
  danger: <ShieldAlert size={18} />,
  info: <Info size={18} />,
} as const;

export function Callout({
  variant = "info",
  title,
  children,
}: {
  variant?: keyof typeof CALLOUT_ICON;
  title?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className={`callout ${variant}`}>
      <span className="icon">{CALLOUT_ICON[variant]}</span>
      <div style={{ minWidth: 0 }}>
        {title && <h4>{title}</h4>}
        {children}
      </div>
    </div>
  );
}



export function JsonBlock({ data, maxHeight }: { data: unknown; maxHeight?: number }) {
  const text = typeof data === "string" ? data : JSON.stringify(data, null, 2);
  return (
    <pre className="json" style={maxHeight ? { maxHeight } : undefined}>
      {text}
    </pre>
  );
}

export function KeyValue({
  entries,
}: {
  entries: [ReactNode, ReactNode][];
}) {
  return (
    <dl className="kv">
      {entries.map(([k, v], i) => (
        <div key={i} style={{ display: "contents" }}>
          <dt>{k}</dt>
          <dd>{v}</dd>
        </div>
      ))}
    </dl>
  );
}

export function Stat({
  label,
  value,
  sub,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
}) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <div className="section-title">
      <h3>{children}</h3>
      <span className="rule" />
    </div>
  );
}
