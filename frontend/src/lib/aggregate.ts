import type { ScenarioOutcome } from "@/api/models";

/** Outcomes over several tiles: sums where the quantity adds up, resident-weighted means where it does not. */
export interface Totals {
  tiles: number;
  trees: number;
  cost_usd: number;
  excess_removed: number;
  people: number;
  baseline_at_risk: number;
  exposure_drop: number;
  equity_gap_change: number;
  baseline_exposure: number;
  efficiency: number;
  surrogate_seconds: number;
}

export function aggregate(outcomes: ScenarioOutcome[], residents: Record<string, number>): Totals {
  const weight = (outcome: ScenarioOutcome) => residents[outcome.tile] ?? 1;
  const weights = sum(outcomes.map(weight)) || 1;
  const mean = (pick: (outcome: ScenarioOutcome) => number) =>
    sum(outcomes.map((outcome) => pick(outcome) * weight(outcome))) / weights;
  const cost = sum(outcomes.map((outcome) => outcome.cost_usd));
  const excess = sum(outcomes.map((outcome) => outcome.excess_removed));
  return {
    tiles: outcomes.length,
    trees: sum(outcomes.map((outcome) => outcome.trees)),
    cost_usd: cost,
    excess_removed: excess,
    people: sum(outcomes.map((outcome) => outcome.people)),
    baseline_at_risk: sum(outcomes.map((outcome) => outcome.baseline_at_risk)),
    exposure_drop: mean((outcome) => outcome.exposure_drop),
    equity_gap_change: mean((outcome) => outcome.equity_gap_change),
    baseline_exposure: mean((outcome) => outcome.baseline_exposure),
    efficiency: cost > 0 ? excess / (cost / 1000) : 0,
    surrogate_seconds: sum(outcomes.map((outcome) => outcome.surrogate_seconds)),
  };
}

function sum(values: number[]): number {
  return values.reduce((total, value) => total + value, 0);
}
