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
  type ScenarioOutcome,
  type TileGrid,
  type Basemap,
  type TileReport,
  type TileStatistics,
  type TileSummary,
} from "./models";
import type { components } from "./types";

export const API = "/api/v1";

type RawTileReport = components["schemas"]["TileReport"];

/** The levers of a scenario as the API takes them; exactly one of coverage and budget_usd is set. */
export interface ScenarioLevers {
  kind?: string;
  arrangement?: string;
  coverage?: number;
  budget_usd?: number;
  unit_cost?: number;
  maintenance?: number;
  threshold?: number;
  size?: number;
}

function leverSearch(levers: ScenarioLevers): string {
  const search = new URLSearchParams();
  for (const [name, value] of Object.entries(levers)) {
    if (value !== undefined) search.set(name, String(value));
  }
  return search.size ? `?${search}` : "";
}

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
  basemap: () => "/basemap",
  cities: () => "/cities",
  city: (city: string) => `/cities/${encodeURIComponent(city)}`,
  tiles: (city: string) => `/cities/${encodeURIComponent(city)}/tiles`,
  grid: (city: string) => `/cities/${encodeURIComponent(city)}/grid`,
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
  scenario: (city: string, tile: string, levers: ScenarioLevers) =>
    `/cities/${encodeURIComponent(city)}/tiles/${encodeURIComponent(tile)}/scenario${leverSearch(levers)}`,
  scenarioField: (city: string, tile: string, levers: ScenarioLevers) =>
    `/cities/${encodeURIComponent(city)}/tiles/${encodeURIComponent(tile)}/scenario/field${leverSearch(levers)}`,
  results: () => "/results",
  findings: () => "/findings",
  references: () => "/references",
  channels: () => "/channels",
  models: (channel: string, city?: string) =>
    `/channels/${encodeURIComponent(channel)}/models${city ? `?city=${encodeURIComponent(city)}` : ""}`,
};

export const api = {
  health: () => getJson<Health>(paths.health()),
  basemap: () => getJson<Basemap>(paths.basemap()),
  cities: () => getJson<CitySummary[]>(paths.cities()),
  city: (city: string) => getJson<TileStatistics>(paths.city(city)),
  tiles: (city: string) => getJson<TileSummary[]>(paths.tiles(city)),
  grid: (city: string) => getJson<TileGrid>(paths.grid(city)),
  report: async (city: string, tile: string): Promise<TileReport> =>
    tileReport(await getJson<RawTileReport>(paths.report(city, tile))),
  cityReport: async (city: string): Promise<TileReport> =>
    tileReport(await getJson<RawTileReport>(paths.cityReport(city))),
  scenario: (city: string, tile: string, levers: ScenarioLevers) =>
    getJson<ScenarioOutcome>(paths.scenario(city, tile, levers)),
  results: async (): Promise<Results> => results(await getJson<RawResults>(paths.results())),
  findings: () => getJson<Findings>(paths.findings()),
  references: () => getJson<ReferenceGroup[]>(paths.references()),
  channels: () => getJson<ChannelSummary[]>(paths.channels()),
  models: (channel: string, city?: string) => getJson<ModelSummary[]>(paths.models(channel, city)),
};
