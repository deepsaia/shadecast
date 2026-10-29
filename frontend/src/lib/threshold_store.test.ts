import { DEFAULT_THRESHOLD, readThreshold, storeThreshold } from "./threshold_store";

beforeEach(() => window.localStorage.clear());

it("falls back to the project's line and keeps a chosen one within the slider's range", () => {
  expect(readThreshold()).toBe(DEFAULT_THRESHOLD);
  storeThreshold(52);
  expect(readThreshold()).toBe(52);
  window.localStorage.setItem("shadecast.threshold", "900");
  expect(readThreshold()).toBe(DEFAULT_THRESHOLD);
  window.localStorage.setItem("shadecast.threshold", "warm");
  expect(readThreshold()).toBe(DEFAULT_THRESHOLD);
});
