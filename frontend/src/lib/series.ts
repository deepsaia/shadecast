/**
 * The arrangements and their colors: fixed per entity, never cycled, validated in both modes with
 * the project's visualization rules (clustered blue, scattered orange, corridor aqua).
 */

export const ARRANGEMENTS = ["clustered", "scattered", "corridor"] as const;
export type Arrangement = (typeof ARRANGEMENTS)[number];

const SLOT: Record<Arrangement, string> = {
  clustered: "var(--series-1)",
  scattered: "var(--series-2)",
  corridor: "var(--series-3)",
};

export function seriesColor(arrangement: string): string {
  return SLOT[arrangement as Arrangement] ?? "var(--muted-foreground)";
}
