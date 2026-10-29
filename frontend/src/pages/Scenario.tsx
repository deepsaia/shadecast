import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router";

import { api, ApiError, type ScenarioLevers } from "@/api/client";
import { fetchScenarioField } from "@/api/fields";
import type { ScenarioOutcome } from "@/api/models";
import { FieldCanvas } from "@/components/FieldCanvas";
import { NextStep } from "@/components/NextStep";
import { TradeoffChart } from "@/components/TradeoffChart";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { useDebounced } from "@/lib/debounce";
import { decimal, integer, percent } from "@/lib/format";
import { band, type NpyArray } from "@/lib/npy";
import { COOL, extent } from "@/lib/ramp";
import { ARRANGEMENTS, type Arrangement, seriesColor } from "@/lib/series";
import { cn } from "@/lib/utils";

const DISPLAY_PX = 384;
const SETTLE_MS = 200; // a slider rests this long before the surrogate is asked
const COVERAGE = { min: 0.005, max: 0.3, step: 0.005 };
const BUDGET = { min: 250_000, max: 25_000_000, step: 250_000 };

/** The kinds a person can choose; only trees have a surrogate today, the rest show the instrument's shape. */
const KINDS = [
  { key: "tree", label: "Trees", live: true },
  { key: "shade", label: "Shade structures", live: false },
  { key: "depave", label: "De-paving", live: false },
  { key: "permeable", label: "Permeable paving", live: false },
  { key: "cool_roof", label: "Cool roofs", live: false },
  { key: "cool_paving", label: "Reflective paving", live: false },
];

type Size = { by: "coverage"; coverage: number } | { by: "budget"; budget_usd: number };

function leversOf(arrangement: Arrangement, size: Size): ScenarioLevers {
  if (size.by === "coverage") return { arrangement, coverage: Number(size.coverage.toFixed(3)) };
  return { arrangement, budget_usd: size.budget_usd };
}

/** The simulator: move the levers on one tile and watch the outcomes, the map and the chart answer. */
export function ScenarioPage() {
  const { city = "", tile = "" } = useParams();
  const [arrangement, setArrangement] = useState<Arrangement>("clustered");
  const [size, setSize] = useState<Size>({ by: "coverage", coverage: 0.05 });
  const settled = useDebounced(size, SETTLE_MS);
  const levers = useMemo(() => leversOf(arrangement, settled), [arrangement, settled]);
  const report = useQuery({ queryKey: ["report", city, tile], queryFn: () => api.report(city, tile) });
  const outcome = useQuery({
    queryKey: ["scenario", city, tile, levers],
    queryFn: () => api.scenario(city, tile, levers),
    placeholderData: keepPreviousData,
  });
  const fields = useQuery({
    queryKey: ["scenarioField", city, tile, levers, DISPLAY_PX],
    queryFn: () => fetchScenarioField(city, tile, { ...levers, size: DISPLAY_PX }),
    placeholderData: keepPreviousData,
  });
  const name = report.data?.name ?? city;
  return (
    <article>
      <header>
        <h1>
          {name} <span className="font-sans text-xl font-normal text-muted-foreground">tile {tile}</span>
        </h1>
        <p className="mt-2 max-w-[60ch] text-muted-foreground">
          Choose what to build and how much, and the tile's surrogate answers in the time it takes to read
          this sentence. Every number is against doing nothing on the hottest day the tile has seen.{" "}
          <Link to={`/cities/${city}/tiles/${tile}`} className="underline underline-offset-4">
            The tile itself
          </Link>{" "}
          holds the physics behind it.
        </p>
      </header>
      <div className="mt-8 grid gap-10 lg:grid-cols-[280px_minmax(0,1fr)]">
        <Levers
          arrangement={arrangement}
          size={size}
          outcome={outcome.data}
          onArrangement={setArrangement}
          onSize={setSize}
        />
        <div>
          {outcome.isError ? (
            <Unanswered error={outcome.error} />
          ) : (
            <Outcomes outcome={outcome.data} busy={outcome.isFetching} />
          )}
          <Fields fields={fields.data} busy={fields.isFetching} />
          {report.data && report.data.plans.length > 0 && outcome.data && (
            <section className="mt-8">
              <h2>Against the physics</h2>
              <p className="mt-1 max-w-[60ch] text-sm text-muted-foreground">
                The stored designs were each run through the engine. This scenario is the diamond among them.
              </p>
              <div className="mt-3">
                <TradeoffChart
                  plans={report.data.plans}
                  live={{ exposure_drop: outcome.data.exposure_drop, people: outcome.data.people, label: "this scenario" }}
                />
              </div>
            </section>
          )}
          {outcome.data && (
            <p className="mt-6 text-sm text-muted-foreground">
              Answered by {outcome.data.model_id} in {decimal(outcome.data.surrogate_seconds, 2)} s.
            </p>
          )}
        </div>
      </div>
    </article>
  );
}

