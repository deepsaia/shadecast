import { act, renderHook } from "@testing-library/react";

import { useDebounced } from "./debounce";

describe("useDebounced", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("holds the last value until it has stopped changing for the delay", () => {
    const { result, rerender } = renderHook(({ value }) => useDebounced(value, 200), { initialProps: { value: 1 } });
    expect(result.current).toBe(1);
    rerender({ value: 2 });
    act(() => vi.advanceTimersByTime(150));
    rerender({ value: 3 });
    act(() => vi.advanceTimersByTime(150));
    expect(result.current).toBe(1);
    act(() => vi.advanceTimersByTime(60));
    expect(result.current).toBe(3);
  });
});
