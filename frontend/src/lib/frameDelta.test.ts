










import { describe, expect, it } from "vitest";
import { advanceRadius, frameDeltaMs, MAX_FRAME_MS } from "./frameDelta";

describe("frameDeltaMs", () => {
  it("passes a normal frame interval through", () => {
    expect(frameDeltaMs(1016.7, 1000)).toBeCloseTo(16.7, 5);
  });

  it("clamps a negative clock difference to a zero-motion frame", () => {


    expect(frameDeltaMs(999.2, 1000)).toBe(0);
  });

  it("caps a long hidden-tab gap at MAX_FRAME_MS", () => {
    expect(frameDeltaMs(60_000, 1_000)).toBe(MAX_FRAME_MS);
  });

  it("returns 0 for non-finite input instead of propagating NaN", () => {
    expect(frameDeltaMs(Number.NaN, 1000)).toBe(0);
    expect(frameDeltaMs(1000, Number.POSITIVE_INFINITY)).toBe(0);
  });

  it("a zero-length frame is allowed and moves nothing", () => {
    expect(frameDeltaMs(1000, 1000)).toBe(0);
  });
});

describe("advanceRadius", () => {
  it("grows the radius under a normal frame", () => {
    expect(advanceRadius(0, 2.1, 1)).toBeCloseTo(2.1, 10);
  });

  it("can never return a negative radius for canvas arc()", () => {



    let r = 0;
    let last = 500;
    for (let i = 0; i < 10_000; i++) {

      const now = i % 3 === 0 ? last - Math.random() * 8 : last + Math.random() * 40;
      const dt = frameDeltaMs(now, last) / 16.667;
      r = advanceRadius(r, 2.1, dt);
      expect(Number.isFinite(r)).toBe(true);
      expect(r).toBeGreaterThanOrEqual(0);
      last = now;
    }
  });
});
