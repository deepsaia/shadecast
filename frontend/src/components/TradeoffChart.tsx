import { CartesianGrid, Legend, Scatter, ScatterChart, XAxis, YAxis, ZAxis } from "recharts";

import type { Plan } from "@/api/models";
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";
import { ARRANGEMENTS, type Arrangement, seriesColor } from "@/lib/series";


/** A point that is not a stored design: a live scenario, drawn as a diamond in the accent color. */
export interface LivePoint {
  exposure_drop: number;
  people: number;
  label: string;
}

const LIVE_COLOR = "var(--sun)";

/**
 * Every plan on both objectives: the average exposure drop against the people moved below the
 * threshold. One fixed color per arrangement, the selected plan drawn larger, a click selects, and a
 * live point sits among them when there is one.
 */
export function TradeoffChart({
  plans,
  selected = null,
  onSelect,
  live,
}: {
  plans: Plan[];
  selected?: string | null;
  onSelect?: (id: string) => void;
  live?: LivePoint;
}) {
  const config = Object.fromEntries([
    ...ARRANGEMENTS.map((arrangement) => [arrangement, { label: arrangement, color: seriesColor(arrangement) }]),
    ...(live ? [[live.label, { label: live.label, color: LIVE_COLOR }]] : []),
  ]);
  return (
    <ChartContainer config={config} className="h-64 w-full">
      <ScatterChart margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
        <CartesianGrid strokeDasharray="2 4" stroke="var(--border)" />
        <XAxis
          type="number"
          dataKey="exposure_drop"
          name="exposure drop"
          unit=" C"
          tickLine={false}
          axisLine={false}
          fontSize={11}
          label={{ value: "average exposure drop, C", position: "insideBottom", offset: -4, fontSize: 11 }}
        />
        <YAxis
          type="number"
          dataKey="people"
          name="people"
          width={44}
          tickLine={false}
          axisLine={false}
          fontSize={11}
          label={{ value: "people below threshold", angle: -90, position: "insideLeft", fontSize: 11 }}
        />
        <ZAxis type="number" dataKey="size" range={[36, 160]} />
        <ChartTooltip
          cursor={{ strokeDasharray: "3 3" }}
          content={<ChartTooltipContent labelKey="id" nameKey="arrangement" />}
        />
        <Legend verticalAlign="top" height={24} iconType="circle" iconSize={8} />
        {ARRANGEMENTS.map((arrangement) => (
          <Scatter
            key={arrangement}
            name={arrangement}
            data={plans
              .filter((plan) => plan.arrangement === arrangement)
              .map((plan) => ({ ...plan, size: plan.id === selected ? 3 : 1 }))}
            fill={seriesColor(arrangement)}
            stroke="var(--card)"
            strokeWidth={1.5}
            onClick={(point) => onSelect?.(String((point as { id?: string }).id))}
            cursor={onSelect ? "pointer" : "default"}
          />
        ))}
        {live && (
          <Scatter
            name={live.label}
            data={[{ ...live, id: live.label, arrangement: live.label, size: 3 }]}
            fill={LIVE_COLOR}
            shape="diamond"
            stroke="var(--foreground)"
            strokeWidth={1.5}
          />
        )}
      </ScatterChart>
    </ChartContainer>
  );
}

export type { Arrangement };
