import { COOL, HEAT, extent, paint, paintMask, ramp, readout } from "./ramp";

it("interpolates between stops and clamps outside them", () => {
  expect(ramp(HEAT, 0)).toEqual(HEAT[0]);
  expect(ramp(HEAT, 1)).toEqual(HEAT[HEAT.length - 1]);
  expect(ramp(COOL, -1)).toEqual(COOL[0]);
  expect(ramp(HEAT, 0.5)).toEqual(HEAT[2]);
});

it("measures the finite extent and widens a flat field", () => {
  expect(extent([3, NaN, 1, 2])).toEqual({ min: 1, max: 3 });
  expect(extent([5, 5])).toEqual({ min: 5, max: 6 });
  expect(extent([NaN])).toEqual({ min: 0, max: 1 });
});

it("paints values through the ramp and leaves gaps transparent", () => {
  const out = new Uint8ClampedArray(3 * 4);
  paint([0, NaN, 10], { min: 0, max: 10 }, HEAT, out);
  expect(Array.from(out.subarray(0, 4))).toEqual([...HEAT[0], 255]);
  expect(out[7]).toBe(0);
  expect(Array.from(out.subarray(8, 12))).toEqual([...HEAT[4], 255]);
});

it("paints a mask as one color on transparency", () => {
  const out = new Uint8ClampedArray(2 * 4);
  paintMask([0, 1], [1, 2, 3], out);
  expect(out[3]).toBe(0);
  expect(Array.from(out.subarray(4, 8))).toEqual([1, 2, 3, 255]);
});

it("never reads minus zero", () => {
  expect(readout(-0.01, " C")).toBe("0.0 C");
  expect(readout(34.96, " C")).toBe("35.0 C");
});
