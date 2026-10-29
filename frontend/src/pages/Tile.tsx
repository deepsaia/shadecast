import { useQuery } from "@tanstack/react-query";
import { Pause, Play } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router";

import { api } from "@/api/client";
import { fetchField } from "@/api/fields";
import type { Plan, TileReport } from "@/api/models";
import { FieldCanvas } from "@/components/FieldCanvas";
import { MetChart } from "@/components/MetChart";
import { NextStep } from "@/components/NextStep";
import { TradeoffChart } from "@/components/TradeoffChart";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { decimal, integer, percent } from "@/lib/format";
import { band, type NpyArray } from "@/lib/npy";
import { COOL, HEAT, extent } from "@/lib/ramp";
import { seriesColor } from "@/lib/series";
import { cn } from "@/lib/utils";

const DISPLAY_PX = 384;

/** The walkthrough for one tile: what it is, the day's heat, the plans, and what the engine did. */
export function TilePage() {
  const { city = "", tile = "" } = useParams();
  const report = useQuery({ queryKey: ["report", city, tile], queryFn: () => api.report(city, tile) });
  if (report.isPending) return <p className="text-muted-foreground">Reading the tile.</p>;
  if (report.isError) {
    return (
      <p className="text-destructive" role="alert">
        {report.error.message}
      </p>
    );
  }
  const found = report.data;
  return (
    <article>
      <header>
        <h1>
          {found.name} <span className="font-sans text-xl font-normal text-muted-foreground">tile {found.tile}</span>
        </h1>
        <p className="mt-2 max-w-[60ch] text-muted-foreground">
          One square kilometre at one metre, built from open data, run through the radiation physics, and
          planted in every arrangement the surrogate learns from.
          {found.stages.model && (
            <>
              {" "}
              <Link to={`/cities/${city}/tiles/${tile}/scenario`} className="underline underline-offset-4">
                Move the levers on this tile
              </Link>
              .
            </>
          )}
        </p>
      </header>
      <FactsPanel report={found} />
      {found.baseline ? (
        <HeatPanel city={city} tile={tile} report={found} />
      ) : (
        <Panel title="The day's heat">
          <NextStep missing="baseline physics" command={`sdc simulate baseline ${city} --tile ${tile}`} />
        </Panel>
      )}
      {found.plans.length > 0 ? (
        <PlansPanel city={city} tile={tile} report={found} />
      ) : (
        found.baseline && (
          <Panel title="The plans">
            <NextStep
              missing="designed physics"
              command={`sdc simulate treeshade ${city} --tiles ${tile}`}
            />
          </Panel>
        )
      )}
      {found.physics && <PhysicsPanel report={found} />}
    </article>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-10 border-t pt-6">
      <h2>{title}</h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function FactsPanel({ report }: { report: TileReport }) {
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
    <Panel title="What the tile is">
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
    </Panel>
  );
}

function HeatPanel({ city, tile, report }: { city: string; tile: string; report: TileReport }) {
  const [hour, setHour] = useState(15);
  const [playing, setPlaying] = useState(false);
  const hours = useQuery({
    queryKey: ["field", city, tile, "hours", DISPLAY_PX],
    queryFn: () => fetchField(city, tile, "hours", { size: DISPLAY_PX }),
  });
  const scale = useMemo(() => (hours.data ? extent(hours.data.data) : null), [hours.data]);
  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => setHour((current) => (current + 1) % 24), 400);
    return () => window.clearInterval(timer);
  }, [playing]);
  const statistic = report.hourly[hour];
  return (
    <Panel title="The day's heat">
      <p className="max-w-[60ch] text-sm text-muted-foreground">
        Mean radiant temperature for every square metre and every hour, on one scale held fixed across the
        day. Hover any pixel to read its value.
      </p>
      <div className="mt-4 grid gap-6 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div>
          {hours.data && scale ? (
            <HourField array={hours.data} hour={hour} scale={scale} />
          ) : (
            <div className="aspect-square w-full rounded-sm bg-secondary" aria-busy="true" />
          )}
          <div className="mt-3 flex items-center gap-3">
            <Button
              variant="outline"
              size="icon"
              aria-pressed={playing}
              aria-label={playing ? "Pause" : "Play the day"}
              onClick={() => setPlaying((current) => !current)}
            >
              {playing ? <Pause /> : <Play />}
            </Button>
            <Slider
              value={[hour]}
              min={0}
              max={23}
              step={1}
              onValueChange={([value]) => setHour(value)}
              aria-label="Hour of day"
              className="flex-1"
            />
            <span className="w-14 text-right tabular-nums">{String(hour).padStart(2, "0")}:00</span>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            {statistic ? `median ${decimal(statistic.median, 1)} C, peak ${decimal(statistic.max, 1)} C` : ""}
            {scale ? `, scale ${decimal(scale.min, 0)} to ${decimal(scale.max, 0)} C` : ""}
          </p>
        </div>
        <div>
          <p className="text-sm text-muted-foreground">Weather on the design day</p>
          <div className="mt-2">
            <MetChart met={report.met} hour={hour} />
          </div>
          {report.baseline && (
            <p className="mt-4 text-sm">
              Doing nothing leaves a population-weighted outdoor exposure of{" "}
              <strong>{decimal(report.baseline.exposure, 1)} C</strong>, with{" "}
              <strong>{integer(report.baseline.at_risk)}</strong> people on ground above the stress threshold.
            </p>
          )}
        </div>
      </div>
    </Panel>
  );
}

