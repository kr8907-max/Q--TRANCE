import { AlertTriangle, CheckCircle2, Info, ShieldAlert, X } from "lucide-react";
import { useApp, type ToastVariant } from "../state/AppContext";

const ICONS: Record<ToastVariant, React.ReactNode> = {
  success: <CheckCircle2 size={18} />,
  error: <ShieldAlert size={18} />,
  warn: <AlertTriangle size={18} />,
  info: <Info size={18} />,
};

export function Toasts() {
  const { toasts, dismissToast } = useApp();
  if (toasts.length === 0) return null;
  return (
    <div className="toasts" role="status" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={`toast ${t.variant}`}>
          <span className="t-icon">{ICONS[t.variant]}</span>
          <div className="t-body">
            <div className="t-title">
              {t.title}
              {t.code && <span className="t-code">{t.code}</span>}
            </div>
            {t.message && <div className="t-msg">{t.message}</div>}
            {t.details && Object.keys(t.details).length > 0 && (
              <details style={{ marginTop: 6, fontSize: 11 }}>
                <summary style={{ cursor: "pointer", opacity: 0.75 }}>technical details</summary>
                <pre
                  className="json"
                  style={{ marginTop: 4, maxHeight: 160, overflow: "auto", fontSize: 11 }}
                >
                  {JSON.stringify(t.details, null, 2)}
                </pre>
              </details>
            )}
          </div>
          <button className="t-close" onClick={() => dismissToast(t.id)} aria-label="Dismiss">
            <X size={15} />
          </button>
        </div>
      ))}
    </div>
  );
}