function Levers({
  arrangement,
  size,
  outcome,
  onArrangement,
  onSize,
}: {
  arrangement: Arrangement;
  size: Size;
  outcome: ScenarioOutcome | undefined;
  onArrangement: (arrangement: Arrangement) => void;
  onSize: (size: Size) => void;
}) {
  return (
    <aside aria-label="Levers" className="space-y-7">
      <Lever title="What to build">
        <div className="flex flex-wrap gap-1.5">
          {KINDS.map((kind) => (
            <Button
              key={kind.key}
              type="button"
              variant="outline"
              size="sm"
              disabled={!kind.live}
              aria-pressed={kind.live}
              className={cn(kind.live && "border-foreground bg-secondary")}
              title={kind.live ? undefined : "No surrogate yet"}
            >
              {kind.label}
              {!kind.live && (
                <Badge variant="secondary" className="ml-1 font-normal">
                  coming soon
                </Badge>
              )}
            </Button>
          ))}
        </div>
      </Lever>
      <Lever title="How to arrange it">
        <div className="flex flex-wrap gap-1.5">
          {ARRANGEMENTS.map((choice) => (
            <Button
              key={choice}
              type="button"
              variant="outline"
              size="sm"
              aria-pressed={choice === arrangement}
              className={cn(choice === arrangement && "border-foreground bg-secondary")}
              onClick={() => onArrangement(choice)}
            >
              <span className="inline-block size-2.5 rounded-full" style={{ background: seriesColor(choice) }} />
              {choice}
            </Button>
          ))}
        </div>
      </Lever>
      <Lever title="How much">
        <div className="flex gap-1.5">
          <Button
            type="button"
            variant="outline"
            size="xs"
            aria-pressed={size.by === "coverage"}
            className={cn(size.by === "coverage" && "border-foreground bg-secondary")}
            onClick={() => onSize({ by: "coverage", coverage: outcome?.coverage ?? 0.05 })}
          >
            by coverage
          </Button>
          <Button
            type="button"
            variant="outline"
            size="xs"
            aria-pressed={size.by === "budget"}
            className={cn(size.by === "budget" && "border-foreground bg-secondary")}
            onClick={() => onSize({ by: "budget", budget_usd: outcome?.cost_usd ?? 5_000_000 })}
          >
            by budget
          </Button>
        </div>
        {size.by === "coverage" ? (
          <Slider
            value={[size.coverage]}
            min={COVERAGE.min}
            max={COVERAGE.max}
            step={COVERAGE.step}
            onValueChange={([value]) => onSize({ by: "coverage", coverage: value })}
            aria-label="Coverage of feasible ground"
            className="mt-4"
          />
        ) : (
          <Slider
            value={[size.budget_usd]}
            min={BUDGET.min}
            max={BUDGET.max}
            step={BUDGET.step}
            onValueChange={([value]) => onSize({ by: "budget", budget_usd: value })}
            aria-label="Budget in USD"
            className="mt-4"
          />
        )}
        <p className="mt-3 text-sm">
          <strong>
            {size.by === "coverage"
              ? `${percent(size.coverage, 1)} of the plantable ground`
              : `${decimal(size.budget_usd / 1e6, 2)} M USD`}
          </strong>
          {outcome && (
            <span className="text-muted-foreground">
              {size.by === "coverage"
                ? `, ${integer(outcome.trees)} trees, ${decimal(outcome.cost_usd / 1e6, 2)} M USD`
                : `, ${integer(outcome.trees)} trees, ${percent(outcome.coverage, 1)} of the plantable ground`}
            </span>
          )}
        </p>
      </Lever>
    </aside>
  );
}

function Lever({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="text-sm font-medium text-muted-foreground">{title}</h2>
      <div className="mt-2">{children}</div>
    </section>
  );
}

function Outcomes({ outcome, busy }: { outcome: ScenarioOutcome | undefined; busy: boolean }) {
  if (!outcome) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3" aria-busy="true">
        {Array.from({ length: 5 }, (_, index) => (
          <div key={index} className="h-24 rounded-md bg-secondary" />
        ))}
      </div>
    );
  }
  return (
    <section aria-label="Outcomes" aria-busy={busy} className={cn("transition-opacity", busy && "opacity-60")}>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <Outcome
          label="Exposure drop"
          value={decimal(outcome.exposure_drop, 2)}
          unit="C"
          note={`from ${decimal(outcome.baseline_exposure, 1)} C, population weighted`}
        />
        <Outcome
          label="Degree-hours removed"
          value={integer(outcome.excess_removed)}
          note="above 45 C, summed over the people exposed"
        />
        <Outcome
          label="People moved below 45 C"
          value={integer(outcome.people)}
          note={`of ${integer(outcome.baseline_at_risk)} above it today`}
        />
        <Outcome
          label="Equity gap change"
          value={`${outcome.equity_gap_change > 0 ? "+" : ""}${decimal(outcome.equity_gap_change, 2)}`}
          unit="C"
          note="densest tenth against sparsest; below zero narrows it"
        />
        <Outcome
          label="Cost"
          value={decimal(outcome.cost_usd / 1e6, 2)}
          unit="M USD"
          note={`${decimal(outcome.efficiency, 1)} degree-hours removed per 1,000 USD`}
        />
      </div>
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
      <div className="mt-2">
        <NextStep missing="trained surrogate" command={command} />
      </div>
    );
  }
  return (
    <p className="text-destructive" role="alert">
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
    <div className={cn("mt-8 grid gap-6 md:grid-cols-2 transition-opacity", busy && "opacity-60")} aria-busy={busy}>
      <figure className="m-0">
        <figcaption className="mb-2 text-sm text-muted-foreground">Where the trees go</figcaption>
        {placement ? (
          <FieldCanvas
            values={placement}
            width={width}
            height={height}
            encoding={{ kind: "mask" }}
            label="Placement of this scenario"
          />
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
