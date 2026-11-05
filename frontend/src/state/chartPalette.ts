






export interface ChartPalette {
  grid: string;
  axis: string;
  tick: string;
  tooltipBg: string;
  tooltipBorder: string;
  cursor: string;
  ref: string;
  accent: string;
  slate: string;
  ok: string;
  warn: string;
  danger: string;
  info: string;
  textHi: string;
}

const DARK_CHART_PALETTE: ChartPalette = {
  grid: "rgba(255, 255, 255, 0.08)",
  axis: "#717c70",
  tick: "#97a296",
  tooltipBg: "#1d221c",
  tooltipBorder: "rgba(255, 255, 255, 0.16)",
  cursor: "rgba(255, 255, 255, 0.06)",
  ref: "rgba(255, 255, 255, 0.28)",
  accent: "#4caf77",
  slate: "#5b9cc4",
  ok: "#4caf77",
  warn: "#d9a441",
  danger: "#e0735f",
  info: "#5b9cc4",
  textHi: "#eaf0e9",
};


export function useChartPalette(): ChartPalette {
  return DARK_CHART_PALETTE;
}
