
























import { useEffect, useRef } from "react";

const RGB = {
  accent: "76, 175, 119",
  accentHi: "126, 208, 155",
  slate: "91, 156, 196",
  teal: "78, 168, 160",
  faint: "113, 124, 112",
};

type Tone = keyof typeof RGB;

type PLayer = "ambient" | "flow" | "node" | "orbit";
interface P3 {
  x: number; y: number; z: number;
  vx: number; vy: number; vz: number;
  tone: Tone; ph: number;
  layer: PLayer; size: number;
  orbR: number; orbA: number; orbS: number; orbTilt: number;
  px: number; py: number;
}
interface Line3 { x: number; y: number; z: number; speed: number; len: number; tone: Tone; off: number; age: number; }
interface Node3 { ring: number; angle: number; speed: number; tone: Tone; }
interface Ripple { r: number; a: number; }


function hash(x: number, y: number, z: number): number {
  const s = Math.sin(x * 127.1 + y * 311.7 + z * 74.7) * 43758.5453;
  return s - Math.floor(s);
}
function smooth(t: number): number { return t * t * (3 - 2 * t); }
function vnoise(x: number, y: number, z: number): number {
  const xi = Math.floor(x), yi = Math.floor(y), zi = Math.floor(z);
  const xf = x - xi, yf = y - yi, zf = z - zi;
  const u = smooth(xf), v = smooth(yf), w = smooth(zf);
  function g(a: number, b: number, cc: number) { return hash(xi + a, yi + b, zi + cc) * 2 - 1; }
  function l(a: number, b: number, t2: number) { return a + (b - a) * t2; }
  const c000 = g(0, 0, 0), c100 = g(1, 0, 0), c010 = g(0, 1, 0), c110 = g(1, 1, 0);
  const c001 = g(0, 0, 1), c101 = g(1, 0, 1), c011 = g(0, 1, 1), c111 = g(1, 1, 1);
  return l(l(l(c000, c100, u), l(c010, c110, u), v), l(l(c001, c101, u), l(c011, c111, u), v), w);
}
function flowX(x: number, y: number, z: number, t: number): number { return vnoise(x * 1.4 + t * 0.05, y * 1.4, z * 1.4); }
function flowY(x: number, y: number, z: number, t: number): number { return vnoise(x * 1.4 + 31.4, y * 1.4 + t * 0.05, z * 1.4 + 17.2); }
function flowZ(x: number, y: number, z: number, t: number): number { return vnoise(x * 1.4 + 57.1, y * 1.4 + 11.7, z * 1.4 + t * 0.05); }

function useReduced(): boolean {
  return useRef(
    typeof window !== "undefined" &&
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  ).current;
}

interface SceneProps { progress: number; className?: string; }

