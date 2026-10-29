import type { TileReport } from "@/api/models";
import { integer, percent } from "@/lib/format";

/** What the tile is: the facts of its bundle and the source every layer carries. */
export function TileFacts({ report }: { report: TileReport }) {
  const facts = report.facts;
  const rows: [string, string][] = [
    ["Design day", facts.design_day ?? ""],
    ["Input quality tier", facts.tier],
    ["Buildings with heights", integer(facts.buildings)],
    ["Ground built on", percent(facts.built_fraction)],
    ["Tree canopy over 2 m", percent(facts.canopy, 1)],
    ["Residents", integer(facts.population_2020)],
  ];
  const centre = facts.urban_centre;
  return (
    <div className="grid gap-8 md:grid-cols-2">
      <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-1.5 text-sm">
        {rows.map(([label, value]) => (
          <div key={label} className="contents">
            <dt className="text-muted-foreground">{label}</dt>
            <dd className="text-right tabular-nums">{value}</dd>
          </div>
        ))}
        {centre && (
          <div className="contents">
            <dt className="text-muted-foreground">Urban centre</dt>
            <dd className="text-right">
              {centre.name}, {centre.koppen ?? "?"}, income {centre.income ?? "?"}, {integer(centre.tiles)} tiles
            </dd>
          </div>
        )}
      </dl>
      <div className="text-sm">
        <p className="text-muted-foreground">Every layer carries its source.</p>
        <ul className="mt-2 space-y-1">
          {Object.entries(facts.sources).map(([layer, source]) => (
            <li key={layer}>
              <span className="text-muted-foreground">{layer}</span> {source}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
