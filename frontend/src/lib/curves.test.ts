import type { Sweep } from "@/api/models";

import { curveRows, designPoints, thresholdIndex, valueOf } from "./curves";

const point = (drop: number, people: number[]) => ({
  exposure_drop: drop,
  equity_gap_change: -0.1,
  excess_removed: people.map((count) => count * 10),
  people,
});

const SWEEP: Sweep = {
  model_id: "m",
  created: "2026-10-29T12:00:00+00:00",
  coverages: [0.05, 0.3],
  thresholds: [45, 49],
  curves: [
    { arrangement: "clustered", points: [point(0.5, [0, 100]), point(2, [0, 400])] },
    { arrangement: "scattered", points: [point(1.5, [0, 200]), point(4, [0, 800])] },
  ],
  designs: [{ id: "clustered_0105", arrangement: "clustered", coverage: 0.052, point: point(0.6, [0, 120]) }],
  seconds: 20,
  fresh: true,
};

it("picks the nearest threshold row and reads a point at it", () => {
  expect(thresholdIndex(SWEEP, 45)).toBe(0);
  expect(thresholdIndex(SWEEP, 48)).toBe(1);
  expect(valueOf(SWEEP.curves[1].points[1], "people", 1)).toBe(800);
  expect(valueOf(SWEEP.curves[1].points[1], "exposure_drop", 1)).toBe(4);
});

it("lays the curves out one row per coverage with a value per arrangement, and the designs on the same axes", () => {
  expect(curveRows(SWEEP, "exposure_drop", 0)).toEqual([
    { coverage: 5, clustered: 0.5, scattered: 1.5 },
    { coverage: 30, clustered: 2, scattered: 4 },
  ]);
  expect(curveRows(SWEEP, "people", 1)[1]).toEqual({ coverage: 30, clustered: 400, scattered: 800 });
  expect(designPoints(SWEEP, "excess_removed", 1)).toEqual([
    { id: "clustered_0105", arrangement: "clustered", coverage: 5.2, value: 1200 },
  ]);
});
