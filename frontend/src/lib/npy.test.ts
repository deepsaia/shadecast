import { encodeNpy as encode } from "@/test/npy_writer";

import { band, parseNpy } from "./npy";

it("reads a float stack hours first and slices one band without copying", () => {
  const array = parseNpy(encode([1, 2, 3, 4, 5, 6, 7, 8], [2, 2, 2], "<f4"));
  expect(array.shape).toEqual([2, 2, 2]);
  expect(array.dtype).toBe("<f4");
  expect(Array.from(band(array, 1))).toEqual([5, 6, 7, 8]);
});

it("reads a placement mask as bytes", () => {
  const mask = parseNpy(encode([0, 1, 1, 0], [2, 2], "|b1"));
  expect(mask.data).toBeInstanceOf(Uint8Array);
  expect(Array.from(mask.data)).toEqual([0, 1, 1, 0]);
});

it("refuses what is not an array", () => {
  expect(() => parseNpy(new TextEncoder().encode("hello").buffer as ArrayBuffer)).toThrow("not an NPY array");
});
