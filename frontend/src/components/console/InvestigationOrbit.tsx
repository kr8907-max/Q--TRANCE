



















import { useEffect, useRef } from "react";
import type { ViewKey } from "../../state/AppContext";
import { shortId } from "../../lib/format";

export interface OrbitStage {
  key: string;
  label: string;
  view: ViewKey;
  state: "complete" | "ready" | "offline";
  meta?: string;
}

interface OrbitProps {
  stages: OrbitStage[];

  sessionId: string | null;
  online: boolean;
  onNavigate: (view: ViewKey) => void;
  onFocus: (key: string | null) => void;
  className?: string;
}

const RGB = {
  accent: "76, 175, 119",
  accentHi: "126, 208, 155",
  slate: "91, 156, 196",
  teal: "78, 168, 160",
  faint: "113, 124, 112",
  text: "194, 204, 193",
};


const RING_OF: Record<string, number> = {
  create: 0, simulate: 0, observe: 0,
  detect: 1, calibrate: 1,
  evaluate: 2, explain: 2,
};
const RING_R = [0.60, 0.92, 1.26];
const RING_TILT = [0.42, -0.28, 0.18];
const RING_SPEED = [0.0032, -0.0021, 0.0014];


const BASE_SCALE = 1.85;

function useReduced(): boolean {
  return useRef(
    typeof window !== "undefined" &&
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  ).current;
}

interface NodePos { x: number; y: number; r: number; z: number; }

