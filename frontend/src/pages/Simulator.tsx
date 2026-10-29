import { keepPreviousData, useQueries, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router";

import { api, ApiError } from "@/api/client";
import { fetchScenarioField } from "@/api/fields";
import type { CitySummary, ScenarioOutcome, TileSummary } from "@/api/models";
import { Chips } from "@/components/Chips";
import { FieldCanvas } from "@/components/FieldCanvas";
import { HeatReplay } from "@/components/HeatReplay";
import { NextStep } from "@/components/NextStep";
import { Picker } from "@/components/Picker";
import { TileFacts } from "@/components/TileFacts";
import { TradeoffChart } from "@/components/TradeoffChart";
import { Checkbox } from "@/components/ui/checkbox";
import { Slider } from "@/components/ui/slider";
import { aggregate, type Totals } from "@/lib/aggregate";
import { useDebounced } from "@/lib/debounce";
import { decimal, integer, percent } from "@/lib/format";
import { band, type NpyArray } from "@/lib/npy";
import { POLICIES, policyOf } from "@/lib/policies";
import { COOL, extent } from "@/lib/ramp";
import {
  BUDGET,
  COVERAGE,
  INITIAL_SCALE,
  type Scale,
  alignToAnswer,
  leversOf,
  moveBudget,
  moveCoverage,
  rateOf,
  setLocked,
} from "@/lib/scale";
import { seriesColor } from "@/lib/series";
import { PRESETS, type Preset, applyPreset } from "@/lib/tile_presets";
import { cn } from "@/lib/utils";

const DISPLAY_PX = 384;
const SETTLE_MS = 200; // a slider rests this long before the surrogate is asked

/** The simulator: pick a city and its tiles, set the policy, the design and the scale, read the outcomes. */
export function SimulatorPage() {
  const [params, setParams] = useSearchParams();
  const cities = useQuery({ queryKey: ["cities"], queryFn: api.cities });
  const cityKey = params.get("city") ?? firstWithModel(cities.data) ?? "";
  const tiles = useQuery({ queryKey: ["tiles", cityKey], queryFn: () => api.tiles(cityKey), enabled: cityKey !== "" });
  const chosen = useMemo(
    () => params.get("tiles")?.split(",").filter(Boolean) ?? applyPreset("densest", tiles.data ?? []),
    [params, tiles.data],
  );
  const focused = params.get("focus") ?? chosen[0] ?? "";
  const city = cities.data?.find((found) => found.key === cityKey);

  function choose(next: { city?: string; tiles?: string[]; focus?: string }) {
    const search = new URLSearchParams();
    const key = next.city ?? cityKey;
    if (key) search.set("city", key);
    if (next.city === undefined) {
      const ids = next.tiles ?? chosen;
      if (ids.length > 0) search.set("tiles", ids.join(","));
      if (next.focus && ids.includes(next.focus)) search.set("focus", next.focus);
    }
    setParams(search);
  }

  return (
    <article>
      <header>
        <h1>Simulator</h1>
        <p className="mt-1 text-lg text-muted-foreground">Heatwave Resilient Cities Simulator</p>
      </header>
      <Where
        cities={cities.data ?? []}
        city={city}
        tiles={tiles.data ?? []}
        chosen={chosen}
        onCity={(key) => choose({ city: key })}
        onTiles={(ids) => choose({ tiles: ids })}
      />
      {cities.isError && (
        <p className="mt-6 text-destructive" role="alert">
          The server did not answer: {cities.error.message}. Start it with <code>sdc serve</code>.
        </p>
      )}
      {city && tiles.data && chosen.length === 0 && (
        <div className="mt-6">
          <NextStep missing="tile with a trained surrogate" command={`sdc surrogate treeshade train ${city.key}`} />
        </div>
      )}
      {city && chosen.length > 0 && (
        <Scenario
          city={city}
          tiles={tiles.data ?? []}
          chosen={chosen}
          focused={focused}
          onFocus={(tile) => choose({ focus: tile })}
        />
      )}
    </article>
  );
}

function firstWithModel(cities: CitySummary[] | undefined): string | undefined {
  return (cities ?? []).find((city) => city.stages.model > 0)?.key ?? cities?.[0]?.key;
}

function Where({
  cities,
  city,
  tiles,
  chosen,
  onCity,
  onTiles,
}: {
  cities: CitySummary[];
  city: CitySummary | undefined;
  tiles: TileSummary[];
  chosen: string[];
  onCity: (key: string) => void;
  onTiles: (ids: string[]) => void;
}) {
  const [preset, setPreset] = useState<Preset | null>("densest");
  const cityChoices = [...cities]
    .sort((a, b) => Number(b.stages.model > 0) - Number(a.stages.model > 0))
    .map((found) => ({
      value: found.key,
      label: `${found.name}, ${found.country}`,
      note: found.stages.model > 0 ? `${found.stages.model} with a model` : lacking(found),
    }));
  const tileChoices = tiles.map((tile) => ({
    value: tile.id,
    label: tile.id,
    note: tile.stages.model ? `${integer(tile.population_2020)} residents` : "no model yet",
    disabled: !tile.stages.model,
  }));
  const modelled = tiles.filter((tile) => tile.stages.model).length;
  function toggleTile(id: string) {
    setPreset(null);
    onTiles(chosen.includes(id) ? chosen.filter((found) => found !== id) : [...chosen, id]);
  }
  return (
    <section aria-label="Where" className="mt-6 flex flex-wrap items-start gap-x-8 gap-y-4">
      <div>
        <p className="text-sm font-medium text-muted-foreground">City</p>
        <div className="mt-1.5">
          <Picker
            label="City"
            summary={city ? `${city.name}, ${city.country}` : "Choose a city"}
            choices={cityChoices}
            selected={city ? [city.key] : []}
            onPick={onCity}
          />
        </div>
      </div>
      <div>
        <p className="text-sm font-medium text-muted-foreground">Tiles</p>
        <div className="mt-1.5 flex flex-wrap items-center gap-3">
          <Picker
            label="Tiles"
            summary={tileSummary(chosen, modelled, tiles.length)}
            choices={tileChoices}
            selected={chosen}
            multiple
            onPick={toggleTile}
          />
          <Chips
            label="Tile presets"
            options={PRESETS.map((name) => ({ key: name, label: name }))}
            value={preset}
            onChange={(name) => {
              setPreset(name as Preset);
              onTiles(applyPreset(name as Preset, tiles));
            }}
          />
        </div>
      </div>
      <div>
        <p className="text-sm font-medium text-muted-foreground">Weather</p>
        <div className="mt-1.5">
          <Chips
            label="Weather"
            options={[
              { key: "design-day", label: "Design day, the hottest in the window" },
              { key: "other", label: "Other days", live: false },
            ]}
            value="design-day"
            onChange={() => undefined}
          />
        </div>
      </div>
    </section>
  );
}

function lacking(city: CitySummary): string {
  if (city.stages.physics > 0) return "no model yet";
  if (city.stages.bundle > 0) return "no physics yet";
  return "not built yet";
}

function tileSummary(chosen: string[], modelled: number, total: number): string {
  if (chosen.length === 0) return total === 0 ? "No tiles described" : `No tile chosen, ${modelled} of ${total} have a model`;
  if (chosen.length === 1) return chosen[0];
  return `${chosen.length} tiles`;
}

function Scenario({
  city,
  tiles,
  chosen,
  focused,
  onFocus,
}: {
  city: CitySummary;
  tiles: TileSummary[];
  chosen: string[];
  focused: string;
  onFocus: (tile: string) => void;
}) {
  const [policyKey, setPolicyKey] = useState("tree");
  const policy = policyOf(policyKey);
  const [designKey, setDesignKey] = useState(policy.designs[0].key);
  const [scale, setScale] = useState<Scale>(INITIAL_SCALE);
  const settled = useDebounced(scale, SETTLE_MS);
  const levers = useMemo(() => leversOf(designKey, settled), [designKey, settled]);
  const answers = useQueries({
    queries: chosen.map((tile) => ({
      queryKey: ["scenario", city.key, tile, levers],
      queryFn: () => api.scenario(city.key, tile, levers),
      placeholderData: keepPreviousData,
    })),
  });
  const outcomes = answers.map((answer) => answer.data).filter((found): found is ScenarioOutcome => Boolean(found));
  const residents = Object.fromEntries(tiles.map((tile) => [tile.id, tile.population_2020 ?? 0]));
  const totals = outcomes.length > 0 ? aggregate(outcomes, residents) : null;
  const busy = answers.some((answer) => answer.isFetching);
  const failed = answers.find((answer) => answer.isError)?.error;
  const focusedOutcome = outcomes.find((outcome) => outcome.tile === focused) ?? outcomes[0];
  const rate = rateOf(focusedOutcome);
  const shown = focusedOutcome ? alignToAnswer(scale, focusedOutcome) : scale;
  const report = useQuery({ queryKey: ["report", city.key, focused], queryFn: () => api.report(city.key, focused) });
  const fields = useQuery({
    queryKey: ["scenarioField", city.key, focused, levers, DISPLAY_PX],
    queryFn: () => fetchScenarioField(city.key, focused, { ...levers, size: DISPLAY_PX }),
    placeholderData: keepPreviousData,
  });

  function choosePolicy(key: string) {
    setPolicyKey(key);
    setDesignKey(policyOf(key).designs[0].key);
  }

  return (
    <>
      {failed ? <Unanswered error={failed} /> : <OutcomesRow totals={totals} busy={busy} />}
      <section aria-label="Levers" className="mt-8 grid gap-8 md:grid-cols-3">
        <Lever title="Policy" question="What to build">
          <Chips
            label="Policy"
            options={POLICIES.map((found) => ({ key: found.key, label: found.label, live: found.live }))}
            value={policyKey}
            onChange={choosePolicy}
          />
        </Lever>
        <Lever title="How to arrange it" question="Designs under that policy">
          <Chips
            label="Design"
            options={policy.designs.map((design) => ({
              key: design.key,
              label: design.label,
              live: design.live,
              color: design.live ? seriesColor(design.key) : undefined,
            }))}
            value={designKey}
            onChange={setDesignKey}
          />
        </Lever>
        <Lever title="Scale" question="How much">
          <ScaleSliders scale={shown} rate={rate} outcome={focusedOutcome} onChange={setScale} />
        </Lever>
      </section>
      <section className="mt-10 border-t pt-6">
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-2">
          <h2>
            Tile {focused} <span className="font-normal text-muted-foreground">in {city.name}</span>
          </h2>
          {chosen.length > 1 && (
            <Chips
              label="Focused tile"
              options={chosen.map((tile) => ({ key: tile, label: tile }))}
              value={focused}
              onChange={onFocus}
            />
          )}
          <Link to={`/cities/${city.key}/tiles/${focused}`} className="text-sm underline underline-offset-4">
            The tile's own page
          </Link>
        </div>
        <Fields fields={fields.data} busy={fields.isFetching} />
        {report.data && report.data.plans.length > 0 && focusedOutcome && (
          <div className="mt-8">
            <h3 className="font-medium">Against the physics</h3>
            <p className="mt-1 max-w-[60ch] text-sm text-muted-foreground">
              The stored designs were each run through the engine. This scenario is the diamond among them.
            </p>
            <div className="mt-3">
              <TradeoffChart
                plans={report.data.plans}
                live={{ exposure_drop: focusedOutcome.exposure_drop, people: focusedOutcome.people, label: "this scenario" }}
              />
            </div>
          </div>
        )}
        {focusedOutcome && (
          <p className="mt-6 text-sm text-muted-foreground">
            Answered by {focusedOutcome.model_id} in {decimal(focusedOutcome.surrogate_seconds, 2)} s.
          </p>
        )}
      </section>
      {report.data && (
        <>
          <Panel title="The day's heat">
            {report.data.baseline ? (
              <HeatReplay city={city.key} tile={focused} report={report.data} />
            ) : (
              <NextStep missing="baseline physics" command={`sdc simulate baseline ${city.key} --tile ${focused}`} />
            )}
          </Panel>
          <Panel title="What the tile is">
            <TileFacts report={report.data} />
          </Panel>
        </>
      )}
    </>
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

function Lever({ title, question, children }: { title: string; question: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="text-base">
        {title} <span className="font-normal text-muted-foreground">{question}</span>
      </h2>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function ScaleSliders({
  scale,
  rate,
  outcome,
  onChange,
}: {
  scale: Scale;
  rate: number | null;
  outcome: ScenarioOutcome | undefined;
  onChange: (scale: Scale) => void;
}) {
  const drives = (driver: Scale["driver"]) => !scale.locked && scale.driver === driver;
  return (
    <div className="space-y-4">
      <div>
        <div className="flex items-baseline justify-between text-sm">
          <span>
            Coverage of the plantable ground{" "}
            {drives("coverage") && <span className="text-xs text-muted-foreground">drives</span>}
          </span>
          <strong className="tabular-nums">{percent(scale.coverage, 1)}</strong>
        </div>
        <Slider
          value={[scale.coverage]}
          min={COVERAGE.min}
          max={COVERAGE.max}
          step={COVERAGE.step}
          onValueChange={([value]) => onChange(moveCoverage(scale, value, rate))}
          aria-label="Coverage of the plantable ground"
          className="mt-2"
        />
        {outcome && (
          <p className="mt-1 text-xs text-muted-foreground">
            {integer(outcome.trees)} trees
            {!scale.locked && scale.driver === "budget" && `, the budget buys ${percent(outcome.coverage, 1)}`}
          </p>
        )}
      </div>
      <div>
        <div className="flex items-baseline justify-between text-sm">
          <span>
            Budget per tile {drives("budget") && <span className="text-xs text-muted-foreground">drives</span>}
          </span>
          <strong className="tabular-nums">{decimal(scale.budget / 1e6, 2)} M USD</strong>
        </div>
        <Slider
          value={[scale.budget]}
          min={BUDGET.min}
          max={BUDGET.max}
          step={BUDGET.step}
          onValueChange={([value]) => onChange(moveBudget(scale, value, rate))}
          aria-label="Budget per tile"
          className="mt-2"
        />
        {outcome && !scale.locked && scale.driver === "coverage" && (
          <p className="mt-1 text-xs text-muted-foreground">
            the coverage costs {decimal(outcome.cost_usd / 1e6, 2)} M USD
          </p>
        )}
      </div>
      <label className="flex items-center gap-2 text-sm">
        <Checkbox
          checked={scale.locked}
          onCheckedChange={(checked) => onChange(setLocked(scale, checked === true, rate))}
          aria-label="Move the two together"
        />
        Move the two together through the cost table
      </label>
    </div>
  );
}

function OutcomesRow({ totals, busy }: { totals: Totals | null; busy: boolean }) {
  if (!totals) {
    return (
      <div className="mt-8 grid gap-3 sm:grid-cols-2 xl:grid-cols-5" aria-busy="true">
        {Array.from({ length: 5 }, (_, index) => (
          <div key={index} className="h-24 rounded-md bg-secondary" />
        ))}
      </div>
    );
  }
  const over = totals.tiles > 1 ? ` over ${totals.tiles} tiles` : "";
  return (
    <section
      aria-label="Outcomes"
      aria-busy={busy}
      className={cn("mt-8 grid gap-3 transition-opacity sm:grid-cols-2 xl:grid-cols-5", busy && "opacity-60")}
    >
      <Outcome
        label="Exposure drop"
        value={decimal(totals.exposure_drop, 2)}
        unit="C"
        note={`from ${decimal(totals.baseline_exposure, 1)} C, population weighted${over}`}
      />
      <Outcome
        label="Degree-hours removed"
        value={integer(totals.excess_removed)}
        note={`above 45 C, summed over the people exposed${over}`}
      />
      <Outcome
        label="People moved below 45 C"
        value={integer(totals.people)}
        note={`of ${integer(totals.baseline_at_risk)} above it today${over}`}
      />
      <Outcome
        label="Equity gap change"
        value={`${totals.equity_gap_change > 0 ? "+" : ""}${decimal(totals.equity_gap_change, 2)}`}
        unit="C"
        note="densest tenth against sparsest; below zero narrows it"
      />
      <Outcome
        label="Cost"
        value={decimal(totals.cost_usd / 1e6, 2)}
        unit="M USD"
        note={`${integer(totals.trees)} trees, ${decimal(totals.efficiency, 1)} degree-hours per 1,000 USD`}
      />
    </section>
  );
}

function Outcome({ label, value, unit, note }: { label: string; value: string; unit?: string; note: string }) {
  return (
    <div className="rounded-md border bg-card p-4">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="mt-1 font-display text-3xl font-bold tracking-tight">
        {value}
        {unit && <span className="ml-1.5 font-sans text-base font-normal text-muted-foreground">{unit}</span>}
      </p>
      <p className="mt-1 text-xs text-muted-foreground">{note}</p>
    </div>
  );
}

function Unanswered({ error }: { error: Error }) {
  const command = error instanceof ApiError && typeof error.body.command === "string" ? error.body.command : null;
  if (command) {
    return (
      <div className="mt-8">
        <NextStep missing="trained surrogate" command={command} />
      </div>
    );
  }
  return (
    <p className="mt-8 text-destructive" role="alert">
      {error.message}
    </p>
  );
}

function Fields({ fields, busy }: { fields: NpyArray | undefined; busy: boolean }) {
  const cooling = useMemo(() => (fields ? band(fields, 0) : null), [fields]);
  const placement = useMemo(() => (fields ? band(fields, 1) : null), [fields]);
  const scale = useMemo(() => (cooling ? extent(cooling) : null), [cooling]);
  const [, height, width] = fields?.shape ?? [0, 0, 0];
  return (
    <div className={cn("mt-6 grid gap-6 transition-opacity md:grid-cols-2", busy && "opacity-60")} aria-busy={busy}>
      <figure className="m-0">
        <figcaption className="mb-2 text-sm text-muted-foreground">Where the trees go</figcaption>
        {placement ? (
          <FieldCanvas values={placement} width={width} height={height} encoding={{ kind: "mask" }} label="Placement of this scenario" />
        ) : (
          <div className="aspect-square w-full rounded-sm bg-secondary" aria-busy="true" />
        )}
      </figure>
      <figure className="m-0">
        <figcaption className="mb-2 text-sm text-muted-foreground">Cooling predicted, hover to read</figcaption>
        {cooling && scale ? (
          <FieldCanvas
            values={cooling}
            width={width}
            height={height}
            encoding={{ kind: "quantity", ramp: COOL, scale: { min: 0, max: scale.max }, unit: " C cooler", floor: 0.05 }}
            label="Cooling predicted for this scenario"
          />
        ) : (
          <div className="aspect-square w-full rounded-sm bg-secondary" aria-busy="true" />
        )}
      </figure>
    </div>
  );
}

