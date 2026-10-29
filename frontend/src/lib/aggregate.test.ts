import type { ScenarioOutcome } from "@/api/models";

import { aggregate } from "./aggregate";

const outcome = (tile: string, drop: number, cost: number, excess: number): ScenarioOutcome =>
  ({
    tile,
    trees: 10,
    cost_usd: cost,
    excess_removed: excess,
    people: 5,
    baseline_at_risk: 100,
    exposure_drop: drop,
    equity_gap_change: -0.1,
    baseline_exposure: 50,
    surrogate_seconds: 0.5,
  }) as ScenarioOutcome;

it("sums what adds up and weights the rest by residents", () => {
  const totals = aggregate([outcome("a", 1, 1000, 300), outcome("b", 3, 3000, 100)], { a: 100, b: 300 });
  expect(totals).toMatchObject({ tiles: 2, trees: 20, cost_usd: 4000, excess_removed: 400, people: 10 });
  expect(totals.exposure_drop).toBe(2.5);
  expect(totals.efficiency).toBe(100);
  expect(aggregate([], {}).tiles).toBe(0);
});
