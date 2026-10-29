import type { TileSummary } from "@/api/models";

import { applyPreset } from "./tile_presets";

const tile = (id: string, density: number, model: boolean): TileSummary =>
  ({ id, density_2020_per_km2: density, stages: { bundle: true, baseline: model, physics: model, model, results: false } }) as TileSummary;

const TILES = [tile("a", 10, true), tile("b", 40, true), tile("c", 30, false), tile("d", 20, true), tile("e", 5, true)];

it("picks among the tiles with a model, densest first", () => {
  expect(applyPreset("densest", TILES)).toEqual(["b"]);
  expect(applyPreset("densest 3", TILES)).toEqual(["b", "d", "a"]);
  expect(applyPreset("sparsest 3", TILES)).toEqual(["e", "a", "d"]);
  expect(applyPreset("all with a model", TILES)).toEqual(["b", "d", "a", "e"]);
  expect(applyPreset("densest", [tile("c", 30, false)])).toEqual([]);
});
