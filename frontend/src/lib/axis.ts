/**
 * Axis stops fitted to the values a chart draws, so no curve leaves the plot and no label is cropped.
 * Recharts fits an axis to the data of any series that carries its own, dropping the chart's rows, so a
 * chart that mixes the two fits its axis here and hands Recharts the result.
 */

const NICE_STEPS = [1, 2, 2.5, 5, 10];
const PX_PER_CHAR = 6; // tabular digits at the charts' 10 px type
const TICK_MARGIN = 8;
const TICK_COUNT = 5;

export interface AxisFit {
  domain: [number, number];
  ticks: number[];
  width: number; // px a vertical axis needs for its labels
}

/** Round stops from at or below `low` to at or above `high`, about five of them, zero always among them. */
export function niceTicks(low: number, high: number): number[] {
  const floor = Math.min(0, low);
  const ceiling = Math.max(0, high);
  const span = ceiling - floor || 1;
  const rough = span / (TICK_COUNT - 1);
  const magnitude = 10 ** Math.floor(Math.log10(rough));
  const nice = NICE_STEPS.find((candidate) => candidate * magnitude >= rough) ?? 10;
  const step = nice * magnitude;
  const decimals = Math.max(0, -Math.floor(Math.log10(magnitude))) + (nice === 2.5 ? 1 : 0);
  const first = Math.floor(floor / step) * step;
  const last = Math.max(Math.ceil(ceiling / step) * step, first + step);
  const count = Math.round((last - first) / step) + 1;
  return Array.from({ length: count }, (_, at) => Number((first + at * step).toFixed(decimals)) + 0);
}

/** The domain, the stops and the label width that hold every finite value, labelled with `format`. */
export function fitAxis(values: number[], format: (value: number) => string): AxisFit {
  const finite = values.filter((value) => Number.isFinite(value));
  const ticks = finite.length > 0 ? niceTicks(Math.min(...finite), Math.max(...finite)) : niceTicks(0, 0);
  const longest = Math.max(...ticks.map((tick) => format(tick).length));
  return { domain: [ticks[0], ticks[ticks.length - 1]], ticks, width: longest * PX_PER_CHAR + TICK_MARGIN };
}
