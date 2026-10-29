import type { TileGrid } from "@/api/models";

import { cellsOf, densityCeiling, densityColor, gridBounds, gridFeatures, thumbnail } from "./tile_grid";

const GRID: TileGrid = {
  columns: ["west", "south", "east", "north", "density_per_km2", "residents", "modelled"],
  ids: ["a", "b", "c"],
  cells: [
    [72.57, 23.13, 72.58, 23.139, 9000, 9000, 1],
    [72.58, 23.13, 72.59, 23.139, 3000, 3000, 0],
    [72.57, 23.139, 72.58, 23.148, 1000, 1000, 0],
  ],
  described: 4,
};

it("turns the parallel lists into cells with the model flag", () => {
  const cells = cellsOf(GRID);
  expect(cells).toHaveLength(3);
  expect(cells[0]).toMatchObject({ id: "a", west: 72.57, north: 23.139, density: 9000, modelled: true });
  expect(cells[1].modelled).toBe(false);
  expect(gridBounds(cells)).toEqual([
    [72.57, 23.13],
    [72.59, 23.148],
  ]);
  expect(gridBounds([])).toBeNull();
});

it("draws polygons closed on their first corner and shades by density up to a ceiling", () => {
  const cells = cellsOf(GRID);
  const features = gridFeatures(cells);
  expect(features.features[0].geometry.coordinates[0]).toHaveLength(5);
  expect(features.features[0].properties.id).toBe("a");
  const ceiling = densityCeiling(cells);
  expect(ceiling).toBe(9000);
  expect(densityColor(0, ceiling)).toBe("#e4eae7");
  expect(densityColor(ceiling, ceiling)).toBe("#1b2b34");
});

it("fits the grid into a square thumbnail with the modelled cell marked", () => {
  const drawn = thumbnail(cellsOf(GRID), 96);
  expect(drawn.width).toBeCloseTo(96, 0);
  expect(drawn.rects).toHaveLength(3);
  expect(drawn.rects.filter((rect) => rect.modelled)).toHaveLength(1);
  expect(drawn.rects[2].y).toBe(0);
  expect(thumbnail([], 96).rects).toEqual([]);
});
