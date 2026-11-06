import { fitAxis, niceTicks } from "./axis";

describe("niceTicks", () => {
  it("contain the whole range on round stops, with zero among them", () => {
    expect(niceTicks(0.187, 12.66)).toEqual([0, 5, 10, 15]);
    expect(niceTicks(9786, 651046)).toEqual([0, 200000, 400000, 600000, 800000]);
    expect(niceTicks(385, 77725)).toEqual([0, 20000, 40000, 60000, 80000]);
  });

  it("reach below zero when a value does, on stops with a clean decimal", () => {
    expect(niceTicks(-6.855, 1.633)).toEqual([-7.5, -5, -2.5, 0, 2.5]);
    expect(niceTicks(-0.41, 0.311)).toEqual([-0.6, -0.4, -0.2, 0, 0.2, 0.4]);
  });

  it("still give two stops when every value is zero", () => {
    expect(niceTicks(0, 0)).toEqual([0, 0.25]);
  });
});

describe("fitAxis", () => {
  it("spans the stops and asks the width the longest label needs", () => {
    const fit = fitAxis([0.5, 12.66, 7.9], (value) => value.toFixed(2));
    expect(fit.domain).toEqual([0, 15]);
    expect(fit.ticks).toEqual([0, 5, 10, 15]);
    expect(fit.width).toBe("15.00".length * 6 + 8);
  });

  it("ignores values that are not finite and falls back to the zero stops", () => {
    expect(fitAxis([Number.NaN], String).domain).toEqual([0, 0.25]);
  });
});
