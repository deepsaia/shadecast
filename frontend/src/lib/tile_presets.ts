import type { TileSummary } from "@/api/models";

/** The ways to pick tiles without naming them; density decides the order, and only modelled tiles count. */
export const PRESETS = ["densest", "densest 3", "sparsest 3", "all with a model"] as const;
export type Preset = (typeof PRESETS)[number];

export function applyPreset(preset: Preset, tiles: TileSummary[]): string[] {
  const modelled = tiles
    .filter((tile) => tile.stages.model)
    .sort((a, b) => (b.density_2020_per_km2 ?? 0) - (a.density_2020_per_km2 ?? 0));
  switch (preset) {
    case "densest":
      return modelled.slice(0, 1).map((tile) => tile.id);
    case "densest 3":
      return modelled.slice(0, 3).map((tile) => tile.id);
    case "sparsest 3":
      return modelled.slice(-3).reverse().map((tile) => tile.id);
    case "all with a model":
      return modelled.map((tile) => tile.id);
  }
}
