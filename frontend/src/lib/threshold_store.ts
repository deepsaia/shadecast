/** The stress threshold a person chose, kept in this browser so a reload shows the same picture. */

export const DEFAULT_THRESHOLD = 45;
export const THRESHOLD = { min: 30, max: 70, step: 1 };
const KEY = "shadecast.threshold";

export function readThreshold(): number {
  try {
    const stored = Number(window.localStorage.getItem(KEY));
    if (Number.isFinite(stored) && stored >= THRESHOLD.min && stored <= THRESHOLD.max) return stored;
  } catch {
    // storage may be blocked or absent; the default stands
  }
  return DEFAULT_THRESHOLD;
}

export function storeThreshold(value: number): void {
  try {
    window.localStorage.setItem(KEY, String(value));
  } catch {
    // storage may be blocked or absent; the page still works for this visit
  }
}
