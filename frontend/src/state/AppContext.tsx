import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { getHealth, getReady, getVersion, ApiError } from "../api/client";
import type {
  DetectionRequest,
  HealthResponse,
  ReadyResponse,
  VersionResponse,
} from "../api/types";



export const VIEWS = [
  { key: "dashboard", label: "Dashboard", index: "01" },
  { key: "sessions", label: "Session Studio", index: "02" },
  { key: "simulation", label: "Simulation Bench", index: "03" },
  { key: "detection", label: "Detection Console", index: "04" },
  { key: "calibration", label: "Calibration Lab", index: "05" },
  { key: "evaluation", label: "Evaluation Center", index: "06" },
  { key: "security", label: "Security Argument", index: "07" },
] as const;

export type ViewKey = (typeof VIEWS)[number]["key"];



export type ToastVariant = "success" | "error" | "info" | "warn";

export interface Toast {
  id: number;
  variant: ToastVariant;
  title: string;
  message?: string;
  code?: string;

  details?: Record<string, unknown> | null;
}



export type ConnStatus = "checking" | "online" | "degraded" | "offline";

export interface ConnectionState {
  status: ConnStatus;
  health: HealthResponse | null;
  ready: ReadyResponse | null;
  version: VersionResponse | null;
  lastChecked: number | null;
  error: string | null;
}



export interface Handoff {
  request: DetectionRequest;
  origin: string;
  at: number;
}

interface AppContextValue {
  view: ViewKey;
  navigate: (v: ViewKey) => void;

  entered: boolean;
  enterConsole: () => void;
  toasts: Toast[];
  pushToast: (t: Omit<Toast, "id">) => void;
  dismissToast: (id: number) => void;

  reportError: (title: string, err: unknown) => void;
  connection: ConnectionState;
  refreshConnection: () => void;
  handoff: Handoff | null;
  sendToDetection: (h: Handoff) => void;
  clearHandoff: () => void;
}

const AppContext = createContext<AppContextValue | null>(null);

const POLL_MS = 8000;

export function AppProvider({ children }: { children: ReactNode }) {
  const [view, setView] = useState<ViewKey>("dashboard");
  const [entered, setEntered] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [handoff, setHandoff] = useState<Handoff | null>(null);
  const [connection, setConnection] = useState<ConnectionState>({
    status: "checking",
    health: null,
    ready: null,
    version: null,
    lastChecked: null,
    error: null,
  });
  const toastId = useRef(0);

  const dismissToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const pushToast = useCallback(
    (t: Omit<Toast, "id">) => {
      const id = ++toastId.current;
      setToasts((prev) => [...prev.slice(-4), { ...t, id }]);

      const ttl = t.variant === "error" ? 9000 : 4200;
      window.setTimeout(() => dismissToast(id), ttl);
    },
    [dismissToast],
  );

  const reportError = useCallback(
    (title: string, err: unknown) => {
      if (err instanceof ApiError) {
        pushToast({
          variant: "error",
          title,
          code: err.code,
          message: err.message + (err.requestId ? ` · ${err.requestId}` : ""),
          details: err.details,
        });
      } else {
        pushToast({
          variant: "error",
          title,
          message: err instanceof Error ? err.message : String(err),
        });
      }
    },
    [pushToast],
  );

  const probe = useCallback(async () => {
    try {
      const [health, ready] = await Promise.all([getHealth(), getReady()]);

      let version: VersionResponse | null = null;
      try {
        version = await getVersion();
      } catch {
        version = null;
      }
      setConnection({
        status: health.status === "degraded" || !ready.ready ? "degraded" : "online",
        health,
        ready,
        version,
        lastChecked: Date.now(),
        error: null,
      });
    } catch (err) {
      setConnection((prev) => ({
        ...prev,
        status: "offline",
        error: err instanceof Error ? err.message : "unreachable",
        lastChecked: Date.now(),
      }));
    }
  }, []);

  useEffect(() => {
    void probe();
    const id = window.setInterval(() => void probe(), POLL_MS);
    return () => window.clearInterval(id);
  }, [probe]);

  const navigate = useCallback((v: ViewKey) => {
    setView(v);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  const sendToDetection = useCallback(
    (h: Handoff) => {
      setHandoff(h);
      setView("detection");
      window.scrollTo({ top: 0, behavior: "smooth" });
    },
    [],
  );

  const enterConsole = useCallback(() => {
    setEntered(true);
    setView("dashboard");
    window.scrollTo({ top: 0 });
  }, []);

  const clearHandoff = useCallback(() => setHandoff(null), []);

  const value = useMemo<AppContextValue>(
    () => ({
      view,
      navigate,
      entered,
      enterConsole,
      toasts,
      pushToast,
      dismissToast,
      reportError,
      connection,
      refreshConnection: () => void probe(),
      handoff,
      sendToDetection,
      clearHandoff,
    }),
    [
      view,
      navigate,
      entered,
      enterConsole,
      toasts,
      pushToast,
      dismissToast,
      reportError,
      connection,
      probe,
      handoff,
      sendToDetection,
      clearHandoff,
    ],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}
