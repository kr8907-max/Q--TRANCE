

export function fmtNum(value: number | null | undefined, digits = 4): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  if (!Number.isFinite(value)) return String(value);
  return value.toFixed(digits);
}

export function fmtPct(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

export function fmtInt(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toLocaleString();
}

export function shortId(value: string | null | undefined, len = 10): string {
  if (!value) return "—";
  return value.length > len ? `${value.slice(0, len)}…` : value;
}


export type Tone = "ok" | "warn" | "danger" | "info" | "violet" | "neutral";

export function boolTone(value: boolean | null | undefined): Tone {
  if (value === null || value === undefined) return "neutral";
  return value ? "ok" : "danger";
}

export function severityTone(severity: string): Tone {
  switch (severity.toUpperCase()) {
    case "HIGH":
    case "CRITICAL":
      return "danger";
    case "MEDIUM":
      return "warn";
    case "LOW":
      return "info";
    default:
      return "neutral";
  }
}

export function lifecycleTone(lifecycle: string): Tone {
  switch (lifecycle.toUpperCase()) {
    case "VERIFIED":
    case "SIGNED":
      return "ok";
    case "REJECTED":
    case "EXPIRED":
      return "danger";
    case "CREATED":
      return "info";
    default:
      return "neutral";
  }
}


export function statusTone(status: string): Tone {
  const s = status.toUpperCase();
  if (s.includes("REJECT") || s.includes("FAIL") || s.includes("ANOMAL") || s.includes("BLOCK"))
    return "danger";
  if (s.includes("WARN") || s.includes("REVIEW") || s.includes("SUSPIC")) return "warn";
  if (s.includes("ACCEPT") || s.includes("PASS") || s.includes("OK") || s.includes("CONSISTENT"))
    return "ok";
  return "neutral";
}

export function titleCase(value: string): string {
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}


export function prettyJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}


export function timeLabel(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}
