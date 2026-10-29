import { INITIAL_SCALE, alignToAnswer, leversOf, moveBudget, moveCoverage, rateOf, setLocked } from "./scale";

const RATE = 60_000_000; // USD for all of the plantable ground

describe("the two sliders", () => {
  it("move together when locked, through the rate", () => {
    const moved = moveCoverage(INITIAL_SCALE, 0.1, RATE);
    expect(moved).toMatchObject({ driver: "coverage", coverage: 0.1, budget: 6_000_000 });
    const back = moveBudget(moved, 3_000_000, RATE);
    expect(back).toMatchObject({ driver: "budget", coverage: 0.05, budget: 3_000_000 });
  });

  it("leave the other where it was when unlocked, and the moved one drives", () => {
    const unlocked = setLocked(INITIAL_SCALE, false, RATE);
    const moved = moveBudget(unlocked, 1_000_000, RATE);
    expect(moved).toMatchObject({ locked: false, driver: "budget", budget: 1_000_000, coverage: 0.05 });
    expect(leversOf("corridor", moved)).toEqual({ arrangement: "corridor", budget_usd: 1_000_000 });
    expect(leversOf("corridor", INITIAL_SCALE)).toEqual({ arrangement: "corridor", coverage: 0.05 });
  });

  it("realign on locking and take the answer's own value for the follower", () => {
    const apart = moveBudget(setLocked(INITIAL_SCALE, false, RATE), 12_000_000, RATE);
    expect(setLocked(apart, true, RATE).coverage).toBe(0.2);
    const answered = alignToAnswer(INITIAL_SCALE, { coverage: 0.05, cost_usd: 2_980_000 } as never);
    expect(answered.budget).toBe(2_980_000);
    const stale = alignToAnswer(INITIAL_SCALE, { coverage: 0.1, cost_usd: 5_960_000 } as never);
    expect(stale.budget).toBe(INITIAL_SCALE.budget);
    const byBudget = moveBudget(INITIAL_SCALE, 3_000_000, RATE);
    expect(alignToAnswer(byBudget, { coverage: 0.0497, cost_usd: 2_980_000 } as never).coverage).toBe(0.0497);
  });

  it("clamp the follower to its slider and read the rate off an answer", () => {
    expect(moveBudget(INITIAL_SCALE, 25_000_000, RATE).coverage).toBe(0.3);
    expect(rateOf({ coverage: 0.05, cost_usd: 3_000_000 } as never)).toBe(60_000_000);
    expect(rateOf(undefined)).toBeNull();
  });
});
