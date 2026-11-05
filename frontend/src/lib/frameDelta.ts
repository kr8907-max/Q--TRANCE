
















export const MAX_FRAME_MS = 50;






export function frameDeltaMs(now: number, lastNow: number): number {
  const raw = now - lastNow;
  if (!Number.isFinite(raw) || raw < 0) return 0;
  return Math.min(MAX_FRAME_MS, raw);
}





export function advanceRadius(radius: number, rate: number, dt: number): number {
  const next = radius + rate * dt;
  return Number.isFinite(next) && next > 0 ? next : 0;
}
