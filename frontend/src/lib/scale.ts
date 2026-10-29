/**
 * The two sliders that set how much: coverage of the plantable ground and budget. They are one
 * quantity related by the cost table, so locked they move together; unlocked, the one moved last
 * is what the surrogate is asked with and the other stays where it was left.
 */

import type { ScenarioLevers } from "@/api/client";
import type { ScenarioOutcome } from "@/api/models";

export const COVERAGE = { min: 0.005, max: 0.3, step: 0.005 };
export const BUDGET = { min: 250_000, max: 25_000_000, step: 250_000 };

export type Driver = "coverage" | "budget";

export interface Scale {
  locked: boolean;
  driver: Driver;
  coverage: number;
  budget: number;
}

export const INITIAL_SCALE: Scale = { locked: true, driver: "coverage", coverage: 0.05, budget: 5_000_000 };

/** USD for all of the plantable ground, read off an answer: what ties the two sliders together. */
export function rateOf(outcome: ScenarioOutcome | undefined): number | null {
  if (!outcome || outcome.coverage <= 0) return null;
  return outcome.cost_usd / outcome.coverage;
}

export function moveCoverage(scale: Scale, coverage: number, rate: number | null): Scale {
  const budget = scale.locked && rate ? clamp(coverage * rate, BUDGET) : scale.budget;
  return { ...scale, driver: "coverage", coverage, budget };
}

export function moveBudget(scale: Scale, budget: number, rate: number | null): Scale {
  const coverage = scale.locked && rate ? clamp(budget / rate, COVERAGE) : scale.coverage;
  return { ...scale, driver: "budget", budget, coverage };
}

/** Locking brings the follower back in line with the driver; unlocking leaves both where they are. */
export function setLocked(scale: Scale, locked: boolean, rate: number | null): Scale {
  const changed = { ...scale, locked };
  if (!locked || rate === null) return changed;
  return scale.driver === "coverage" ? moveCoverage(changed, scale.coverage, rate) : moveBudget(changed, scale.budget, rate);
}

/**
 * The follower as an answer to the current driver value sets it, which is exact where the rate was a
 * guess. An answer to an earlier value, still showing while a slider moves, changes nothing.
 */
export function alignToAnswer(scale: Scale, outcome: ScenarioOutcome): Scale {
  if (!scale.locked) return scale;
  if (scale.driver === "coverage") {
    const answered = Math.abs(outcome.coverage - scale.coverage) <= COVERAGE.step / 2;
    return answered ? { ...scale, budget: clamp(outcome.cost_usd, BUDGET) } : scale;
  }
  const answered = outcome.cost_usd <= scale.budget && scale.budget - outcome.cost_usd <= scale.budget * 0.02;
  return answered ? { ...scale, coverage: clamp(outcome.coverage, COVERAGE) } : scale;
}

export function leversOf(design: string, scale: Scale): ScenarioLevers {
  if (scale.driver === "coverage") return { arrangement: design, coverage: Number(scale.coverage.toFixed(3)) };
  return { arrangement: design, budget_usd: Math.round(scale.budget) };
}

function clamp(value: number, range: { min: number; max: number }): number {
  return Math.min(range.max, Math.max(range.min, value));
}
