import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";

import { api } from "@/api/client";
import type { CityResult, Results } from "@/api/models";
import { FacetChart } from "@/components/FacetChart";
import { Loading } from "@/components/Loading";
import { SeriesLegend } from "@/components/SeriesLegend";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { decimal, integer, percent } from "@/lib/format";

/** What the physics measured across every tile, with nothing typed in. */
export function ResultsPage() {
  const results = useQuery({ queryKey: ["results"], queryFn: api.results });
  return (
    <section>
      <h1>Results</h1>
      <Loading query={results} what="the results" />
      {results.data && (results.data.cities.length ? <Measured data={results.data} /> : <Nothing />)}
    </section>
  );
}

function Nothing() {
  return (
    <p className="mt-4 max-w-[60ch] text-muted-foreground">
      No tile has generated physics yet. Build a city, run the designs through the engine with{" "}
      <code>sdc surrogate treeshade generate</code>, and the results appear here.
    </p>
  );
}

function Measured({ data }: { data: Results }) {
  const totals = data.totals;
  const verdict = data.arrangement;
  return (
    <>
      <p className="mt-2 max-w-[60ch] text-muted-foreground">
        Every plan below was simulated with real physics across {totals.cities} {totals.cities === 1 ? "tile" : "tiles"}
        {verdict.cities_compared > 0 && (
          <>
            . In {verdict.scattered_wins} of {verdict.cities_compared} the scattered plan delivered more cooling per
            dollar than the clustered plan at the same coverage, by {verdict.ratio_min} to {verdict.ratio_max} times
          </>
        )}
        .
      </p>
      <dl className="mt-4 flex flex-wrap gap-x-8 gap-y-1 text-sm">
        <Fact label="As of" value={data.as_of} />
        <Fact label="Plans" value={`${integer(totals.plans)}, all engine-simulated`} />
        <Fact label="Budgets" value={`$${decimal(totals.budget_min_m, 2)}M to $${decimal(totals.budget_max_m, 2)}M`} />
        <Fact label="Threshold" value={`${data.threshold_C} C`} />
      </dl>

      <h2 className="mt-10">Cooling and people, by tile</h2>
      <p className="mt-1 max-w-[60ch] text-sm text-muted-foreground">
        Average exposure drop against people moved below the threshold. Up and to the right is better on both.
      </p>
      <div className="mt-3">
        <SeriesLegend />
      </div>
      <div className="mt-4 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {data.cities.map((city) => (
          <figure key={city.key} className="m-0">
            <figcaption className="mb-1 text-sm font-medium">{city.name}</figcaption>
            <FacetChart city={city} />
            <p className="text-xs text-muted-foreground">
              {percent(city.facts.canopy)} canopy, {percent(city.facts.built_fraction)} built, tier {city.facts.tier}
            </p>
          </figure>
        ))}
      </div>

      <Arrangement data={data} />
      <Ranking data={data} />
      <Measures data={data} />
      <EveryPlan cities={data.cities} />

      <p className="mt-10 border-t pt-4 text-sm text-muted-foreground">
        Every number is a real SOLWEIG run at 1 m, not a surrogate. Sparse probe designs are omitted from the charts:
        they exist to characterize the response kernel, not to be candidate plans.
      </p>
    </>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  );
}

