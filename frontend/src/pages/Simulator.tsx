import { type UseQueryResult, keepPreviousData, useQueries, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Info } from "lucide-react";
import { Link, useSearchParams } from "react-router";

import { api, ApiError } from "@/api/client";
import { fetchScenarioField } from "@/api/fields";
import type { CitySummary, ScenarioOutcome, Sweep, TileSummary } from "@/api/models";
import { Chips } from "@/components/Chips";
import { CityMap, type Zoom } from "@/components/CityMap";
import { FieldCanvas } from "@/components/FieldCanvas";
import { HeatReplay } from "@/components/HeatReplay";
import { NextStep } from "@/components/NextStep";
import { OutcomeCurves } from "@/components/OutcomeCurves";
import { Picker } from "@/components/Picker";
import { TileFacts } from "@/components/TileFacts";
import { TradeoffChart } from "@/components/TradeoffChart";
import { Checkbox } from "@/components/ui/checkbox";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Slider } from "@/components/ui/slider";
import { aggregate, type Totals } from "@/lib/aggregate";
import { byName } from "@/lib/order";
import { type OutcomesView, readOutcomesView, storeOutcomesView } from "@/lib/outcomes_view";
import { coolingImage } from "@/lib/overlay";
import { useDebounced } from "@/lib/debounce";
import { decimal, integer, percent } from "@/lib/format";
import { band, type NpyArray } from "@/lib/npy";
import { POLICIES, policyOf } from "@/lib/policies";
import { COOL, extent } from "@/lib/ramp";
import {
  COVERAGE,
  INITIAL_SCALE,
  SIMULATED_COVERAGE,
  type Scale,
  alignToAnswer,
  budgetRange,
  extrapolating,
  leversOf,
  moveBudget,
  moveCoverage,
  rateOf,
  setLocked,
  simulatedBudget,
} from "@/lib/scale";
import { seriesColor } from "@/lib/series";
import { type Cell, cellBounds, cellsOf } from "@/lib/tile_grid";
import { THRESHOLD, readThreshold, storeThreshold } from "@/lib/threshold_store";
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
  const grid = useQuery({ queryKey: ["grid", cityKey], queryFn: () => api.grid(cityKey), enabled: cityKey !== "" });
  const basemap = useQuery({ queryKey: ["basemap"], queryFn: api.basemap });
  const cells = useMemo(() => (grid.data ? cellsOf(grid.data) : []), [grid.data]);

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
        <h1>Heatwave Resilient Cities</h1>
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
          cells={cells}
          basemap={basemap.data?.style_url}
          chosen={chosen}
          focused={focused}
          onFocus={(tile) => choose({ focus: tile })}
          onPick={(tile) => choose({ tiles: chosen.includes(tile) ? chosen : [...chosen, tile], focus: tile })}
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
  const cityChoices = byName(cities).map((found) => ({
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
  cells,
  basemap,
  chosen,
  focused,
  onFocus,
  onPick,
}: {
  city: CitySummary;
  tiles: TileSummary[];
  cells: Cell[];
  basemap: string | undefined;
  chosen: string[];
  focused: string;
  onFocus: (tile: string) => void;
  onPick: (tile: string) => void;
}) {
  const [policyKey, setPolicyKey] = useState("tree");
  const policy = policyOf(policyKey);
  const [designKey, setDesignKey] = useState(policy.designs[0].key);
  const [scale, setScale] = useState<Scale>(INITIAL_SCALE);
  const [assumptions, setAssumptions] = useState<Assumptions>({});
  const [threshold, setThreshold] = useState<number>(readThreshold);
  const [view, setView] = useState<OutcomesView>(readOutcomesView);
  const settled = useDebounced({ scale, assumptions, threshold }, SETTLE_MS);
  const levers = useMemo(
    () => ({ ...leversOf(designKey, settled.scale), ...settled.assumptions, threshold: settled.threshold }),
    [designKey, settled],
  );

  function chooseThreshold(value: number) {
    setThreshold(value);
    storeThreshold(value);
  }

  function chooseView(next: OutcomesView) {
    setView(next);
    storeOutcomesView(next);
  }
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
  const sweep = useQuery({
    queryKey: ["sweep", city.key, focused],
    queryFn: () => api.sweep(city.key, focused),
    enabled: view === "curves" && focused !== "",
    staleTime: Infinity,
  });
  const [zoom, setZoom] = useState<Zoom>("city");
  const [coolingOnMap, setCoolingOnMap] = useState(false);
  const focusedCell = cells.find((cell) => cell.id === focused);
  const overlay = useMemo(() => {
    if (!coolingOnMap || !fields.data || !focusedCell) return undefined;
    const cooling = band(fields.data, 0);
    const [, height, width] = fields.data.shape;
    const url = coolingImage(cooling, width, height, { min: 0, max: extent(cooling).max });
    return url ? { url, bounds: cellBounds(focusedCell) } : undefined;
  }, [coolingOnMap, fields.data, focusedCell]);

  function choosePolicy(key: string) {
    setPolicyKey(key);
    setDesignKey(policyOf(key).designs[0].key);
  }

  return (
    <>
      <div className="mt-8 flex items-center justify-between">
        <h2 className="text-sm font-medium text-muted-foreground">Outcomes</h2>
        <Chips
          label="Outcomes view"
          options={[
            { key: "numbers", label: "numbers" },
            { key: "curves", label: "curves" },
          ]}
          value={view}
          onChange={(key) => chooseView(key as OutcomesView)}
        />
      </div>
      {failed ? (
        <Unanswered error={failed} />
      ) : view === "curves" ? (
        <Curves
          sweep={sweep}
          threshold={focusedOutcome?.threshold ?? threshold}
          outcome={focusedOutcome}
          arrangement={designKey}
          onPickCoverage={(coverage) => setScale(moveCoverage(shown, coverage, rate))}
        />
      ) : (
        <OutcomesRow totals={totals} busy={busy} threshold={focusedOutcome?.threshold ?? threshold} />
      )}
      <div className="mt-8 grid gap-10 lg:grid-cols-[300px_minmax(0,1fr)]">
      <aside aria-label="Levers" className="space-y-8">
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
          <AssumptionsPanel assumptions={assumptions} outcome={focusedOutcome} onChange={setAssumptions} />
        </Lever>
        <Lever title="Threshold" question="Who counts as exposed">
          <div className="flex items-baseline justify-between text-sm">
            <span>Stress line, mean radiant temperature</span>
            <strong className="tabular-nums">{threshold} C</strong>
          </div>
          <Slider
            value={[threshold]}
            min={THRESHOLD.min}
            max={THRESHOLD.max}
            step={THRESHOLD.step}
            onValueChange={([value]) => chooseThreshold(value)}
            aria-label="Stress threshold"
            className="mt-2"
          />
          <p className="mt-2 text-xs text-muted-foreground">
            45 C is this project's line for heat stress outdoors, not a standard; the published lines for heat
            deaths sit higher. Your choice is kept in this browser.
          </p>
        </Lever>
      </aside>
      <section aria-label="The focused tile">
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
              The stored designs were each run through the engine. This scenario is the diamond among them
              {focusedOutcome.threshold !== 45 && "; the stored designs count people against 45 C"}.
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
      </div>
      {cells.length > 0 && basemap && (
        <section aria-label="Where in the city" className="mt-10 border-t pt-6">
          <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
            <h2>
              Where in {city.name} <span className="font-normal text-muted-foreground">{integer(cells.length)} tiles of one square kilometre</span>
            </h2>
            <div className="flex flex-wrap items-center gap-4">
              <Chips
                label="Map view"
                options={[
                  { key: "city", label: "whole city" },
                  { key: "tile", label: "the tile" },
                ]}
                value={zoom}
                onChange={(key) => setZoom(key as Zoom)}
              />
              <label className="flex items-center gap-2 text-sm">
                <Checkbox
                  checked={coolingOnMap}
                  onCheckedChange={(checked) => setCoolingOnMap(checked === true)}
                  aria-label="Cooling on the map"
                />
                cooling on the map
              </label>
            </div>
          </div>
          <p className="mt-1 max-w-[70ch] text-sm text-muted-foreground">
            Ink is residents per tile; the sun outline marks a tile with a model, which a click chooses. The street
            map underneath is the one layer that is not our data.
          </p>
          <div className="mt-4">
            <CityMap style={basemap} cells={cells} chosen={chosen} focused={focused} zoom={zoom} overlay={overlay} onPick={onPick} />
          </div>
        </section>
      )}
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
  const budgets = budgetRange(rate);
  const beyond = extrapolating(scale, rate);
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
        <MarkedSlider
          value={scale.coverage}
          range={COVERAGE}
          mark={SIMULATED_COVERAGE}
          onChange={(value) => onChange(moveCoverage(scale, value, rate))}
          label="Coverage of the plantable ground"
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
        <MarkedSlider
          value={scale.budget}
          range={budgets}
          mark={simulatedBudget(rate)}
          onChange={(value) => onChange(moveBudget(scale, value, rate))}
          label="Budget per tile"
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
      <p className={cn("text-xs", beyond ? "text-destructive" : "text-muted-foreground")} role={beyond ? "status" : undefined}>
        {beyond
          ? `Beyond ${percent(SIMULATED_COVERAGE)} of the plantable ground the surrogate extrapolates past the simulated designs.`
          : `The red mark is ${percent(SIMULATED_COVERAGE)} of the plantable ground, as far as the designs were simulated.`}
      </p>
    </div>
  );
}

/** A slider with a red mark at one value: where the simulated designs stop and the surrogate goes on alone. */
function MarkedSlider({
  value,
  range,
  mark,
  onChange,
  label,
}: {
  value: number;
  range: { min: number; max: number; step: number };
  mark: number | null;
  onChange: (value: number) => void;
  label: string;
}) {
  const fraction = mark === null ? null : Math.min(1, Math.max(0, (mark - range.min) / (range.max - range.min)));
  return (
    <div className="relative mt-2">
      <Slider
        value={[Math.min(range.max, value)]}
        min={range.min}
        max={range.max}
        step={range.step}
        onValueChange={([next]) => onChange(next)}
        aria-label={label}
      />
      {fraction !== null && (
        <span
          className="pointer-events-none absolute top-1/2 size-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-destructive ring-2 ring-background"
          style={{ left: `${fraction * 100}%` }}
          title="as far as the designs were simulated"
          aria-hidden="true"
        />
      )}
    </div>
  );
}

/** The prices a scenario is costed at when a person sets them; otherwise the catalogue's placeholders. */
interface Assumptions {
  unit_cost?: number;
  maintenance?: number;
}

function AssumptionsPanel({
  assumptions,
  outcome,
  onChange,
}: {
  assumptions: Assumptions;
  outcome: ScenarioOutcome | undefined;
  onChange: (assumptions: Assumptions) => void;
}) {
  function set(name: keyof Assumptions, raw: string, scale = 1) {
    const value = Number(raw);
    const next = { ...assumptions };
    if (raw === "" || !Number.isFinite(value)) delete next[name];
    else next[name] = value / scale;
    onChange(next);
  }
  return (
    <details className="mt-5 rounded-md border px-3 py-2 text-sm">
      <summary className="cursor-pointer text-muted-foreground">
        Assumptions{outcome && `, priced at ${outcome.unit_cost} USD per m², ${percent(outcome.maintenance)} a year`}
      </summary>
      <div className="mt-3 grid gap-3">
        <label className="grid gap-1">
          <span className="text-xs text-muted-foreground">Unit cost, USD per square metre</span>
          <input
            type="number"
            min={1}
            step={1}
            inputMode="decimal"
            value={assumptions.unit_cost ?? ""}
            placeholder={outcome ? String(outcome.unit_cost) : ""}
            onChange={(event) => set("unit_cost", event.target.value)}
            className="w-32 rounded-sm border bg-background px-2 py-1 tabular-nums"
          />
        </label>
        <label className="grid gap-1">
          <span className="text-xs text-muted-foreground">Maintenance, percent of capital a year</span>
          <input
            type="number"
            min={0}
            max={99}
            step={1}
            inputMode="decimal"
            value={assumptions.maintenance === undefined ? "" : Math.round(assumptions.maintenance * 100)}
            placeholder={outcome ? String(Math.round(outcome.maintenance * 100)) : ""}
            onChange={(event) => set("maintenance", event.target.value, 100)}
            className="w-32 rounded-sm border bg-background px-2 py-1 tabular-nums"
          />
        </label>
        <p className="text-xs text-muted-foreground">
          The catalogue's prices are placeholders. Yours change the cost and what it buys, never the cooling.
        </p>
      </div>
    </details>
  );
}

function Curves({
  sweep,
  threshold,
  outcome,
  arrangement,
  onPickCoverage,
}: {
  sweep: UseQueryResult<Sweep>;
  threshold: number;
  outcome: ScenarioOutcome | undefined;
  arrangement: string;
  onPickCoverage: (coverage: number) => void;
}) {
  if (sweep.isError) return <Unanswered error={sweep.error} />;
  if (!sweep.data) {
    return (
      <p className="mt-2 text-sm text-muted-foreground" aria-busy="true">
        Computing the curves for this model: the surrogate over every coverage in every arrangement, about half a
        minute the first time, then kept beside the tile.
      </p>
    );
  }
  const live = outcome && {
    arrangement,
    coverage: outcome.coverage,
    values: {
      exposure_drop: outcome.exposure_drop,
      excess_removed: outcome.excess_removed,
      people: outcome.people,
      equity_gap_change: outcome.equity_gap_change,
    },
  };
  return (
    <div className="mt-2">
      <OutcomeCurves sweep={sweep.data} threshold={threshold} live={live} onPickCoverage={onPickCoverage} />
      <p className="mt-2 text-xs text-muted-foreground">
        Lines are the surrogate, dots the engine-verified designs, the diamond this scenario. Click a curve to set the
        coverage. Curves from {sweep.data.model_id}.
      </p>
    </div>
  );
}

function OutcomesRow({ totals, busy, threshold }: { totals: Totals | null; busy: boolean; threshold: number }) {
  if (!totals) {
    return (
      <div className="mt-2 grid gap-3 sm:grid-cols-2 xl:grid-cols-5" aria-busy="true">
        {Array.from({ length: 5 }, (_, index) => (
          <div key={index} className="h-[4.5rem] rounded-md bg-secondary" />
        ))}
      </div>
    );
  }
  const over = totals.tiles > 1 ? ` over ${totals.tiles} tiles` : "";
  const share = totals.baseline_at_risk > 0 ? percent(totals.people / totals.baseline_at_risk, 1) : "0%";
  return (
    <section
      aria-label="Outcomes"
      aria-busy={busy}
      className={cn("mt-2 grid gap-3 transition-opacity sm:grid-cols-2 xl:grid-cols-5", busy && "opacity-60")}
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
        note={`above ${threshold} C, summed over the people exposed${over}`}
      />
      <Outcome
        label={`People moved below ${threshold} C`}
        value={integer(totals.people)}
        note={`${share} of the ${integer(totals.baseline_at_risk)} above it today${over}`}
        explainer={PEOPLE_EXPLAINER}
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

const PEOPLE_EXPLAINER =
  "How this is counted. We know how many people live in each 100 metre square from the GHS population grid, and we " +
  "place them in the buildings there. Nobody stands on their own roof, so we spread each person over the open ground " +
  "within about 25 metres of home. On the design day we take the daytime average radiant temperature of that ground. " +
  "People whose nearby ground is hotter than the threshold count as exposed. This number is how many of them the " +
  "scenario brings below the line.";

function Outcome({
  label,
  value,
  unit,
  note,
  explainer,
}: {
  label: string;
  value: string;
  unit?: string;
  note: string;
  explainer?: string;
}) {
  return (
    <div className="rounded-md border bg-card px-3 py-2">
      <p className="flex items-center gap-1 text-xs text-muted-foreground">
        {label}
        {explainer && (
          <TooltipProvider delayDuration={100}>
            <Tooltip>
              <TooltipTrigger asChild>
                <button type="button" aria-label="How this is counted" className="inline-flex text-muted-foreground hover:text-foreground">
                  <Info className="size-3.5" aria-hidden="true" />
                </button>
              </TooltipTrigger>
              <TooltipContent>{explainer}</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}
      </p>
      <p className="font-display text-2xl font-bold leading-tight tracking-tight">
        {value}
        {unit && <span className="ml-1 font-sans text-sm font-normal text-muted-foreground">{unit}</span>}
      </p>
      <p className="text-[11px] leading-snug text-muted-foreground">{note}</p>
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

