

















import { useEffect, useRef } from "react";
import { frameDeltaMs } from "../../lib/frameDelta";

const RGB = {
  accent: "76, 175, 119",
  slate: "91, 156, 196",
  teal: "78, 168, 160",
  faint: "113, 124, 112",
  danger: "224, 115, 95",
};

type Tone = keyof typeof RGB;

interface FP { x: number; y: number; z: number; vx: number; vy: number; tone: Tone; ph: number; }
interface FL { x: number; y: number; speed: number; len: number; tone: Tone; off: number; age: number; }
interface Ripple { x: number; y: number; r: number; a: number; }


function hash(x: number, y: number, z: number): number {
  const s = Math.sin(x * 127.1 + y * 311.7 + z * 74.7) * 43758.5453;
  return s - Math.floor(s);
}
function sm(t: number): number { return t * t * (3 - 2 * t); }
function vnoise(x: number, y: number, z: number): number {
  const xi = Math.floor(x), yi = Math.floor(y), zi = Math.floor(z);
  const xf = x - xi, yf = y - yi, zf = z - zi;
  const u = sm(xf), v = sm(yf), w = sm(zf);
  function g(a: number, b: number, cc: number) { return hash(xi + a, yi + b, zi + cc) * 2 - 1; }
  function l(a: number, b: number, t2: number) { return a + (b - a) * t2; }
  const c000 = g(0, 0, 0), c100 = g(1, 0, 0), c010 = g(0, 1, 0), c110 = g(1, 1, 0);
  const c001 = g(0, 0, 1), c101 = g(1, 0, 1), c011 = g(0, 1, 1), c111 = g(1, 1, 1);
  return l(l(l(c000, c100, u), l(c010, c110, u), v), l(l(c001, c101, u), l(c011, c111, u), v), w);
}
function flowX(x: number, y: number, t: number): number { return vnoise(x * 1.5 + t, y * 1.5, 3.7); }
function flowY(x: number, y: number, t: number): number { return vnoise(x * 1.5 + 19.1, y * 1.5 + t, 8.2); }

function useReduced(): boolean {
  return useRef(
    typeof window !== "undefined" &&
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  ).current;
}

export type ConsoleStatus = "checking" | "online" | "degraded" | "offline";

interface ConsoleFieldProps {
  status: ConsoleStatus;

  pulseKey: number | null;
  className?: string;
}