function Arrangement({ data }: { data: Results }) {
  const rows = data.cities.filter((city) => city.matched);
  if (!rows.length) return null;
  const verdict = data.arrangement;
  const every = verdict.scattered_wins === verdict.cities_compared ? "in every tile compared" : `in ${verdict.scattered_wins} of ${verdict.cities_compared} tiles`;
  return (
    <>
      <h2 className="mt-10">Same trees, same money</h2>
      <p className="mt-1 max-w-[60ch] text-sm text-muted-foreground">
        The fairest comparison of arrangements is at the same coverage, so each tile is quoted on the clustered and
        scattered plans closest in coverage.
      </p>
      <div className="mt-4">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Tile</TableHead>
              <TableHead>Matched coverage</TableHead>
              <TableHead className="text-right">Clustered per $1k</TableHead>
              <TableHead className="text-right">Scattered per $1k</TableHead>
              <TableHead className="text-right">Scattered over clustered</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((city) => (
              <TableRow key={city.key}>
                <TableCell className="font-medium">{city.name}</TableCell>
                <TableCell>
                  {percent(city.matched!.clustered.coverage, 1)} against {percent(city.matched!.scattered.coverage, 1)}, $
                  {decimal(city.matched!.clustered.cost_m, 2)}M
                </TableCell>
                <TableCell className="text-right">{decimal(city.matched!.clustered.efficiency, 1)}</TableCell>
                <TableCell className="text-right">{decimal(city.matched!.scattered.efficiency, 1)}</TableCell>
                <TableCell className="text-right">{city.matched!.ratio === null ? "" : `${decimal(city.matched!.ratio, 1)}x`}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <p className="mt-3 text-sm">
        Scattered planting delivered more cooling per dollar than clustered planting {every}, by {verdict.ratio_min} to{" "}
        {verdict.ratio_max} times.
      </p>
    </>
  );
}

function Ranking({ data }: { data: Results }) {
  const ranking = data.ranking;
  if (!ranking.rows.length) return null;
  const top = ranking.rows[0];
  const bottom = ranking.rows[ranking.rows.length - 1];
  return (
    <>
      <h2 className="mt-10">Which tile buys the most</h2>
      <div className="mt-4">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Tile</TableHead>
              <TableHead>Regime</TableHead>
              <TableHead className="text-right">Clustered per $1k</TableHead>
              <TableHead className="text-right">Scattered per $1k</TableHead>
              <TableHead className="text-right">Gain from arranging</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {ranking.rows.map((row) => (
              <TableRow key={row.key}>
                <TableCell className="font-medium">{row.name}</TableCell>
                <TableCell>
                  {percent(row.canopy)} canopy, {percent(row.built_fraction)} built
                </TableCell>
                <TableCell className="text-right">{decimal(row.clustered_per_1k, 1)}</TableCell>
                <TableCell className="text-right">{decimal(row.scattered_per_1k, 1)}</TableCell>
                <TableCell className="text-right">{row.gain === null ? "" : `${decimal(row.gain, 1)}x`}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <p className="mt-3 text-sm">
        {ranking.spread && ranking.rows.length > 1
          ? `${top.name} returns ${decimal(ranking.spread, 1)}x more cooling per dollar than ${bottom.name}, measured on the median scattered plan of each. `
          : "One tile so far; the comparison needs a second. "}
        Per $1k is excess degree-hours above the threshold removed per thousand dollars over a 20 year horizon.
      </p>
    </>
  );
}

function Measures({ data }: { data: Results }) {
  const rows = Array.isArray(data.factorial) ? (data.factorial as Record<string, unknown>[]) : [];
  if (!rows.length) return null;
  const sorted = [...rows].sort(
    (a, b) =>
      String(a.city).localeCompare(String(b.city)) ||
      Number(a.budget_usd) - Number(b.budget_usd) ||
      String(a.kind).localeCompare(String(b.kind)),
  );
  return (
    <>
      <h2 className="mt-10">Which measure buys the most</h2>
      <p className="mt-1 max-w-[60ch] text-sm text-muted-foreground">
        The factorial experiment: every intervention type at every budget in every city, each cell a real run.
      </p>
      <div className="mt-4">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>City</TableHead>
              <TableHead>Measure</TableHead>
              <TableHead className="text-right">Budget</TableHead>
              <TableHead className="text-right">Units</TableHead>
              <TableHead className="text-right">Exposure drop, C</TableHead>
              <TableHead className="text-right">People below threshold</TableHead>
              <TableHead className="text-right">Per $1k</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.map((row, index) => (
              <TableRow key={index}>
                <TableCell className="font-medium capitalize">{String(row.city)}</TableCell>
                <TableCell>{String(row.kind)}</TableCell>
                <TableCell className="text-right">${decimal(Number(row.budget_usd) / 1e6, 1)}M</TableCell>
                <TableCell className="text-right">{integer(Number(row.units))}</TableCell>
                <TableCell className="text-right">{decimal(Number(row.exposure_drop_C), 3)}</TableCell>
                <TableCell className="text-right">{integer(Number(row.people))}</TableCell>
                <TableCell className="text-right">{decimal(Number(row.efficiency), 1)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </>
  );
}

function EveryPlan({ cities }: { cities: CityResult[] }) {
  return (
    <>
      <h2 className="mt-10">Every plan</h2>
      <div className="mt-4">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Tile</TableHead>
              <TableHead>Arrangement</TableHead>
              <TableHead className="text-right">Coverage</TableHead>
              <TableHead className="text-right">Cost</TableHead>
              <TableHead className="text-right">Exposure drop, C</TableHead>
              <TableHead className="text-right">People below threshold</TableHead>
              <TableHead className="text-right">Per $1k</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {cities.flatMap((city) =>
              [...city.plans]
                .sort((a, b) => a.arrangement.localeCompare(b.arrangement) || a.coverage - b.coverage)
                .map((plan) => (
                  <TableRow key={`${city.key}-${plan.id}`}>
                    <TableCell className="font-medium">
                      <Link to={`/cities/${city.key.split("-")[0]}/tiles/${city.tile}`} className="underline-offset-4 hover:underline">
                        {city.name}
                      </Link>
                    </TableCell>
                    <TableCell>{plan.arrangement}</TableCell>
                    <TableCell className="text-right">{percent(plan.coverage, 1)}</TableCell>
                    <TableCell className="text-right">${decimal(plan.cost_m, 2)}M</TableCell>
                    <TableCell className="text-right">{decimal(plan.exposure_drop, 4)}</TableCell>
                    <TableCell className="text-right">{integer(plan.people)}</TableCell>
                    <TableCell className="text-right">{decimal(plan.efficiency, 2)}</TableCell>
                  </TableRow>
                )),
            )}
          </TableBody>
        </Table>
      </div>
    </>
  );
}
