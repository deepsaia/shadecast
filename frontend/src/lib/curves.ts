/** The sweep shaped for charts: one row per coverage with a value per arrangement, at the threshold chosen. */

import type { Sweep, SweepPoint } from "@/api/models";

export type CurveKey = "exposure_drop" | "excess_removed" | "people" | "equity_gap_change";

export interface Curve {
  key: CurveKey;
  label: string;
  unit: string;
}

export const CURVES: Curve[] = [
  { key: "exposure_drop", label: "Exposure drop", unit: "C" },
  { key: "excess_removed", label: "Degree-hours removed", unit: "" },
  { key: "people", label: "People moved below the threshold", unit: "" },
  { key: "equity_gap_change", label: "Equity gap change", unit: "C" },
];

/** The row of the threshold table nearest the threshold a person chose. */
export function thresholdIndex(sweep: Sweep, threshold: number): number {
  let best = 0;
  sweep.thresholds.forEach((value, index) => {
    if (Math.abs(value - threshold) < Math.abs(sweep.thresholds[best] - threshold)) best = index;
  });
  return best;
}

export function valueOf(point: SweepPoint, key: CurveKey, index: number): number {
  if (key === "excess_removed" || key === "people") return point[key][index] ?? 0;
  return point[key];
}

export interface CurveRow {
  coverage: number; // percent of the plantable ground
  [arrangement: string]: number;
}

export function curveRows(sweep: Sweep, key: CurveKey, index: number): CurveRow[] {
  return sweep.coverages.map((coverage, at) => {
    const row: CurveRow = { coverage: Math.round(coverage * 1000) / 10 };
    for (const curve of sweep.curves) row[curve.arrangement] = valueOf(curve.points[at], key, index);
    return row;
  });
}

export interface DesignPoint {
  id: string;
  arrangement: string;
  coverage: number; // percent
  value: number;
}

export function designPoints(sweep: Sweep, key: CurveKey, index: number): DesignPoint[] {
  return sweep.designs.map((design) => ({
    id: design.id,
    arrangement: design.arrangement,
    coverage: Math.round(design.coverage * 1000) / 10,
    value: valueOf(design.point, key, index),
  }));
}
