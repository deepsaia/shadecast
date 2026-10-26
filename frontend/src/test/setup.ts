import "@testing-library/jest-dom/vitest";

// jsdom has no 2D canvas; the canvas component paints only when a context exists.
HTMLCanvasElement.prototype.getContext = () => null;

// jsdom has no ResizeObserver; the chart container measures itself with one.
class StillResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = StillResizeObserver as unknown as typeof ResizeObserver;
