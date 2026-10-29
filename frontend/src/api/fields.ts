/** Fetch a tile's field as an array, the way the API serves it: NPY, hours or plans first. */

import { API, ApiError, paths, type ScenarioLevers } from "./client";
import { parseNpy, type NpyArray } from "@/lib/npy";

export interface FieldQuery {
  design?: string;
  size?: number;
}

export async function fetchField(
  city: string,
  tile: string,
  field: "hours" | "context" | "cooling" | "placement",
  query: FieldQuery = {},
): Promise<NpyArray> {
  return fetchNpy(paths.field(city, tile, field, query));
}

/** A scenario's cooling field and placement, stacked in that order. */
export async function fetchScenarioField(city: string, tile: string, levers: ScenarioLevers): Promise<NpyArray> {
  return fetchNpy(paths.scenarioField(city, tile, levers));
}

async function fetchNpy(path: string): Promise<NpyArray> {
  const response = await fetch(`${API}${path}`);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const message = typeof body.error === "string" ? body.error : `${response.status} for ${path}`;
    throw new ApiError(response.status, message, body);
  }
  return parseNpy(await response.arrayBuffer());
}