export function FrontFieldScene({ progress, className }: SceneProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const pointer = useRef({ x: 0.5, y: 0.44, tx: 0.5, ty: 0.44 });
  const progressRef = useRef(progress);
  const reduced = useReduced();
  progressRef.current = progress;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return;

    let raf = 0;
    let running = true;
    let W = 0, H = 0;
    let parts: P3[] = [];
    let extentX = 2.4;
    let extentY = 1.6;
    let lines: Line3[] = [];
    let nodes: Node3[] = [];
    const ripples: Ripple[] = [];
    let t = 0;
    let lastNow = performance.now();
    let sp = 0;
    let nextRipple = 700;


    let camWX = 0, camWY = 0;
    let yaw = 0, pit = 0;

    let coreWX = 0, coreWY = 0, coreScale = 1;

    let quietX = 0, quietY = 0, quietR = 0;

    function seed() {
      const density = Math.max(0.7, Math.min(1.4, (W * H) / (1400 * 900)));
      const np = Math.round(380 * density);
      const nl = Math.round(150 * density);
      quietX = W * 0.5;
      quietY = H * 0.40;
      quietR = Math.min(W, H) * 0.30;

      parts = [];


      const fPlane = Math.min(W, H) * 0.92;
      extentX = Math.max(2.0, ((W * 0.5 * 3.7) / fPlane) * 1.3);
      extentY = Math.max(1.4, ((H * 0.56 * 3.7) / fPlane) * 1.3);
      const pick = (r: number) => (r < 0.14 ? "accent" : r < 0.28 ? "slate" : r < 0.38 ? "teal" : "faint") as Tone;
      const rp = () => Math.random() * 2 - 1;
      const rb = () => (Math.random() + Math.random() + Math.random()) / 1.5 - 1;
      for (let i = 0; i < np; i++) {
        const r = Math.random();
        const layer: PLayer = i % 29 === 0 ? "orbit" : i % 13 === 0 ? "node" : r < 0.5 ? "ambient" : "flow";
        const p: P3 = {
          x: rb() * extentX,
          y: rb() * extentY,
          z: rp() * 1.3 - 0.15,
          vx: 0, vy: 0, vz: 0,
          tone: pick(Math.random()),
          ph: Math.random() * Math.PI * 2,
          layer,
          size: 0.7 + Math.random() * 1.3,
          orbR: 0, orbA: 0, orbS: 0, orbTilt: 0,
          px: NaN, py: NaN,
        };
        if (layer === "orbit") {
          p.orbR = 0.55 + Math.random() * 0.55;
          p.orbA = Math.random() * Math.PI * 2;
          p.orbS = 0.02 + Math.random() * 0.05;
          p.orbTilt = Math.random() * Math.PI;
          p.tone = Math.random() < 0.5 ? "accent" : "teal";
          p.size = 1.0 + Math.random() * 0.8;
        }
        if (layer === "node") p.size = 1.6 + Math.random() * 1.0;
        parts.push(p);
      }

      lines = [];
      for (let i = 0; i < nl; i++) {
        lines.push({
          x: (Math.random() * 2 - 1) * extentX,
          y: (Math.random() * 2 - 1) * extentY,
          z: Math.random() * 2.4 - 1.4,
          speed: 0.85 + Math.random() * 0.4,
          len: 5 + Math.floor(Math.random() * 7),
          tone: Math.random() < 0.22 ? "accent" : "faint",
          off: Math.random() * 100,
          age: Math.random() * 90,
        });
      }

      nodes = [];
      for (let i = 0; i < 6; i++) {
        nodes.push({
          ring: i % 3,
          angle: Math.random() * Math.PI * 2,
          speed: (0.05 + Math.random() * 0.07) * (i % 2 === 0 ? 1 : -1),
          tone: i % 3 === 0 ? "accentHi" : i % 3 === 1 ? "slate" : "teal",
        });
      }
    }


    function project(x: number, y: number, z: number) {
      const xw = x - camWX, yw = y - camWY;
      const cosy = Math.cos(yaw), siny = Math.sin(yaw);
      const cosp = Math.cos(pit), sinp = Math.sin(pit);
      const x1 = xw * cosy + z * siny;
      const z1 = -xw * siny + z * cosy;
      const y1 = yw * cosp - z1 * sinp;
      const z2 = yw * sinp + z1 * cosp;
      const zp = z2 + 3.1;
      if (zp <= 0.2) return null;
      const f = Math.min(W, H) * 0.92;
      return { sx: W * 0.5 + (x1 * f) / zp, sy: H * 0.44 + (y1 * f) / zp, zp };
    }


    function quietFade(sx: number, sy: number): number {
      const d = Math.hypot(sx - quietX, sy - quietY);
      if (d >= quietR) return 1;
      const k = d / quietR;
      return 0.18 + 0.82 * k * k;
    }

    function frame(now: number) {
      if (!running || !ctx) return;
      const dtms = Math.min(50, now - lastNow);
      lastNow = now;
      const dt = dtms / 16.667;
      const motion = reduced ? 0 : 1;
      t += dt * motion;


      const pk = 1 - Math.exp(-dt * 3.0);
      pointer.current.x += (pointer.current.tx - pointer.current.x) * pk;
      pointer.current.y += (pointer.current.ty - pointer.current.y) * pk;


      const targetP = progressRef.current;
      if (reduced) sp = targetP;
      else sp += (targetP - sp) * (1 - Math.exp(-dt * 2.2));
      const ease = sp * sp * (3 - 2 * sp);
      const org = Math.min(1, Math.max(0, sp * 1.1));


      camWX = (pointer.current.x - 0.5) * 0.10;
      camWY = (pointer.current.y - 0.44) * 0.08 - ease * 0.30;
      yaw = t * 0.0016 + (pointer.current.x - 0.5) * 0.35 + ease * 0.22;
      pit = -0.14 + (pointer.current.y - 0.44) * 0.18 - ease * 0.05;


      coreWX = ease * 0.55;
      coreWY = ease * 0.80;
      coreScale = 1 + ease * 0.32;


      if (!reduced && t > nextRipple) {
        ripples.push({ r: 0, a: 1 });
        nextRipple = t + 700 + Math.random() * 900;
      }
      for (let i = ripples.length - 1; i >= 0; i--) {
        ripples[i].r += 0.004 * dt * motion;
        ripples[i].a *= Math.pow(0.992, dt);
        if (ripples[i].a < 0.02) ripples.splice(i, 1);
      }

      ctx.clearRect(0, 0, W, H);
      const coreC = project(coreWX, coreWY, 0);
      const f = Math.min(W, H) * 0.92;
      const coreScreenR = coreC ? (0.52 * coreScale * f) / coreC.zp : 120;


      if (coreC) {
        const haze = ctx.createRadialGradient(coreC.sx, coreC.sy, 0, coreC.sx, coreC.sy, coreScreenR * 2.1);
        haze.addColorStop(0, `rgba(${RGB.accent}, 0.09)`);
        haze.addColorStop(0.55, `rgba(${RGB.teal}, 0.035)`);
        haze.addColorStop(1, "rgba(0,0,0,0)");
        ctx.fillStyle = haze;
        ctx.beginPath();
        ctx.arc(coreC.sx, coreC.sy, coreScreenR * 2.1, 0, Math.PI * 2);
        ctx.fill();
      }


      ctx.lineWidth = 1;
      for (const ln of lines) {
        ln.age += dt;
        const fadeIn = Math.min(1, ln.age / 90);
        const step = 0.0034 * ln.speed * dt * motion;
        ln.x += flowX(ln.x, ln.y, ln.z, t * 0.015 + ln.off) * step;
        ln.y += flowY(ln.x, ln.y, ln.z, t * 0.015 + ln.off) * step;
        ln.z += flowZ(ln.x, ln.y, ln.z, t * 0.015 + ln.off) * step;
        for (const rp of ripples) {
          const d = Math.sqrt(ln.x * ln.x + ln.y * ln.y + ln.z * ln.z) + 1e-4;
          const band = Math.abs(d - rp.r * 1.6);
          if (band < 0.22) {
            const push = (1 - band / 0.22) * rp.a * 0.008 * dt * motion;
            ln.x += (ln.x / d) * push;
            ln.y += (ln.y / d) * push;
            ln.z += (ln.z / d) * push;
          }
        }
        if (Math.abs(ln.x) > extentX * 1.05 || Math.abs(ln.y) > extentY * 1.05 || ln.z < -1.55 || ln.z > 1.25) {
          ln.x = (Math.random() * 2 - 1) * extentX * 0.9;
          ln.y = (Math.random() * 2 - 1) * extentY * 0.9;
          ln.z = 1.0 + Math.random() * 0.2;
          ln.age = 0;
        }

        ctx.beginPath();
        let px = ln.x, py = ln.y, pz = ln.z;
        let first = true;
        let baseA = 0;
        let draw = false;
        for (let s = 0; s < ln.len; s++) {
          const q = project(px, py, pz);
          if (!q) break;
          let a = ln.tone === "accent" ? 0.10 : 0.045;
          if (coreC) {
            const dCore = Math.hypot(q.sx - coreC.sx, q.sy - coreC.sy);
            a += Math.max(0, 1 - Math.abs(dCore - coreScreenR * 1.1) / (coreScreenR * 1.1)) * 0.14;
          }
          a *= Math.max(0, 1 - (q.zp - 2.0) / 2.6) * quietFade(q.sx, q.sy) * fadeIn;
          a += org * 0.02;
          if (a > 0.012) draw = true;
          baseA = Math.max(baseA, a);
          if (first) { ctx.moveTo(q.sx, q.sy); first = false; } else ctx.lineTo(q.sx, q.sy);
          px += flowX(px, py, pz, t * 0.015 + ln.off) * 0.012;
          py += flowY(px, py, pz, t * 0.015 + ln.off) * 0.012;
          pz += flowZ(px, py, pz, t * 0.015 + ln.off) * 0.012;
        }
        if (draw) {
          ctx.strokeStyle = `rgba(${RGB[ln.tone]}, ${Math.min(0.38, baseA).toFixed(3)})`;
          ctx.stroke();
        }
      }






      const pScale = Math.min(W, H) * 0.92;
      for (const pt of parts) {
        if (pt.layer === "orbit") {

          pt.orbA += pt.orbS * dt * motion * 0.35;
          const ca = Math.cos(pt.orbA), sa = Math.sin(pt.orbA);
          const tilt = pt.orbTilt + ease * 0.5;
          pt.x = coreWX + ca * pt.orbR * coreScale;
          pt.z = sa * pt.orbR * coreScale * Math.cos(tilt);
          pt.y = coreWY + sa * pt.orbR * coreScale * Math.sin(tilt);
        } else {

          const ft = t * 0.012 + pt.ph;
          pt.vx += (flowX(pt.x, pt.y, pt.z, ft) * 0.0022 - pt.vx) * 0.03 * dt;
          pt.vy += (flowY(pt.x, pt.y, pt.z, ft) * 0.0022 - pt.vy) * 0.03 * dt;
          pt.vz += (flowZ(pt.x, pt.y, pt.z, ft) * 0.0022 - pt.vz) * 0.03 * dt;
          pt.x += pt.vx * dt * motion;
          pt.y += pt.vy * dt * motion;
          pt.z += pt.vz * dt * motion;

          pt.y += ease * 0.0008 * dt * motion;
          pt.x += (0 - pt.x) * 0.00018 * org * dt * motion;

          if (Math.abs(pt.x) > extentX || Math.abs(pt.y) > extentY || pt.z < -1.5 || pt.z > 1.2) {
            pt.x = (Math.random() * 2 - 1) * extentX * 0.9;
            pt.y = (Math.random() * 2 - 1) * extentY * 0.9;
            pt.z = 1.0 + Math.random() * 0.15;
            pt.vx = pt.vy = pt.vz = 0;
            pt.px = pt.py = NaN;
          }
        }

        const q = project(pt.x, pt.y, pt.z);
        if (!q) { pt.px = pt.py = NaN; continue; }
        if (q.sx < -30 || q.sx > W + 30 || q.sy < -30 || q.sy > H + 30) { pt.px = pt.py = NaN; continue; }
        const depth = Math.max(0.04, 1 - (q.zp - 2.0) / 2.6);
        const tw = 0.5 + 0.5 * Math.sin(t * 0.012 + pt.ph);
        let a = (pt.layer === "ambient" ? 0.05 : pt.layer === "flow" ? 0.10 : pt.layer === "node" ? 0.20 : 0.30)
          + 0.22 * tw;
        a *= depth * quietFade(q.sx, q.sy);
        if (pt.layer === "orbit") a *= 0.9 + org * 0.3;
        if (a < 0.012) { pt.px = pt.py = NaN; continue; }

        const sz = Math.max(0.4, ((pt.size * depth * pScale) / q.zp) * 0.012);


        if ((pt.layer === "flow" || pt.layer === "orbit") && !Number.isNaN(pt.px) && !reduced) {
          ctx.beginPath();
          ctx.moveTo(pt.px, pt.py);
          ctx.lineTo(q.sx, q.sy);
          ctx.strokeStyle = `rgba(${RGB[pt.tone]}, ${(a * 0.35).toFixed(3)})`;
          ctx.lineWidth = 1;
          ctx.stroke();
        }

        ctx.beginPath();
        ctx.arc(q.sx, q.sy, sz, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${RGB[pt.tone]}, ${Math.min(0.8, a).toFixed(3)})`;
        ctx.fill();

        pt.px = q.sx;
        pt.py = q.sy;
      }


      const breathe = 1 + Math.sin(t * 0.006) * 0.02;
      const ringR = [0.52, 0.72, 0.92];
      const ringTilt = [0.0, Math.PI / 3, (2 * Math.PI) / 3];
      const ringSpeed = [0.0030, -0.0020, 0.0025];
      const ringTone = [RGB.accent, RGB.slate, RGB.teal];

      function ringPoint(i: number, a: number) {
        const rr = ringR[i] * coreScale * breathe;
        const tilt = ringTilt[i] + t * ringSpeed[i] + ease * 0.35;
        const x0 = Math.cos(a) * rr;
        const z0 = Math.sin(a) * rr;
        const x1 = x0 * Math.cos(tilt);
        const y1 = x0 * Math.sin(tilt);
        return { x: coreWX + x1, y: coreWY + y1, z: z0 };
      }

      function drawRingSeg(i: number, back: boolean) {
        const c = ctx!;
        c.beginPath();
        let pen = false;
        const tone = ringTone[i];
        for (let s = 0; s <= 64; s++) {
          const a = (s / 64) * Math.PI * 2;
          const pt3 = ringPoint(i, a);
          const isBack = pt3.z > 0;
          if (isBack !== back) { pen = false; continue; }
          const q = project(pt3.x, pt3.y, pt3.z);
          if (!q) { pen = false; continue; }
          const alpha = back ? 0.10 - i * 0.02 : 0.32 - i * 0.05;
          if (!pen) { c.moveTo(q.sx, q.sy); pen = true; } else c.lineTo(q.sx, q.sy);
          c.strokeStyle = `rgba(${tone}, ${Math.max(0.04, alpha).toFixed(3)})`;
        }
        c.lineWidth = back ? 1 : 1.25;
        c.stroke();
      }


      for (let i = 0; i < 3; i++) drawRingSeg(i, true);


      if (coreC) {
        const nr = Math.max(2.5, ((0.05 * coreScale * breathe * (Math.min(W, H) * 0.92)) / coreC.zp));
        ctx.beginPath();
        ctx.arc(coreC.sx, coreC.sy, nr, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${RGB.accentHi}, 0.9)`;
        ctx.fill();
        ctx.beginPath();
        ctx.arc(coreC.sx, coreC.sy, nr + 4, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(${RGB.accent}, 0.32)`;
        ctx.lineWidth = 1;
        ctx.stroke();
      }


      for (let i = 0; i < 3; i++) drawRingSeg(i, false);


      for (const nd of nodes) {
        nd.angle += nd.speed * dt * motion;
        const pt3 = ringPoint(nd.ring, nd.angle);
        const q = project(pt3.x, pt3.y, pt3.z);
        if (!q) continue;
        const nr = Math.max(1.2, ((0.02 * coreScale * (Math.min(W, H) * 0.92)) / q.zp));
        const nodeAlpha = pt3.z > 0 ? 0.4 : 0.9;
        ctx.beginPath();
        ctx.arc(q.sx, q.sy, nr, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${RGB[nd.tone]}, ${nodeAlpha})`;
        ctx.fill();
      }
    }

    function loop(now: number) {
      frame(now);
      if (!reduced) raf = window.requestAnimationFrame(loop);
    }

    function onPointer(e: PointerEvent) {
      pointer.current.tx = e.clientX / Math.max(1, window.innerWidth);
      pointer.current.ty = e.clientY / Math.max(1, window.innerHeight);
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
    window.addEventListener("pointermove", onPointer, { passive: true });
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      running = false;
      window.cancelAnimationFrame(raf);
      ro.disconnect();
      window.removeEventListener("pointermove", onPointer);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [reduced]);

  return <canvas ref={canvasRef} className={className} aria-hidden="true" role="presentation" />;
}
