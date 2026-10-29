/** The city's tile grid as a map wants it: cells with bounds, residents and the model flag, from the API's parallel lists. */

import type { FeatureCollection, Polygon } from "geojson";

import type { TileGrid } from "@/api/models";
import { type Ramp, type Rgb, ramp } from "@/lib/ramp";

export interface Cell {
  id: string;
  west: number;
  south: number;
  east: number;
  north: number;
  density: number;
  residents: number;
  modelled: boolean;
}

/** Residents per square kilometre, light to dark in the project's ink, so the map stays calm under the data. */
export const INK: Ramp = [
  [228, 234, 231],
  [168, 183, 178],
  [110, 128, 126],
  [64, 84, 90],
  [27, 43, 52],
];

export function cellsOf(grid: TileGrid): Cell[] {
  const ids = grid.ids ?? [];
  return (grid.cells ?? []).flatMap((values, index) => {
    const [west, south, east, north, density, residents, modelled] = values;
    if (ids[index] === undefined || values.length < 7) return [];
    return [{ id: ids[index], west, south, east, north, density, residents, modelled: modelled > 0 }];
  });
}

export type Bounds = [[number, number], [number, number]];

export function cellBounds(cell: Cell): Bounds {
  return [
    [cell.west, cell.south],
    [cell.east, cell.north],
  ];
}

export function gridBounds(cells: Cell[]): Bounds | null {
  if (cells.length === 0) return null;
  return [
    [Math.min(...cells.map((cell) => cell.west)), Math.min(...cells.map((cell) => cell.south))],
    [Math.max(...cells.map((cell) => cell.east)), Math.max(...cells.map((cell) => cell.north))],
  ];
}

/** The density the darkest ink stands for: the 95th percentile, so a few towers do not wash out the rest. */
export function densityCeiling(cells: Cell[]): number {
  const sorted = cells.map((cell) => cell.density).sort((a, b) => a - b);
  if (sorted.length === 0) return 1;
  return Math.max(1, sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * 0.95))]);
}

/** The colour as a hex string: the one form every renderer, the map library included, reads alike. */
export function densityColor(density: number, ceiling: number): string {
  return hex(ramp(INK, density / ceiling));
}

export const INK_LIGHT = hex(INK[0]);
export const INK_DARK = hex(INK[INK.length - 1]);

export function gridFeatures(cells: Cell[]): FeatureCollection<Polygon, Cell> {
  return {
    type: "FeatureCollection",
    features: cells.map((cell) => ({
      type: "Feature",
      id: cell.id,
      properties: cell,
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [cell.west, cell.south],
            [cell.east, cell.south],
            [cell.east, cell.north],
            [cell.west, cell.north],
            [cell.west, cell.south],
          ],
        ],
      },
    })),
  };
}

export interface Rect {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
  fill: string;
  modelled: boolean;
}

/** The grid as rectangles in a box of the given side, longitudes shortened by the latitude so squares stay square. */
export function thumbnail(cells: Cell[], side: number): { rects: Rect[]; width: number; height: number } {
  const bounds = gridBounds(cells);
  if (!bounds) return { rects: [], width: side, height: side };
  const [[west, south], [east, north]] = bounds;
  const stretch = Math.cos((((south + north) / 2) * Math.PI) / 180);
  const spanX = (east - west) * stretch || 1;
  const spanY = north - south || 1;
  const scale = side / Math.max(spanX, spanY);
  const width = spanX * scale;
  const height = spanY * scale;
  const ceiling = densityCeiling(cells);
  const rects = cells.map((cell) => ({
    id: cell.id,
    x: (cell.west - west) * stretch * scale,
    y: (north - cell.north) * scale,
    width: (cell.east - cell.west) * stretch * scale,
    height: (cell.north - cell.south) * scale,
    fill: densityColor(cell.density, ceiling),
    modelled: cell.modelled,
  }));
  return { rects, width, height };
}

function hex([r, g, b]: Rgb): string {
  return `#${[r, g, b].map((channel) => channel.toString(16).padStart(2, "0")).join("")}`;
}