function HourField({ array, hour, scale }: { array: NpyArray; hour: number; scale: { min: number; max: number } }) {
  const [, height, width] = array.shape;
  const values = useMemo(() => band(array, hour), [array, hour]);
  return (
    <FieldCanvas
      values={values}
      width={width}
      height={height}
      encoding={{ kind: "quantity", ramp: HEAT, scale, unit: " C" }}
      label={`Mean radiant temperature at ${hour}:00`}
    />
  );
}

function PlansPanel({ city, tile, report }: { city: string; tile: string; report: TileReport }) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = report.plans.find((plan) => plan.id === selectedId) ?? report.plans[0];
  return (
    <Panel title="The plans">
      <p className="max-w-[60ch] text-sm text-muted-foreground">
        The same canopy at each coverage, in different arrangements, every one simulated. Two objectives
        disagree about which wins; both are shown. Pick a plan to see where its trees go and what cooling
        arrives.
      </p>
      <div className="mt-4 grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <TradeoffChart plans={report.plans} selected={selected.id} onSelect={setSelectedId} />
        <PlanList plans={report.plans} selected={selected.id} onSelect={setSelectedId} />
      </div>
      <p className="mt-4 text-sm">
        <span className="inline-block size-2.5 rounded-full align-middle" style={{ background: seriesColor(selected.arrangement) }} />{" "}
        <strong>{selected.arrangement}</strong> at {percent(selected.coverage, 1)} coverage costs{" "}
        <strong>${decimal(selected.cost_m, 2)}M</strong>, lowers average outdoor exposure by{" "}
        <strong>{decimal(selected.exposure_drop, 2)} C</strong> and moves{" "}
        <strong>{integer(selected.people)}</strong> people below the threshold.
      </p>
      <PlanFields city={city} tile={tile} plan={selected} />
    </Panel>
  );
}

function PlanList({
  plans,
  selected,
  onSelect,
}: {
  plans: Plan[];
  selected: string;
  onSelect: (id: string) => void;
}) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Plan</TableHead>
          <TableHead className="text-right">Coverage</TableHead>
          <TableHead className="text-right">Cost</TableHead>
          <TableHead className="text-right">Drop, C</TableHead>
          <TableHead className="text-right">Per $1k</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {plans.map((plan) => (
          <TableRow
            key={plan.id}
            aria-selected={plan.id === selected}
            className={cn("cursor-pointer", plan.id === selected && "bg-secondary")}
            onClick={() => onSelect(plan.id)}
          >
            <TableCell>
              <button type="button" className="flex items-center gap-2 text-left" onClick={() => onSelect(plan.id)}>
                <span className="inline-block size-2.5 rounded-full" style={{ background: seriesColor(plan.arrangement) }} />
                {plan.arrangement}
              </button>
            </TableCell>
            <TableCell className="text-right">{percent(plan.coverage, 1)}</TableCell>
            <TableCell className="text-right">${decimal(plan.cost_m, 2)}M</TableCell>
            <TableCell className="text-right">{decimal(plan.exposure_drop, 2)}</TableCell>
            <TableCell className="text-right">{decimal(plan.efficiency, 1)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function PlanFields({ city, tile, plan }: { city: string; tile: string; plan: Plan }) {
  const placement = useQuery({
    queryKey: ["field", city, tile, "placement", plan.id, DISPLAY_PX],
    queryFn: () => fetchField(city, tile, "placement", { design: plan.id, size: DISPLAY_PX }),
  });
  const cooling = useQuery({
    queryKey: ["field", city, tile, "cooling", plan.id, DISPLAY_PX],
    queryFn: () => fetchField(city, tile, "cooling", { design: plan.id, size: DISPLAY_PX }),
  });
  const scale = useMemo(() => (cooling.data ? extent(cooling.data.data) : null), [cooling.data]);
  return (
    <div className="mt-6 grid gap-6 md:grid-cols-2">
      <figure className="m-0">
        <figcaption className="mb-2 text-sm text-muted-foreground">Where the trees go</figcaption>
        {placement.data ? (
          <FieldCanvas
            values={placement.data.data}
            width={placement.data.shape[1]}
            height={placement.data.shape[0]}
            encoding={{ kind: "mask" }}
            label={`Placement of ${plan.id}`}
          />
        ) : (
          <div className="aspect-square w-full rounded-sm bg-secondary" aria-busy="true" />
        )}
      </figure>
      <figure className="m-0">
        <figcaption className="mb-2 text-sm text-muted-foreground">Cooling delivered, hover to read</figcaption>
        {cooling.data && scale ? (
          <FieldCanvas
            values={cooling.data.data}
            width={cooling.data.shape[1]}
            height={cooling.data.shape[0]}
            encoding={{ kind: "quantity", ramp: COOL, scale: { min: 0, max: scale.max }, unit: " C cooler", floor: 0.05 }}
            label={`Cooling delivered by ${plan.id}`}
          />
        ) : (
          <div className="aspect-square w-full rounded-sm bg-secondary" aria-busy="true" />
        )}
      </figure>
    </div>
  );
}

function PhysicsPanel({ report }: { report: TileReport }) {
  const physics = report.physics!;
  return (
    <Panel title="What the engine did">
      <p className="text-sm">
        <strong>{physics.designs}</strong> designs through the physics engine, {decimal(physics.engine_minutes, 0)} engine
        minutes in all, {physics.seconds_per_design_min} to {physics.seconds_per_design_max} seconds a design.
      </p>
    </Panel>
  );
}
