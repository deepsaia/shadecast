import { CartesianGrid, ComposedChart, Line, ReferenceDot, Scatter, XAxis, YAxis } from "recharts";

import type { Sweep } from "@/api/models";
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";
import { CURVES, type CurveKey, curveRows, designPoints, thresholdIndex } from "@/lib/curves";
import { decimal, integer } from "@/lib/format";
import { ARRANGEMENTS, seriesColor } from "@/lib/series";

/** The scenario on the levers, drawn as a diamond in the accent colour wherever a chart pins it. */
function Diamond({ cx = 0, cy = 0 }: { cx?: number; cy?: number }) {
  const r = 6;
  return (
    <polygon
      points={`${cx},${cy - r} ${cx + r},${cy} ${cx},${cy + r} ${cx - r},${cy}`}
      fill="var(--sun)"
      stroke="var(--foreground)"
      strokeWidth={1.5}
    />
  );
}

export interface LiveScenario {
  arrangement: string;
  coverage: number; // share of the plantable ground
  values: Record<CurveKey, number>;
}

/**
 * Four compact charts, one per outcome, each the whole curve of the outcome against coverage in every
 * arrangement: the surrogate as lines, the engine-verified designs as dots, and the scenario on the
 * levers pinned as a diamond. The threshold picks the row of the table for the two bound outcomes.
 */
export function OutcomeCurves({
  sweep,
  threshold,
  live,
  onPickCoverage,
}: {
  sweep: Sweep;
  threshold: number;
  live?: LiveScenario;
  onPickCoverage?: (coverage: number) => void;
}) {
  const index = thresholdIndex(sweep, threshold);
  const config = Object.fromEntries(
    ARRANGEMENTS.map((arrangement) => [arrangement, { label: arrangement, color: seriesColor(arrangement) }]),
  );
  return (
    <section aria-label="Outcome curves" className="grid gap-4 sm:grid-cols-2">
      {CURVES.map((curve) => {
        const rows = curveRows(sweep, curve.key, index);
        const designs = designPoints(sweep, curve.key, index);
        const format = curve.key === "exposure_drop" || curve.key === "equity_gap_change" ? decimal : integer;
        return (
          <figure key={curve.key} className="m-0 rounded-md border bg-card px-3 py-2">
            <figcaption className="flex items-baseline justify-between text-xs text-muted-foreground">
              <span>
                {curve.label}
                {curve.unit && `, ${curve.unit}`}
              </span>
              {live && (
                <span className="tabular-nums text-foreground">
                  {format(live.values[curve.key])} at {decimal(live.coverage * 100, 1)}%
                </span>
              )}
            </figcaption>
            <ChartContainer config={config} className="h-36 w-full">
              <ComposedChart
                data={rows}
                margin={{ top: 8, right: 8, bottom: 0, left: 0 }}
                onClick={(state) => {
                  const picked = Number(state?.activeLabel);
                  if (onPickCoverage && Number.isFinite(picked)) onPickCoverage(picked / 100);
                }}
                style={{ cursor: onPickCoverage ? "pointer" : "default" }}
              >
                <CartesianGrid strokeDasharray="2 4" stroke="var(--border)" />
                <XAxis
                  dataKey="coverage"
                  type="number"
                  domain={[0, 100]}
                  ticks={[0, 25, 50, 75, 100]}
                  unit="%"
                  tickLine={false}
                  axisLine={false}
                  fontSize={10}
                />
                <YAxis width={44} tickLine={false} axisLine={false} fontSize={10} tickFormatter={(value) => format(value)} />
                <ChartTooltip content={<ChartTooltipContent labelFormatter={(label) => `${label}% of the ground`} />} />
                {ARRANGEMENTS.map((arrangement) => (
                  <Line
                    key={arrangement}
                    type="monotone"
                    dataKey={arrangement}
                    stroke={seriesColor(arrangement)}
                    strokeWidth={2}
                    dot={false}
                    isAnimationActive={false}
                  />
                ))}
                {ARRANGEMENTS.map((arrangement) => (
                  <Scatter
                    key={`${arrangement}-designs`}
                    name={`${arrangement} designs`}
                    data={designs.filter((design) => design.arrangement === arrangement)}
                    dataKey="value"
                    fill={seriesColor(arrangement)}
                    stroke="var(--card)"
                    isAnimationActive={false}
                  />
                ))}
                {live && (
                  <ReferenceDot
                    x={Math.round(live.coverage * 1000) / 10}
                    y={live.values[curve.key]}
                    r={5}
                    shape={Diamond}
                  />
                )}
              </ComposedChart>
            </ChartContainer>
          </figure>
        );
      })}
    </section>
  );
}