export function InvestigationOrbit({ stages, sessionId, online, onNavigate, onFocus, className }: OrbitProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const reduced = useReduced();

  const stagesRef = useRef(stages);
  const sessionRef = useRef(sessionId);
  const onlineRef = useRef(online);
  const navRef = useRef(onNavigate);
  const focusRef = useRef(onFocus);
  stagesRef.current = stages;
  sessionRef.current = sessionId;
  onlineRef.current = online;
  navRef.current = onNavigate;
  focusRef.current = onFocus;

  const hoverRef = useRef<number>(-1);
  const nodePos = useRef<NodePos[]>([]);
  const pointer = useRef({ x: 0.5, y: 0.5, tx: 0.5, ty: 0.5 });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return;

    let raf = 0;
    let running = true;
    let W = 0, H = 0;
    let t = 0;
    let lastNow = performance.now();
    let yaw = 0;
    let pit = 0;
    let zoom = 1;


    function ringAngles(ring: number): number[] {
      const keys = stagesRef.current.filter((s) => RING_OF[s.key] === ring);
      const n = keys.length;
      return keys.map((_, i) => (i / Math.max(1, n)) * Math.PI * 2 + ring * 0.7);
    }

    function project(x: number, y: number, z: number) {
      const cosy = Math.cos(yaw), siny = Math.sin(yaw);
      const cosp = Math.cos(pit), sinp = Math.sin(pit);
      const x1 = x * cosy + z * siny;
      const z1 = -x * siny + z * cosy;
      const y1 = y * cosp - z1 * sinp;
      const z2 = y * sinp + z1 * cosp;
      const zp = z2 + 3.4;
      if (zp <= 0.2) return null;
      const f = Math.min(W, H) * 0.98 * BASE_SCALE * zoom;
      return { sx: W * 0.5 + (x1 * f) / zp, sy: H * 0.5 + (y1 * f) / zp, zp };
    }

    function stagePoint(s: OrbitStage, idxInRing: number) {
      const ring = RING_OF[s.key] ?? 0;
      const angles = ringAngles(ring);
      const a = angles[idxInRing] + t * RING_SPEED[ring];
      const rr = RING_R[ring];
      const x0 = Math.cos(a) * rr;
      const z0 = Math.sin(a) * rr;
      const tilt = RING_TILT[ring];
      const x1 = x0 * Math.cos(tilt);
      const y1 = x0 * Math.sin(tilt);
      return { x: x1, y: y1, z: z0 };
    }

    function frame(now: number) {
      if (!running || !ctx) return;
      const dtms = Math.min(50, now - lastNow);
      lastNow = now;
      const dt = dtms / 16.667;
      const motion = reduced ? 0 : 1;
      t += dt * motion;


      const pk = 1 - Math.exp(-dt * 2.6);
      pointer.current.x += (pointer.current.tx - pointer.current.x) * pk;
      pointer.current.y += (pointer.current.ty - pointer.current.y) * pk;
      yaw = t * 0.0011 + (pointer.current.x - 0.5) * 0.34;
      pit = -0.30 + (pointer.current.y - 0.5) * 0.22;
      zoom += ((onlineRef.current ? 1 : 0.94) - zoom) * (1 - Math.exp(-dt * 1.5));

      ctx.clearRect(0, 0, W, H);
      const core = project(0, 0, 0);
      const f = Math.min(W, H) * 0.98 * BASE_SCALE * zoom;


      if (core) {
        const hr = (0.62 * f) / core.zp;
        const hz = ctx.createRadialGradient(core.sx, core.sy, 0, core.sx, core.sy, hr * 1.6);
        hz.addColorStop(0, `rgba(${RGB.accent}, ${sessionRef.current ? 0.10 : 0.05})`);
        hz.addColorStop(1, "rgba(0,0,0,0)");
        ctx.fillStyle = hz;
        ctx.beginPath();
        ctx.arc(core.sx, core.sy, hr * 1.6, 0, Math.PI * 2);
        ctx.fill();
      }


      for (let ring = 0; ring < 3; ring++) {
        for (const back of [true, false]) {
          ctx.beginPath();
          let pen = false;
          const tone = ring === 0 ? RGB.accent : ring === 1 ? RGB.slate : RGB.teal;
          const alpha = back ? 0.07 : 0.16;
          for (let s = 0; s <= 72; s++) {
            const a = (s / 72) * Math.PI * 2;
            const rr = RING_R[ring];
            const x0 = Math.cos(a) * rr;
            const z0 = Math.sin(a) * rr;
            if ((z0 > 0) !== back) { pen = false; continue; }
            const tilt = RING_TILT[ring] + t * RING_SPEED[ring] * 0.25;
            const x1 = x0 * Math.cos(tilt);
            const y1 = x0 * Math.sin(tilt);
            const q = project(x1, y1, z0);
            if (!q) { pen = false; continue; }
            if (!pen) { ctx.moveTo(q.sx, q.sy); pen = true; } else ctx.lineTo(q.sx, q.sy);
          }
          ctx.strokeStyle = `rgba(${tone}, ${alpha})`;
          ctx.lineWidth = back ? 1 : 1.2;
          ctx.stroke();
        }
      }


      if (core && sessionRef.current) {
        ctx.lineWidth = 1;
        stagesRef.current.forEach((s, i) => {
          if (s.state !== "complete") return;
          const p3 = stagePoint(s, ringIndexOf(i));
          const q = project(p3.x, p3.y, p3.z);
          if (!q) return;
          ctx.strokeStyle = `rgba(${RGB.accent}, 0.14)`;
          ctx.beginPath();
          ctx.moveTo(core.sx, core.sy);
          ctx.lineTo(q.sx, q.sy);
          ctx.stroke();
        });
      }


      if (core) {
        const nr = Math.max(9, (0.075 * f) / core.zp);
        if (sessionRef.current) {
          ctx.beginPath();
          ctx.arc(core.sx, core.sy, nr, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(${RGB.accentHi}, 0.92)`;
          ctx.fill();
          ctx.beginPath();
          ctx.arc(core.sx, core.sy, nr + 5, 0, Math.PI * 2);
          ctx.strokeStyle = `rgba(${RGB.accent}, 0.4)`;
          ctx.stroke();
          drawLabel(core.sx, core.sy + nr + 16, shortId(sessionRef.current, 10), RGB.accentHi, 0.9);
        } else {
          ctx.beginPath();
          ctx.arc(core.sx, core.sy, nr, 0, Math.PI * 2);
          ctx.strokeStyle = `rgba(${RGB.faint}, 0.55)`;
          ctx.setLineDash([3, 4]);
          ctx.stroke();
          ctx.setLineDash([]);
          drawLabel(core.sx, core.sy + nr + 16, "AWAITING INVESTIGATION", RGB.faint, 0.8);
        }
      }


      const positions: NodePos[] = [];
      const ringCursor: Record<number, number> = { 0: 0, 1: 0, 2: 0 };
      stagesRef.current.forEach((s, i) => {
        const ring = RING_OF[s.key] ?? 0;
        const idxInRing = ringCursor[ring]++;
        const p3 = stagePoint(s, idxInRing);
        const q = project(p3.x, p3.y, p3.z);
        if (!q) return;
        const depth = Math.max(0.3, 1 - (q.zp - 2.6) / 2.2);
        const hovered = hoverRef.current === i;
        const base = Math.max(3.2, (0.026 * f) / q.zp);
        const r = hovered ? base * 1.5 : base;
        positions[i] = { x: q.sx, y: q.sy, r: r + 8, z: q.zp };

        let fill: string | null = null;
        let stroke = `rgba(${RGB.faint}, ${0.5 * depth})`;
        let alpha = 0.6 * depth;
        if (s.state === "complete") {
          fill = `rgba(${RGB.accent}, ${0.9 * depth})`;
          stroke = `rgba(${RGB.accent}, ${0.9 * depth})`;
          alpha = 0.9 * depth;
        } else if (s.state === "ready") {
          stroke = `rgba(${RGB.slate}, ${0.75 * depth})`;
          alpha = 0.7 * depth;
        } else {
          alpha = 0.35 * depth;
        }
        if (hovered) alpha = 1;

        ctx.beginPath();
        ctx.arc(q.sx, q.sy, r, 0, Math.PI * 2);
        if (fill) { ctx.fillStyle = fill; ctx.fill(); }
        ctx.strokeStyle = hovered ? `rgba(${RGB.accentHi}, 0.95)` : stroke;
        ctx.lineWidth = hovered ? 1.6 : 1.1;
        ctx.stroke();

        drawLabel(q.sx, q.sy - r - 8, s.label.toUpperCase(), hovered ? RGB.accentHi : RGB.text, hovered ? 0.95 : alpha * 0.85);
      });
      nodePos.current = positions;
    }

    function ringIndexOf(stageIdx: number): number {
      const key = stagesRef.current[stageIdx]?.key ?? "";
      const ring = RING_OF[key] ?? 0;
      let idx = 0;
      for (let i = 0; i < stageIdx; i++) {
        if ((RING_OF[stagesRef.current[i].key] ?? 0) === ring) idx++;
      }
      return idx;
    }

    function drawLabel(x: number, y: number, text: string, rgb: string, alpha: number) {
      ctx!.font = "600 9.5px \"JetBrains Mono\", monospace";
      ctx!.textAlign = "center";
      ctx!.fillStyle = `rgba(${rgb}, ${alpha.toFixed(3)})`;
      ctx!.fillText(text, x, y);
    }

    function hitTest(cx: number, cy: number): number {
      const rect = canvas!.getBoundingClientRect();
      const mx = cx - rect.left, my = cy - rect.top;
      let best = -1, bestD = 1e9;
      nodePos.current.forEach((p, i) => {
        if (!p) return;
        const d = Math.hypot(p.x - mx, p.y - my);
        if (d < p.r && d < bestD) { best = i; bestD = d; }
      });
      return best;
    }

    function onMove(e: PointerEvent) {
      const rect = canvas!.getBoundingClientRect();
      pointer.current.tx = (e.clientX - rect.left) / Math.max(1, rect.width);
      pointer.current.ty = (e.clientY - rect.top) / Math.max(1, rect.height);
      const hit = hitTest(e.clientX, e.clientY);
      if (hit !== hoverRef.current) {
        hoverRef.current = hit;
        canvas!.style.cursor = hit >= 0 ? "pointer" : "default";
        focusRef.current(hit >= 0 ? stagesRef.current[hit].key : null);
        if (reduced) frame(performance.now());
      }
    }

    function onLeave() {
      hoverRef.current = -1;
      canvas!.style.cursor = "default";
      focusRef.current(null);
      if (reduced) frame(performance.now());
    }

    function onClick(e: PointerEvent) {
      const hit = hitTest(e.clientX, e.clientY);
      if (hit >= 0) {
        const st = stagesRef.current[hit];
        if (st.state !== "offline") navRef.current(st.view);
      }
    }

    function loop(now: number) {
      frame(now);
      if (!reduced) raf = window.requestAnimationFrame(loop);
    }

    function onVisibility() {
      if (document.hidden) {
        running = false;
        window.cancelAnimationFrame(raf);
      } else if (!running) {
        running = true;
        lastNow = performance.now();
        if (reduced) frame(lastNow); else raf = window.requestAnimationFrame(loop);
      }
    }

    function onResize() {
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      W = Math.max(1, Math.floor(rect.width));
      H = Math.max(1, Math.floor(rect.height));
      const dpr = Math.min(window.devicePixelRatio || 1, 1.75);
      canvas.width = Math.floor(W * dpr);
      canvas.height = Math.floor(H * dpr);
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
      lastNow = performance.now();
      if (reduced) frame(lastNow);
    }

    onResize();
    if (reduced) frame(lastNow); else raf = window.requestAnimationFrame(loop);

    const ro = new ResizeObserver(onResize);
    ro.observe(canvas);
    canvas.addEventListener("pointermove", onMove, { passive: true });
    canvas.addEventListener("pointerleave", onLeave);
    canvas.addEventListener("click", onClick);
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      running = false;
      window.cancelAnimationFrame(raf);
      ro.disconnect();
      canvas.removeEventListener("pointermove", onMove);
      canvas.removeEventListener("pointerleave", onLeave);
      canvas.removeEventListener("click", onClick);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [reduced]);

  return (
    <div ref={wrapRef} className={className}>
      <canvas
        ref={canvasRef}
        className="orbit-canvas"
        role="img"
        aria-label="Investigation map: the current session at the centre with the seven workflow stages orbiting. Use the sidebar or the focus panel to navigate."
      />
    </div>
  );
}
