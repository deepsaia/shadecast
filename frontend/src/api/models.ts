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
export type Results = components["schemas"]["Results"];
export type Health = components["schemas"]["Health"];

type RawTileReport = components["schemas"]["TileReport"];
export type Plan = NonNullable<RawTileReport["plans"]>[number];
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