export function ConsoleField({ status, pulseKey, className }: ConsoleFieldProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const statusRef = useRef<ConsoleStatus>(status);
  const pulseRef = useRef<number | null>(pulseKey);
  const reduced = useReduced();
  statusRef.current = status;
  pulseRef.current = pulseKey;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return;

    let raf = 0;
    let running = true;
    let W = 0, H = 0;
    let parts: FP[] = [];
    let lines: FL[] = [];
    const ripples: Ripple[] = [];
    let t = 0;
    let lastNow = performance.now();
    let seenPulse: number | null = null;
    let coh = 0.5;

    function seed() {
      const density = Math.max(0.7, Math.min(1.3, (W * H) / (1500 * 950)));
      parts = [];
      const np = Math.round(170 * density);
      for (let i = 0; i < np; i++) {
        parts.push({
          x: Math.random() * W,
          y: Math.random() * H,
          z: Math.random(),
          vx: 0, vy: 0,
          tone: i % 11 === 0 ? "accent" : i % 7 === 0 ? "slate" : i % 5 === 0 ? "teal" : "faint",
          ph: Math.random() * Math.PI * 2,
        });
      }
      lines = [];
      const nl = Math.round(70 * density);
      for (let i = 0; i < nl; i++) {
        lines.push({
          x: Math.random() * W,
          y: Math.random() * H,
          speed: 0.8 + Math.random() * 0.5,
          len: 5 + Math.floor(Math.random() * 6),
          tone: Math.random() < 0.2 ? "slate" : "faint",
          off: Math.random() * 100,
          age: Math.random() * 80,
        });
      }
    }


    function targetCoh(): number {
      switch (statusRef.current) {
        case "online": return 1;
        case "degraded": return 0.6;
        case "checking": return 0.45;
        case "offline": return 0.18;
        default: return 0.5;
      }
    }

    function frame(now: number) {
      if (!running || !ctx) return;




      const dtms = frameDeltaMs(now, lastNow);
      lastNow = now;
      const dt = dtms / 16.667;
      const motion = reduced ? 0 : 1;
      t += dt * motion;


      coh += (targetCoh() - coh) * (1 - Math.exp(-dt * 1.8));


      const pk = pulseRef.current;
      if (!reduced && pk !== null && pk !== seenPulse) {
        seenPulse = pk;
        ripples.push({ x: W * 0.68, y: H * 0.32, r: 0, a: 1 });
      }
      for (let i = ripples.length - 1; i >= 0; i--) {
        ripples[i].r += 2.1 * dt * motion;
        ripples[i].a *= Math.pow(0.985, dt);
        if (ripples[i].a < 0.02) ripples.splice(i, 1);
      }

      ctx.clearRect(0, 0, W, H);


      const hx = W * 0.62, hy = H * 0.3;
      const hr = Math.min(W, H) * 0.55;
      const haze = ctx.createRadialGradient(hx, hy, 0, hx, hy, hr);
      const hazeRGB = statusRef.current === "offline" ? RGB.danger : RGB.accent;
      haze.addColorStop(0, `rgba(${hazeRGB}, ${(0.05 * coh).toFixed(3)})`);
      haze.addColorStop(0.6, `rgba(${RGB.teal}, ${(0.02 * coh).toFixed(3)})`);
      haze.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = haze;
      ctx.beginPath();
      ctx.arc(hx, hy, hr, 0, Math.PI * 2);
      ctx.fill();


      ctx.lineWidth = 1;
      const ft = t * 0.004;
      for (const ln of lines) {
        ln.age += dt;
        const fadeIn = Math.min(1, ln.age / 80);
        const sp = 0.14 * ln.speed * dt * motion;
        ln.x += flowX(ln.x * 0.004, ln.y * 0.004, ft + ln.off) * sp * 10;
        ln.y += flowY(ln.x * 0.004, ln.y * 0.004, ft + ln.off) * sp * 10;
        for (const rp of ripples) {
          const d = Math.hypot(ln.x - rp.x, ln.y - rp.y) + 1e-4;
          const band = Math.abs(d - rp.r);
          if (band < 60) {
            const push = (1 - band / 60) * rp.a * 0.6 * dt * motion;
            ln.x += ((ln.x - rp.x) / d) * push;
            ln.y += ((ln.y - rp.y) / d) * push;
          }
        }
        if (ln.x < -40 || ln.x > W + 40 || ln.y < -40 || ln.y > H + 40) {
          ln.x = Math.random() * W;
          ln.y = Math.random() * H;
          ln.age = 0;
        }
        ctx.beginPath();
        let px = ln.x, py = ln.y;
        let first = true;
        let peak = 0;
        for (let s = 0; s < ln.len; s++) {
          if (first) { ctx.moveTo(px, py); first = false; } else ctx.lineTo(px, py);
          peak = Math.max(peak, (ln.tone === "slate" ? 0.07 : 0.04) * coh * fadeIn);
          px += flowX(px * 0.004, py * 0.004, ft + ln.off) * 7;
          py += flowY(px * 0.004, py * 0.004, ft + ln.off) * 7;
        }
        if (peak > 0.008) {
          ctx.strokeStyle = `rgba(${RGB[ln.tone]}, ${Math.min(0.16, peak).toFixed(3)})`;
          ctx.stroke();
        }
      }


      for (const pt of parts) {
        const ft2 = t * 0.004 + pt.ph;
        const drift = 0.05 + pt.z * 0.12;
        pt.vx += (flowX(pt.x * 0.004, pt.y * 0.004, ft2) * drift - pt.vx) * 0.03 * dt;
        pt.vy += (flowY(pt.x * 0.004, pt.y * 0.004, ft2) * drift - pt.vy) * 0.03 * dt;
        pt.x += pt.vx * dt * motion * 10;
        pt.y += pt.vy * dt * motion * 10;
        if (pt.x < -20 || pt.x > W + 20 || pt.y < -20 || pt.y > H + 20) {
          pt.x = Math.random() * W;
          pt.y = Math.random() * H;
          pt.vx = pt.vy = 0;
        }
        const depth = 0.35 + pt.z * 0.65;
        const tw = 0.5 + 0.5 * Math.sin(t * 0.01 + pt.ph);
        const a = (0.06 + 0.2 * tw) * depth * coh;
        if (a < 0.012) continue;
        const sz = 0.5 + pt.z * 1.2;
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, sz, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${RGB[pt.tone]}, ${Math.min(0.6, a).toFixed(3)})`;
        ctx.fill();
      }


      for (const rp of ripples) {
        ctx.beginPath();
        ctx.arc(rp.x, rp.y, rp.r, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(${RGB.accent}, ${(0.18 * rp.a).toFixed(3)})`;
        ctx.lineWidth = 1;
        ctx.stroke();
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
      seed();
      lastNow = performance.now();
      if (reduced) frame(lastNow);
    }

    onResize();
    if (reduced) frame(lastNow); else raf = window.requestAnimationFrame(loop);

    const ro = new ResizeObserver(onResize);
    ro.observe(canvas);
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      running = false;
      window.cancelAnimationFrame(raf);
      ro.disconnect();
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [reduced]);

  return <canvas ref={canvasRef} className={className} aria-hidden="true" role="presentation" />;
}
