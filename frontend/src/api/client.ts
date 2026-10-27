/**
 * The one way the client reaches data: typed fetches over /api/v1, with the server's own error
 * body surfaced as the message. Paths are built here and nowhere else.
 */

import {
  tileReport,
  type ChannelSummary,
  type CitySummary,
  type Findings,
  type Health,
  type ModelSummary,
  type RawResults,
  type ReferenceGroup,
  type Results,
  results,
  type TileReport,
  type TileStatistics,
  type TileSummary,
} from "./models";
import type { components } from "./types";

export const API = "/api/v1";

type RawTileReport = components["schemas"]["TileReport"];

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly body: Record<string, unknown>,
  ) {
    super(message);
  }
}

export async function getJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, { ...init, headers: { Accept: "application/json" } });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const message = typeof body.error === "string" ? body.error : `${response.status} for ${path}`;
    throw new ApiError(response.status, message, body);
  }
  return (await response.json()) as T;
}

export const paths = {
  health: () => "/health",
  cities: () => "/cities",
  city: (city: string) => `/cities/${encodeURIComponent(city)}`,
  tiles: (city: string) => `/cities/${encodeURIComponent(city)}/tiles`,
  report: (city: string, tile: string) =>
    `/cities/${encodeURIComponent(city)}/tiles/${encodeURIComponent(tile)}/report`,
  cityReport: (city: string) => `/cities/${encodeURIComponent(city)}/report`,
  field: (city: string, tile: string, field: string, query: { design?: string; size?: number } = {}) => {
    const search = new URLSearchParams();
    if (query.design) search.set("design", query.design);
    if (query.size) search.set("size", String(query.size));
    const suffix = search.size ? `?${search}` : "";
    return `/cities/${encodeURIComponent(city)}/tiles/${encodeURIComponent(tile)}/fields/${field}${suffix}`;
  },
  results: () => "/results",
  findings: () => "/findings",
  references: () => "/references",
  channels: () => "/channels",
  models: (channel: string, city?: string) =>
    `/channels/${encodeURIComponent(channel)}/models${city ? `?city=${encodeURIComponent(city)}` : ""}`,
};

export const api = {
  health: () => getJson<Health>(paths.health()),
  cities: () => getJson<CitySummary[]>(paths.cities()),
  city: (city: string) => getJson<TileStatistics>(paths.city(city)),
  tiles: (city: string) => getJson<TileSummary[]>(paths.tiles(city)),
  report: async (city: string, tile: string): Promise<TileReport> =>
    tileReport(await getJson<RawTileReport>(paths.report(city, tile))),
  cityReport: async (city: string): Promise<TileReport> =>
    tileReport(await getJson<RawTileReport>(paths.cityReport(city))),
  results: async (): Promise<Results> => results(await getJson<RawResults>(paths.results())),
  findings: () => getJson<Findings>(paths.findings()),
  references: () => getJson<ReferenceGroup[]>(paths.references()),
  channels: () => getJson<ChannelSummary[]>(paths.channels()),
  models: (channel: string, city?: string) => getJson<ModelSummary[]>(paths.models(channel, city)),
};
