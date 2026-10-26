/**
 * Names for the schemas the client uses most, taken from the generated types so they stay one
 * contract. A report's lists default to empty on the server, which the schema records as optional;
 * the client reads them as arrays, so they are made required here and filled in by the client.
 */

import type { components } from "./types";

export type CitySummary = components["schemas"]["CitySummary"];
export type StageCounts = components["schemas"]["StageCounts"];
export type TileSummary = components["schemas"]["TileSummary"];
export type TileStatistics = components["schemas"]["TileStatistics"];
export type Health = components["schemas"]["Health"];
export type Findings = components["schemas"]["Findings"];
export type ModelSummary = components["schemas"]["ModelSummary"];
export type ChannelSummary = components["schemas"]["ChannelSummary"];
export type Plan = components["schemas"]["Plan"];

export type RawResults = components["schemas"]["Results"];
type RawCityResult = RawResults["cities"][number];
export type CityResult = Omit<RawCityResult, "plans"> & { plans: Plan[] };
export type Results = Omit<RawResults, "cities"> & { cities: CityResult[] };
export type RankingRow = Results["ranking"]["rows"][number];

export function results(raw: RawResults): Results {
  return { ...raw, cities: raw.cities.map((city) => ({ ...city, plans: city.plans ?? [] })) };
}

/** A cited source as the registry lists it, in its group. */
export interface Reference {
  key: string;
  group: string;
  title: string;
  authors_or_publisher: string;
  year: number | null;
  doi: string | null;
  used_for: string;
}

export interface ReferenceGroup {
  key: string;
  title: string;
  sources: Reference[];
}

type RawTileReport = components["schemas"]["TileReport"];
export type MetHour = NonNullable<RawTileReport["met"]>[number];
export type HourlyStatistic = NonNullable<RawTileReport["hourly"]>[number];
export type TileReport = Omit<RawTileReport, "plans" | "met" | "hourly"> & {
  plans: Plan[];
  met: MetHour[];
  hourly: HourlyStatistic[];
};

export function tileReport(raw: RawTileReport): TileReport {
  return { ...raw, plans: raw.plans ?? [], met: raw.met ?? [], hourly: raw.hourly ?? [] };
}
