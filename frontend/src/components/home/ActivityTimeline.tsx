







import { Activity, FileSignature, HeartPulse } from "lucide-react";
import type { SessionSummary } from "../../api/types";
import { EmptyState } from "../ui";
import { shortId, timeLabel } from "../../lib/format";

interface ActivityItem {
  id: string;
  icon: "session" | "probe";
  label: string;
  detail?: string;
  at: string | null;
}

interface ActivityTimelineProps {
  sessions: SessionSummary[];
  lastChecked: number | null;
  loading: boolean;
}

export function ActivityTimeline({ sessions, lastChecked, loading }: ActivityTimelineProps) {
  const items: ActivityItem[] = [];

  for (const s of sessions.slice(0, 5)) {
    items.push({
      id: s.session_id,
      icon: "session",
      label: `Session ${s.lifecycle.toLowerCase()}`,
      detail: shortId(s.session_id, 10),
      at: s.created_at,
    });
  }
  if (lastChecked) {
    items.push({
      id: "probe",
      icon: "probe",
      label: "Backend health probe",
      detail: "/health · /ready",
      at: new Date(lastChecked).toISOString(),
    });
  }
  items.sort((a, b) => new Date(b.at ?? 0).getTime() - new Date(a.at ?? 0).getTime());

  return (
    <div className="cc-panel cc-activity">
      <div className="cc-panel-head">
        <span className="cc-panel-kicker">Recent Activity</span>
        <h3>Timeline</h3>
      </div>

      {loading ? (
        <div className="cc-skel" style={{ width: "100%", height: 140 }} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={<Activity size={22} />}
          title="No activity yet"
          body="Activity appears here as you create sessions and the backend is probed."
        />
      ) : (
        <ul className="cc-timeline">
          {items.map((it) => (
            <li className="cc-timeline-item" key={`${it.id}-${it.at}`}>
              <span className="cc-timeline-icon" aria-hidden="true">
                {it.icon === "session" ? <FileSignature size={14} /> : <HeartPulse size={14} />}
              </span>
              <div className="cc-timeline-body">
                <div className="cc-timeline-label">{it.label}</div>
                {it.detail && <div className="cc-timeline-detail mono">{it.detail}</div>}
              </div>
              <time className="cc-timeline-time mono">{timeLabel(it.at)}</time>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
