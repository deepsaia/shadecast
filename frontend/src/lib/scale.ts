/**
 * The two sliders that set how much: coverage of the plantable ground and budget. They are one
 * quantity related by the cost table, so locked they move together; unlocked, the one moved last
 * is what the surrogate is asked with and the other stays where it was left.
 */

import type { ScenarioLevers } from "@/api/client";
import type { ScenarioOutcome } from "@/api/models";

export interface Range {
  min: number;
  max: number;
  step: number;
}

export const COVERAGE: Range = { min: 0.005, max: 1, step: 0.005 };
/** The budget slider before any answer tells the rate; after one it runs to what the whole ground costs. */
export const BUDGET: Range = { min: 250_000, max: 25_000_000, step: 250_000 };
/** The coverage the designs were simulated up to; past it the surrogate extrapolates. */
export const SIMULATED_COVERAGE = 0.3;

/** The budget slider's range: up to what all of the plantable ground costs, in two hundred steps. */
export function budgetRange(rate: number | null): Range {
  if (rate === null) return BUDGET;
  const step = niceStep(rate / 200);
  return { min: step, max: Math.ceil(rate / step) * step, step };
}

/** The budget that buys the simulated coverage, where the red mark on the budget slider sits. */
export function simulatedBudget(rate: number | null): number | null {
  return rate === null ? null : rate * SIMULATED_COVERAGE;
}

/** True when the scale asks beyond the coverage the designs reached, by either slider. */
export function extrapolating(scale: Scale, rate: number | null): boolean {
  if (scale.driver === "coverage") return scale.coverage > SIMULATED_COVERAGE + 1e-9;
  const limit = simulatedBudget(rate);
  return limit !== null && scale.budget > limit + 1e-6;
}

function niceStep(rough: number): number {
  const magnitude = 10 ** Math.floor(Math.log10(rough));
  const unit = rough / magnitude;
  const nice = unit <= 1 ? 1 : unit <= 2 ? 2 : unit <= 5 ? 5 : 10;
  return nice * magnitude;
}

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
  const budget = scale.locked && rate ? clamp(coverage * rate, budgetRange(rate)) : scale.budget;
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
    return answered ? { ...scale, budget: clamp(outcome.cost_usd, budgetRange(rateOf(outcome))) } : scale;
  }
  const answered = outcome.cost_usd <= scale.budget && scale.budget - outcome.cost_usd <= scale.budget * 0.02;
  return answered ? { ...scale, coverage: clamp(outcome.coverage, COVERAGE) } : scale;
}

export function leversOf(design: string, scale: Scale): ScenarioLevers {
  if (scale.driver === "coverage") return { arrangement: design, coverage: Number(scale.coverage.toFixed(3)) };
  return { arrangement: design, budget_usd: Math.round(scale.budget) };
}

function clamp(value: number, range: Range): number {
  return Math.min(range.max, Math.max(range.min, value));
}
