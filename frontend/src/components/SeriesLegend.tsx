import { ARRANGEMENTS, seriesColor } from "@/lib/series";

const WORDS: Record<string, string> = {
  clustered: "clustered, what greedy produces",
  scattered: "scattered",
  corridor: "corridor, along streets",
};

/** The one legend for the arrangements, present wherever two or more of them are drawn. */
export function SeriesLegend() {
  return (
    <ul className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-muted-foreground">
      {ARRANGEMENTS.map((arrangement) => (
        <li key={arrangement} className="flex items-center gap-2">
          <span className="inline-block size-2.5 rounded-full" style={{ background: seriesColor(arrangement) }} />
          {WORDS[arrangement]}
        </li>
      ))}
    </ul>
  );
}
