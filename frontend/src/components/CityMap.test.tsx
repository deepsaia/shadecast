import { act, render, screen } from "@testing-library/react";

import { FakeMap, fakeMaplibre } from "@/test/fake_maplibre";

import { CityMap } from "./CityMap";
import type { Cell } from "@/lib/tile_grid";

vi.mock("maplibre-gl", () => ({ default: fakeMaplibre, ...fakeMaplibre }));
vi.mock("maplibre-gl/dist/maplibre-gl.css", () => ({}));

const cell = (id: string, west: number, modelled: boolean): Cell => ({
  id,
  west,
  south: 23.13,
  east: west + 0.01,
  north: 23.139,
  density: modelled ? 9000 : 1000,
  residents: modelled ? 9000 : 1000,
  modelled,
});
const CELLS = [cell("a", 72.57, true), cell("b", 72.58, false)];

beforeEach(() => {
  FakeMap.instances.length = 0;
});

it("hands the grid to the map, outlines the chosen and focused tiles and fits the city", async () => {
  render(<CityMap style="https://example.test/style" cells={CELLS} chosen={["a"]} focused="a" zoom="city" onPick={() => undefined} />);
  await act(async () => {});
  const map = FakeMap.instances[0];
  expect(map.layers).toEqual(["grid-fill", "grid-line", "grid-modelled", "grid-chosen", "grid-focused"]);
  expect((map.getSource("grid")?.data as { features: unknown[] }).features).toHaveLength(2);
  expect(map.filters.get("grid-chosen")).toEqual(["in", ["get", "id"], ["literal", ["a"]]]);
  expect(map.filters.get("grid-focused")).toEqual(["==", ["get", "id"], "a"]);
  expect(map.options).toMatchObject({ style: "https://example.test/style" });
  expect(map.fitted).toHaveLength(1);
  expect(map.fitted[0]).toMatchObject({ bounds: [[72.57, 23.13], [72.59, 23.139]] });
});

it("zooms to the focused tile, reads a hovered tile, and picks only a tile with a model", async () => {
  const picked: string[] = [];
  const { rerender } = render(
    <CityMap style="https://example.test/style" cells={CELLS} chosen={["a"]} focused="a" zoom="tile" onPick={(id) => picked.push(id)} />,
  );
  await act(async () => {});
  const map = FakeMap.instances[0];
  expect(map.fitted[0]).toMatchObject({ bounds: [[72.57, 23.13], [72.58, 23.139]] });
  act(() => map.fire("mousemove:grid-fill", { features: [{ properties: CELLS[1] }] }));
  expect(screen.getByText("b, 1,000 residents, no model yet")).toBeInTheDocument();
  act(() => map.fire("click:grid-fill", { features: [{ properties: CELLS[1] }] }));
  act(() => map.fire("click:grid-fill", { features: [{ properties: CELLS[0] }] }));
  expect(picked).toEqual(["a"]);
  rerender(
    <CityMap
      style="https://example.test/style"
      cells={CELLS}
      chosen={["a"]}
      focused="a"
      zoom="tile"
      overlay={{ url: "data:,", bounds: [[72.57, 23.13], [72.58, 23.139]] }}
      onPick={() => undefined}
    />,
  );
  expect(map.layers).toContain("cooling");
});
